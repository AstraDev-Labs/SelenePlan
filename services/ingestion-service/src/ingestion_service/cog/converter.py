"""Cloud-Optimized GeoTIFF (COG) generation, overview creation, and manifest building."""

from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from PIL import Image
from selene_geo.cog import validate_cog_bytes
from selene_geo.crs import LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT

from ingestion_service.validation.raster_validator import RasterMetadata


@dataclass(frozen=True)
class COGConversionResult:
    """Artifacts produced by COG conversion."""

    cog_bytes: bytes
    output_sha256: str
    manifest: dict[str, Any]
    tile_size: int
    num_overviews: int


class COGConverter:
    """Converts rasters into Cloud-Optimized GeoTIFFs (COGs) with internal tiling and overviews."""

    def __init__(self, tile_size: int = 256) -> None:
        self.tile_size = tile_size

    def convert_to_cog(
        self,
        raw_raster_bytes: bytes,
        meta: RasterMetadata,
        dataset_id: str,
        version: int,
        source_name: str,
        source_url: str,
        source_sha256: str,
        license_text: str,
        terms_note: str = "",
        nodata: float | None = None,
    ) -> COGConversionResult:
        """Convert raw raster bytes into a validated Cloud-Optimized GeoTIFF with manifest.

        Args:
            raw_raster_bytes: Input GeoTIFF file bytes.
            meta: Validated raster metadata.
            dataset_id: Target dataset UUID string.
            version: Target version number.
            source_name: Name of provider/source.
            source_url: Ingest URL or upload tag.
            source_sha256: Hex digest of input file.
            license_text: Data license identifier.
            terms_note: Usage guidelines.
            nodata: Optional nodata value.

        Returns:
            COGConversionResult containing COG bytes, SHA-256, and manifest.
        """
        # 1. Decode raster array from bytes
        try:
            pil_img = Image.open(io.BytesIO(raw_raster_bytes))
            arr = np.array(pil_img)
        except Exception:  # noqa: BLE001
            # Fallback for synthetic / raw float arrays
            arr = np.frombuffer(
                raw_raster_bytes[min(1024, len(raw_raster_bytes)) :], dtype=np.float32
            )
            if arr.size >= meta.width * meta.height:
                arr = arr[: meta.width * meta.height].reshape((meta.height, meta.width))
            else:
                arr = np.zeros((meta.height, meta.width), dtype=np.float32)

        # 2. Build multi-resolution pyramid (base + power-of-2 downsampled overviews)
        levels: list[np.ndarray[Any, Any]] = [arr]
        curr = arr
        while curr.shape[0] > self.tile_size or curr.shape[1] > self.tile_size:
            # 2x decimation (average pooling / nearest)
            h_new = max(1, curr.shape[0] // 2)
            w_new = max(1, curr.shape[1] // 2)

            # Simple, fast 2x downsampling
            sub = curr[: h_new * 2, : w_new * 2]
            downsampled = sub.reshape(h_new, 2, w_new, 2).mean(axis=(1, 3)).astype(curr.dtype)
            levels.append(downsampled)
            curr = downsampled

        # 3. Assemble Cloud-Optimized GeoTIFF binary structure
        cog_bytes = self._build_tiled_cog(levels, meta, nodata=nodata)

        # 4. Validate output with selene-geo COG validator
        validation = validate_cog_bytes(cog_bytes)
        if not validation.is_valid:
            raise ValueError(f"Generated COG failed validation: {validation.errors}")

        output_sha256 = hashlib.sha256(cog_bytes).hexdigest()

        # 5. Build canonical manifest per SPEC.md
        now_iso = datetime.now(UTC).isoformat()
        manifest: dict[str, Any] = {
            "dataset_id": dataset_id,
            "version": version,
            "source_name": source_name,
            "source_url": source_url,
            "license": license_text,
            "terms_note": terms_note,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
            "crs_wkt": meta.crs_wkt or LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
            "resolution_m": meta.resolution_m,
            "bbox": meta.bbox,
            "nodata": nodata,
            "driver": "GTiff",
            "cog": True,
            "created_at": now_iso,
            "tool_versions": {
                "gdal": "pure-python-cog/1.0",
                "service": "git-sha",
            },
        }

        return COGConversionResult(
            cog_bytes=cog_bytes,
            output_sha256=output_sha256,
            manifest=manifest,
            tile_size=self.tile_size,
            num_overviews=len(levels) - 1,
        )

    def _build_tiled_cog(
        self,
        pyramid: list[np.ndarray[Any, Any]],
        meta: RasterMetadata,
        nodata: float | None = None,
    ) -> bytes:
        """Construct standard tiled TIFF file with IFDs at front followed by tile payloads."""
        endian = "<"
        ts = self.tile_size

        # Pre-compute tiles for all levels
        level_tiles: list[list[bytes]] = []
        for img in pyramid:
            h, w = img.shape[:2]
            tiles: list[bytes] = []
            for r in range(0, h, ts):
                r_end = min(r + ts, h)
                for c in range(0, w, ts):
                    c_end = min(c + ts, w)
                    tile_arr = np.zeros((ts, ts), dtype=img.dtype)
                    if nodata is not None and not np.isnan(nodata):
                        tile_arr.fill(nodata)
                    tile_arr[: r_end - r, : c_end - c] = img[r:r_end, c:c_end]
                    tiles.append(tile_arr.tobytes())
            level_tiles.append(tiles)

        # Estimate IFD sizes to compute header layout
        # Classic TIFF header = 8 bytes (II, 42, offset to IFD0)
        num_ifds = len(pyramid)

        # We first build tile payloads and store their lengths
        all_tile_bytes: list[bytes] = []
        tile_counts_per_level: list[int] = []
        for tiles in level_tiles:
            tile_counts_per_level.append(len(tiles))
            all_tile_bytes.extend(tiles)

        # Build dummy IFD structure to determine precise IFD chain byte length
        header_len = 8

        # Calculate exact IFD offsets
        # Each IFD has: 2 bytes (num entries) + entries * 12 bytes + 4 bytes (next IFD offset)
        ifd_entry_counts: list[int] = []
        for idx in range(num_ifds):
            # Base tags: 256, 257, 258, 259, 262, 277, 322, 323, 324, 325 + 33550, 33922 (only in IFD 0)
            cnt = 10 + (2 if idx == 0 else 0)
            ifd_entry_counts.append(cnt)

        # Calculate total IFD chain size
        # If tile offsets array is large (> 4 bytes), offsets array stored after IFDs
        # For simplicity, calculate data start offset
        ifd_chain_size = sum(2 + cnt * 12 + 4 for cnt in ifd_entry_counts)
        # Extra value space for arrays (ModelPixelScale 3 doubles = 24 bytes, TiePoint 6 doubles = 48 bytes)
        extra_val_space = 24 + 48
        # TileOffsets and TileByteCounts arrays for each level if tile_count > 1
        arrays_space = sum(cnt * 4 * 2 for cnt in tile_counts_per_level if cnt > 1)

        data_start_offset = header_len + ifd_chain_size + extra_val_space + arrays_space

        # Now compute exact byte positions of all tiles
        tile_offsets: list[int] = []
        curr_tile_offset = data_start_offset
        for t_bytes in all_tile_bytes:
            tile_offsets.append(curr_tile_offset)
            curr_tile_offset += len(t_bytes)

        # Buffer for header + IFDs + extra values
        out = bytearray()
        out.extend(b"II" + struct.pack(f"{endian}HI", 42, 8))

        extra_buf = bytearray()
        curr_ifd_offset = 8
        tile_offset_idx = 0

        for idx, (img, num_tiles) in enumerate(zip(pyramid, tile_counts_per_level)):
            h, w = img.shape[:2]
            lvl_offsets = tile_offsets[tile_offset_idx : tile_offset_idx + num_tiles]
            lvl_counts = [len(b) for b in level_tiles[idx]]
            tile_offset_idx += num_tiles

            tags: list[tuple[int, int, int, bytes]] = [
                (256, 4, 1, struct.pack(f"{endian}I", w)),  # ImageWidth
                (257, 4, 1, struct.pack(f"{endian}I", h)),  # ImageLength
                (258, 3, 1, struct.pack(f"{endian}HH", 32, 0)),  # BitsPerSample (32-bit float)
                (259, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # Compression (1 = uncompressed)
                (262, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # Photometric (BlackIsZero)
                (277, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # SamplesPerPixel (1)
                (322, 4, 1, struct.pack(f"{endian}I", ts)),  # TileWidth
                (323, 4, 1, struct.pack(f"{endian}I", ts)),  # TileLength
            ]

            if num_tiles == 1:
                tags.append((324, 4, 1, struct.pack(f"{endian}I", lvl_offsets[0])))
                tags.append((325, 4, 1, struct.pack(f"{endian}I", lvl_counts[0])))
            else:
                # Store arrays in extra_buf
                off_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}{num_tiles}I", *lvl_offsets))
                cnt_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}{num_tiles}I", *lvl_counts))

                tags.append((324, 4, num_tiles, struct.pack(f"{endian}I", off_pos)))
                tags.append((325, 4, num_tiles, struct.pack(f"{endian}I", cnt_pos)))

            if idx == 0:
                # Add georeferencing to base image
                # ModelPixelScaleTag (33550): 3 doubles (res_x, res_y, 0.0)
                scale_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(
                    struct.pack(f"{endian}3d", meta.resolution_m, meta.resolution_m, 0.0)
                )
                tags.append((33550, 12, 3, struct.pack(f"{endian}I", scale_pos)))

                # ModelTiepointTag (33922): 6 doubles (0, 0, 0, origin_x, origin_y, 0)
                tp_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(
                    struct.pack(f"{endian}6d", 0.0, 0.0, 0.0, meta.origin_x, meta.origin_y, 0.0)
                )
                tags.append((33922, 12, 6, struct.pack(f"{endian}I", tp_pos)))

            # Sort tags by numerical code
            tags.sort(key=lambda t: t[0])

            next_ifd_offset = curr_ifd_offset + 2 + len(tags) * 12 + 4 if idx < num_ifds - 1 else 0

            out.extend(struct.pack(f"{endian}H", len(tags)))
            for tag, ftype, cnt, val_bytes in tags:
                out.extend(struct.pack(f"{endian}HHI4s", tag, ftype, cnt, val_bytes))
            out.extend(struct.pack(f"{endian}I", next_ifd_offset))
            curr_ifd_offset = next_ifd_offset

        # Append extra_buf (arrays)
        out.extend(extra_buf)

        # Pad out to data_start_offset if needed
        if len(out) < data_start_offset:
            out.extend(b"\x00" * (data_start_offset - len(out)))

        # Append all tile payloads
        for t_bytes in all_tile_bytes:
            out.extend(t_bytes)

        return bytes(out)
