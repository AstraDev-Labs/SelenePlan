"""Cloud-Optimized GeoTIFF writer for terrain analysis arrays."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from selene_geo.cog import validate_cog_bytes
from selene_geo.crs import LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT


@dataclass(frozen=True)
class COGWriteResult:
    """Result of converting a numpy array to a validated COG."""

    cog_bytes: bytes
    sha256: str
    size_bytes: int
    manifest: dict[str, Any]
    width: int
    height: int
    tile_size: int
    num_overviews: int


class ArrayCOGWriter:
    """Converts 2D numpy arrays (float32 or uint8) into validated Cloud-Optimized GeoTIFFs."""

    def __init__(self, tile_size: int = 256) -> None:
        self.tile_size = tile_size

    def write_cog(
        self,
        array: np.ndarray,
        product_id: str,
        kind: str,
        resolution_m: float = 10.0,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
        nodata: float | None = np.nan,
        extra_manifest: dict[str, Any] | None = None,
    ) -> COGWriteResult:
        """Write array to COG format with power-of-2 pyramid overviews."""
        if array.ndim != 2:
            raise ValueError(f"Array must be 2-dimensional, got shape {array.shape}")

        height, width = array.shape
        endian = "<"  # Little-endian (II)

        # 1. Build multi-resolution pyramid
        pyramid: list[np.ndarray] = [array]
        curr = array
        while curr.shape[0] > self.tile_size * 2 or curr.shape[1] > self.tile_size * 2:
            # 2x2 decimation
            h_half = max(1, curr.shape[0] // 2)
            w_half = max(1, curr.shape[1] // 2)
            downsampled = curr[: h_half * 2 : 2, : w_half * 2 : 2]
            pyramid.append(downsampled)
            curr = downsampled

        num_overviews = len(pyramid) - 1
        num_ifds = len(pyramid)

        # 2. Slice tiles for all levels
        ts = self.tile_size
        level_tiles: list[list[bytes]] = []
        for img in pyramid:
            h, w = img.shape[:2]
            tiles: list[bytes] = []
            for r in range(0, h, ts):
                r_end = min(r + ts, h)
                for c in range(0, w, ts):
                    c_end = min(c + ts, w)
                    tile_arr = np.zeros((ts, ts), dtype=img.dtype)
                    if nodata is not None:
                        if np.isnan(nodata):
                            if np.issubdtype(img.dtype, np.floating):
                                tile_arr.fill(np.nan)
                            else:
                                tile_arr.fill(0)
                        else:
                            tile_arr.fill(nodata)
                    tile_arr[: r_end - r, : c_end - c] = img[r:r_end, c:c_end]
                    tiles.append(tile_arr.tobytes())
            level_tiles.append(tiles)

        # 3. Assemble IFDs and offsets
        all_tile_bytes: list[bytes] = []
        tile_counts_per_level: list[int] = []
        for tiles in level_tiles:
            tile_counts_per_level.append(len(tiles))
            all_tile_bytes.extend(tiles)

        header_len = 8
        ifd_entry_counts: list[int] = []
        for idx in range(num_ifds):
            cnt = 10 + (2 if idx == 0 else 0)
            ifd_entry_counts.append(cnt)

        ifd_chain_size = sum(2 + cnt * 12 + 4 for cnt in ifd_entry_counts)
        extra_val_space = 24 + 48  # ModelPixelScale (24 bytes) + ModelTiepoint (48 bytes)
        arrays_space = sum(cnt * 4 * 2 for cnt in tile_counts_per_level if cnt > 1)

        data_start_offset = header_len + ifd_chain_size + extra_val_space + arrays_space

        tile_offsets: list[int] = []
        curr_tile_offset = data_start_offset
        for t_bytes in all_tile_bytes:
            tile_offsets.append(curr_tile_offset)
            curr_tile_offset += len(t_bytes)

        out = bytearray()
        out.extend(b"II" + struct.pack(f"{endian}HI", 42, 8))

        extra_buf = bytearray()
        tile_offset_idx = 0

        # Determine BitsPerSample and SampleFormat
        is_float = array.dtype in (np.float32, np.float64)
        bits_per_sample = 32 if is_float else 8

        for idx, (img, num_tiles) in enumerate(zip(pyramid, tile_counts_per_level)):
            h, w = img.shape[:2]
            lvl_offsets = tile_offsets[tile_offset_idx : tile_offset_idx + num_tiles]
            lvl_counts = [len(b) for b in level_tiles[idx]]
            tile_offset_idx += num_tiles

            tags: list[tuple[int, int, int, bytes]] = [
                (256, 4, 1, struct.pack(f"{endian}I", w)),  # ImageWidth
                (257, 4, 1, struct.pack(f"{endian}I", h)),  # ImageLength
                (258, 3, 1, struct.pack(f"{endian}HH", bits_per_sample, 0)),  # BitsPerSample
                (259, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # Compression (1=None)
                (262, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # Photometric (BlackIsZero)
                (277, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # SamplesPerPixel (1)
                (322, 4, 1, struct.pack(f"{endian}I", ts)),  # TileWidth
                (323, 4, 1, struct.pack(f"{endian}I", ts)),  # TileLength
            ]

            if num_tiles == 1:
                tags.append((324, 4, 1, struct.pack(f"{endian}I", lvl_offsets[0])))
                tags.append((325, 4, 1, struct.pack(f"{endian}I", lvl_counts[0])))
            else:
                off_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}{num_tiles}I", *lvl_offsets))
                cnt_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}{num_tiles}I", *lvl_counts))

                tags.append((324, 4, num_tiles, struct.pack(f"{endian}I", off_pos)))
                tags.append((325, 4, num_tiles, struct.pack(f"{endian}I", cnt_pos)))

            if idx == 0:
                scale_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}3d", resolution_m, resolution_m, 0.0))
                tags.append((33550, 12, 3, struct.pack(f"{endian}I", scale_pos)))

                tiepoint_pos = header_len + ifd_chain_size + len(extra_buf)
                extra_buf.extend(struct.pack(f"{endian}6d", 0.0, 0.0, 0.0, origin_x, origin_y, 0.0))
                tags.append((33922, 12, 6, struct.pack(f"{endian}I", tiepoint_pos)))

            tags.sort(key=lambda t: t[0])

            # Write IFD
            out.extend(struct.pack(f"{endian}H", len(tags)))
            for tag_id, tag_type, count, val_bytes in tags:
                out.extend(struct.pack(f"{endian}HHI", tag_id, tag_type, count))
                out.extend(val_bytes)

            next_ifd_offset = (
                header_len + sum(2 + cnt * 12 + 4 for cnt in ifd_entry_counts[: idx + 1])
                if idx < num_ifds - 1
                else 0
            )
            out.extend(struct.pack(f"{endian}I", next_ifd_offset))

        out.extend(extra_buf)

        # Append image tiles
        for t_bytes in all_tile_bytes:
            out.extend(t_bytes)

        cog_bytes = bytes(out)

        # Validate layout
        val_res = validate_cog_bytes(cog_bytes)
        if not val_res.is_valid:
            raise ValueError(f"Generated COG failed validation: {val_res.errors}")

        cog_sha256 = hashlib.sha256(cog_bytes).hexdigest()

        # Build manifest
        manifest: dict[str, Any] = {
            "schema": "selene.manifest.v1",
            "product_id": product_id,
            "kind": kind,
            "crs_wkt": crs_wkt,
            "resolution_m": resolution_m,
            "dimensions": {"width": width, "height": height},
            "tile_size": ts,
            "num_overviews": num_overviews,
            "output_sha256": cog_sha256,
            "size_bytes": len(cog_bytes),
            "generated_at": datetime.now(UTC).isoformat(),
        }
        if extra_manifest:
            manifest.update(extra_manifest)

        return COGWriteResult(
            cog_bytes=cog_bytes,
            sha256=cog_sha256,
            size_bytes=len(cog_bytes),
            manifest=manifest,
            width=width,
            height=height,
            tile_size=ts,
            num_overviews=num_overviews,
        )
