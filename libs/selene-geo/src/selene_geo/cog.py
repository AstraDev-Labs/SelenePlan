"""Cloud Optimized GeoTIFF (COG) validation helper.

Validates:
1. Valid TIFF / BigTIFF structure and magic header.
2. Internal tiling (TileWidth and TileLength tags present on full-res image).
3. Overviews presence and structure for multi-resolution pyramids.
4. COG offset ordering (IFDs before image tile data).
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Standard TIFF tag constants
TAG_IMAGE_WIDTH = 256
TAG_IMAGE_LENGTH = 257
TAG_COMPRESSION = 259
TAG_TILE_WIDTH = 322
TAG_TILE_LENGTH = 323
TAG_TILE_OFFSETS = 324
TAG_TILE_BYTE_COUNTS = 325
TAG_SUB_IFDS = 330


class COGValidationResult(BaseModel):
    """Structured result of COG layout validation."""

    is_valid: bool
    is_tiled: bool = False
    tile_width: int | None = None
    tile_height: int | None = None
    overview_count: int = 0
    is_bigtiff: bool = False
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}


def validate_cog_bytes(data: bytes | io.BytesIO | Path | str) -> COGValidationResult:
    """Validate whether input bytes, path, or stream represents a valid Cloud Optimized GeoTIFF.

    Args:
        data: Raw file bytes, file-like BytesIO buffer, or Path/str to a GeoTIFF.

    Returns:
        COGValidationResult detailing validation status, tiling, and any defects.
    """
    if isinstance(data, (str, Path)):
        with open(data, "rb") as f:
            return _validate_tiff_stream(f)
    if isinstance(data, bytes):
        return _validate_tiff_stream(io.BytesIO(data))
    return _validate_tiff_stream(data)


def _validate_tiff_stream(f: io.BufferedIOBase) -> COGValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    f.seek(0)
    header = f.read(16)
    if len(header) < 8:
        return COGValidationResult(
            is_valid=False,
            errors=["File too small to be a valid TIFF"],
        )

    # 1. Byte order
    byte_order_mark = header[:2]
    if byte_order_mark == b"II":
        endian = "<"
    elif byte_order_mark == b"MM":
        endian = ">"
    else:
        return COGValidationResult(
            is_valid=False,
            errors=[f"Invalid TIFF byte order mark: {byte_order_mark!r}. Must be 'II' or 'MM'."],
        )

    # 2. Magic number
    (version,) = struct.unpack(f"{endian}H", header[2:4])
    is_bigtiff = False
    if version == 42:
        is_bigtiff = False
        (first_ifd_offset,) = struct.unpack(f"{endian}I", header[4:8])
    elif version == 43:
        is_bigtiff = True
        (bytesize, _zero, first_ifd_offset) = struct.unpack(f"{endian}HHQ", header[4:16])
        if bytesize != 8:
            return COGValidationResult(
                is_valid=False,
                errors=[f"Unsupported BigTIFF byte size: {bytesize}"],
            )
    else:
        return COGValidationResult(
            is_valid=False,
            errors=[
                f"Invalid TIFF magic number: {version}. Expected 42 (Classic) or 43 (BigTIFF)."
            ],
        )

    details["is_bigtiff"] = is_bigtiff
    details["first_ifd_offset"] = first_ifd_offset

    # 3. Read IFD chain
    ifds: list[dict[int, Any]] = []
    ifd_offsets: list[int] = []
    curr_offset = first_ifd_offset

    while curr_offset != 0:
        if curr_offset in ifd_offsets:
            errors.append("Cyclic IFD chain detected")
            break
        ifd_offsets.append(curr_offset)
        f.seek(curr_offset)

        if not is_bigtiff:
            num_entries_bytes = f.read(2)
            if len(num_entries_bytes) < 2:
                errors.append(f"Unexpected EOF reading IFD entry count at offset {curr_offset}")
                break
            (num_entries,) = struct.unpack(f"{endian}H", num_entries_bytes)
            entry_size = 12
        else:
            num_entries_bytes = f.read(8)
            if len(num_entries_bytes) < 8:
                errors.append(
                    f"Unexpected EOF reading BigTIFF IFD entry count at offset {curr_offset}"
                )
                break
            (num_entries,) = struct.unpack(f"{endian}Q", num_entries_bytes)
            entry_size = 20

        raw_entries = f.read(num_entries * entry_size)
        if len(raw_entries) < num_entries * entry_size:
            errors.append("Truncated IFD entries")
            break

        tags: dict[int, Any] = {}
        for i in range(num_entries):
            chunk = raw_entries[i * entry_size : (i + 1) * entry_size]
            if not is_bigtiff:
                tag, field_type, count, val_or_offset = struct.unpack(f"{endian}HHI4s", chunk)
            else:
                tag, field_type, count, val_or_offset = struct.unpack(f"{endian}HHQ8s", chunk)

            # Extract integer value if count == 1 and short/long
            val: Any = val_or_offset
            if count == 1:
                if field_type == 3:  # SHORT
                    val = struct.unpack(f"{endian}H", val_or_offset[:2])[0]
                elif field_type == 4:  # LONG
                    val = struct.unpack(f"{endian}I", val_or_offset[:4])[0]
                elif field_type == 16 and is_bigtiff:  # LONG8
                    val = struct.unpack(f"{endian}Q", val_or_offset[:8])[0]

            tags[tag] = val

        ifds.append(tags)

        # Next IFD pointer
        if not is_bigtiff:
            next_ptr_bytes = f.read(4)
            curr_offset = (
                struct.unpack(f"{endian}I", next_ptr_bytes)[0] if len(next_ptr_bytes) == 4 else 0
            )
        else:
            next_ptr_bytes = f.read(8)
            curr_offset = (
                struct.unpack(f"{endian}Q", next_ptr_bytes)[0] if len(next_ptr_bytes) == 8 else 0
            )

    if not ifds:
        return COGValidationResult(
            is_valid=False,
            is_bigtiff=is_bigtiff,
            errors=errors or ["No IFDs found in TIFF"],
        )

    # 4. Check Base Image (IFD 0)
    base_ifd = ifds[0]
    img_width = base_ifd.get(TAG_IMAGE_WIDTH)
    img_height = base_ifd.get(TAG_IMAGE_LENGTH)
    tile_w = base_ifd.get(TAG_TILE_WIDTH)
    tile_h = base_ifd.get(TAG_TILE_LENGTH)

    details["width"] = img_width
    details["height"] = img_height
    details["tile_width"] = tile_w
    details["tile_height"] = tile_h
    details["ifd_count"] = len(ifds)

    is_tiled = bool(tile_w and tile_h)
    if not is_tiled:
        errors.append(
            "The base image is not tiled (missing TileWidth / TileLength tags). COGs must be tiled."
        )

    # 5. Check Overviews
    overview_count = len(ifds) - 1
    details["overview_count"] = overview_count

    if (
        is_tiled
        and img_width
        and img_height
        and (img_width > (tile_w or 256) or img_height > (tile_h or 256))
        and overview_count == 0
    ):
        warnings.append(
            f"Raster dimensions ({img_width}x{img_height}) exceed tile size, but no overviews exist."
        )

    # Check that overview IFDs are also tiled
    for idx, ov_ifd in enumerate(ifds[1:], start=1):
        if not (ov_ifd.get(TAG_TILE_WIDTH) and ov_ifd.get(TAG_TILE_LENGTH)):
            warnings.append(f"Overview {idx} is not tiled.")

    # 6. Check COG Layout (IFDs must precede data offsets)
    # Check that first IFD offset is near the header
    first_tile_offset = base_ifd.get(TAG_TILE_OFFSETS)
    if isinstance(first_tile_offset, int) and first_ifd_offset > first_tile_offset:
        warnings.append(
            "IFD offset is placed after tile data; standard COGs place IFDs at file start."
        )

    is_valid = len(errors) == 0

    return COGValidationResult(
        is_valid=is_valid,
        is_tiled=is_tiled,
        tile_width=tile_w if isinstance(tile_w, int) else None,
        tile_height=tile_h if isinstance(tile_h, int) else None,
        overview_count=overview_count,
        is_bigtiff=is_bigtiff,
        errors=errors,
        warnings=warnings,
        details=details,
    )
