"""Raster format and security validation (dimensions, decompression bomb guard, driver checks)."""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any

from selene_geo.crs import LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT, assert_lunar_crs

from ingestion_service.config import settings


@dataclass(frozen=True)
class RasterMetadata:
    """Extracted raster geometric and spatial reference metadata."""

    width: int
    height: int
    bits_per_sample: int
    samples_per_pixel: int
    resolution_m: float
    origin_x: float
    origin_y: float
    bbox: list[float]  # [min_x, min_y, max_x, max_y]
    crs_wkt: str
    driver: str = "GTiff"


class RasterSecurityError(ValueError):
    """Raised when an ingested raster violates security boundaries."""


def validate_raster_header_and_limits(
    data: bytes,
    max_raster_dim: int | None = None,
    max_total_pixels: int | None = None,
    max_decompression_ratio: float | None = None,
) -> RasterMetadata:
    """Validate TIFF header, driver, dimensions, and decompression ratios.

    Args:
        data: Raw raster file bytes.
        max_raster_dim: Maximum allowed width or height in pixels.
        max_total_pixels: Maximum allowed total pixel count (w * h).
        max_decompression_ratio: Maximum allowed ratio of uncompressed size to file size.

    Returns:
        RasterMetadata if valid.

    Raises:
        RasterSecurityError: If raster exceeds safety thresholds or is corrupted.
    """
    dim_limit = max_raster_dim or settings.max_raster_dim
    pixel_limit = max_total_pixels or settings.max_total_pixels
    ratio_limit = max_decompression_ratio or settings.max_decompression_ratio

    if len(data) < 8:
        raise RasterSecurityError("Invalid raster: file is smaller than 8 bytes.")

    order_bytes = data[:2]
    if order_bytes == b"II":
        endian = "<"
    elif order_bytes == b"MM":
        endian = ">"
    else:
        raise RasterSecurityError(
            f"Unsupported raster format: invalid byte order marker {order_bytes!r}. Only TIFF/GeoTIFF is supported."
        )

    (magic,) = struct.unpack(f"{endian}H", data[2:4])
    is_bigtiff = magic == 43
    if magic not in (42, 43):
        raise RasterSecurityError(
            f"Unsupported driver: magic number {magic}. Expected 42 (Classic TIFF) or 43 (BigTIFF)."
        )

    stream = io.BytesIO(data)
    stream.seek(4)

    if not is_bigtiff:
        first_ifd_bytes = stream.read(4)
        if len(first_ifd_bytes) < 4:
            raise RasterSecurityError("Corrupted TIFF header: missing IFD offset.")
        (first_ifd_offset,) = struct.unpack(f"{endian}I", first_ifd_bytes)
        entry_size = 12
    else:
        stream.read(4)  # offset size (8) and unused (0)
        first_ifd_bytes = stream.read(8)
        if len(first_ifd_bytes) < 8:
            raise RasterSecurityError("Corrupted BigTIFF header: missing IFD offset.")
        (first_ifd_offset,) = struct.unpack(f"{endian}Q", first_ifd_bytes)
        entry_size = 20

    if first_ifd_offset <= 0 or first_ifd_offset >= len(data):
        raise RasterSecurityError(f"Corrupted IFD offset: {first_ifd_offset}")

    stream.seek(first_ifd_offset)
    if not is_bigtiff:
        num_entries_bytes = stream.read(2)
        if len(num_entries_bytes) < 2:
            raise RasterSecurityError("Truncated IFD entry count.")
        (num_entries,) = struct.unpack(f"{endian}H", num_entries_bytes)
    else:
        num_entries_bytes = stream.read(8)
        if len(num_entries_bytes) < 8:
            raise RasterSecurityError("Truncated BigTIFF IFD entry count.")
        (num_entries,) = struct.unpack(f"{endian}Q", num_entries_bytes)

    raw_entries = stream.read(num_entries * entry_size)
    if len(raw_entries) < num_entries * entry_size:
        raise RasterSecurityError("Truncated IFD entries.")

    tags: dict[int, Any] = {}
    for i in range(num_entries):
        chunk = raw_entries[i * entry_size : (i + 1) * entry_size]
        if not is_bigtiff:
            tag, ftype, count, val_or_offset = struct.unpack(f"{endian}HHI4s", chunk)
        else:
            tag, ftype, count, val_or_offset = struct.unpack(f"{endian}HHQ8s", chunk)

        val: Any = val_or_offset
        if count == 1:
            if ftype == 3:  # SHORT
                val = struct.unpack(f"{endian}H", val_or_offset[:2])[0]
            elif ftype == 4:  # LONG
                val = struct.unpack(f"{endian}I", val_or_offset[:4])[0]
            elif ftype == 16 and is_bigtiff:  # LONG8
                val = struct.unpack(f"{endian}Q", val_or_offset[:8])[0]

        tags[tag] = val

    # 1. Check Dimensions
    width = tags.get(256)
    height = tags.get(257)
    if not (isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0):
        raise RasterSecurityError("Invalid raster dimensions in TIFF header.")

    if width > dim_limit or height > dim_limit:
        raise RasterSecurityError(
            f"Raster dimensions ({width}x{height}) exceed maximum allowed dimension ({dim_limit} px)."
        )

    total_pixels = width * height
    if total_pixels > pixel_limit:
        raise RasterSecurityError(
            f"Raster total pixel count ({total_pixels}) exceeds maximum allowed ({pixel_limit} px)."
        )

    # 2. Bits per sample & samples per pixel
    bits_per_sample = tags.get(258, 8)
    if isinstance(bits_per_sample, (tuple, list)):
        bits_per_sample = bits_per_sample[0]
    elif not isinstance(bits_per_sample, int):
        bits_per_sample = 8

    samples_per_pixel = tags.get(277, 1)
    if not isinstance(samples_per_pixel, int):
        samples_per_pixel = 1

    # 3. Decompression Bomb Guard
    bytes_per_pixel = (bits_per_sample // 8 or 1) * samples_per_pixel
    uncompressed_size = total_pixels * bytes_per_pixel
    compressed_size = len(data)

    if compressed_size > 0:
        ratio = uncompressed_size / compressed_size
        if ratio > ratio_limit and uncompressed_size > 50_000_000:
            raise RasterSecurityError(
                f"Potential decompression bomb: decompression ratio {ratio:.1f}:1 exceeds "
                f"maximum limit of {ratio_limit}:1 (uncompressed {uncompressed_size} bytes)."
            )

    # 4. Georeferencing / CRS
    resolution_m = 20.0
    origin_x = 0.0
    origin_y = 0.0

    # Extract ModelPixelScaleTag (33550) if present
    if 33550 in tags:
        scale_val = tags[33550]
        if isinstance(scale_val, (tuple, list)) and len(scale_val) >= 2:
            resolution_m = float(scale_val[0])
    # Extract ModelTiepointTag (33922) if present
    if 33922 in tags:
        tp = tags[33922]
        if isinstance(tp, (tuple, list)) and len(tp) >= 6:
            origin_x = float(tp[3])
            origin_y = float(tp[4])

    min_x = origin_x
    max_x = origin_x + width * resolution_m
    min_y = origin_y - height * resolution_m
    max_y = origin_y
    bbox = [min_x, min_y, max_x, max_y]

    # Validate CRS (default to Lunar South Pole Stereographic)
    crs_wkt = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT
    assert_lunar_crs(crs_wkt)

    return RasterMetadata(
        width=width,
        height=height,
        bits_per_sample=bits_per_sample,
        samples_per_pixel=samples_per_pixel,
        resolution_m=resolution_m,
        origin_x=origin_x,
        origin_y=origin_y,
        bbox=bbox,
        crs_wkt=crs_wkt,
        driver="GTiff",
    )
