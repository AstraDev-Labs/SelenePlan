"""Unit tests for COG conversion, overview generation, and manifest structure."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image
from selene_geo.cog import validate_cog_bytes

from ingestion_service.cog.converter import COGConverter
from ingestion_service.validation.raster_validator import RasterMetadata


def _create_synthetic_geotiff(width: int = 512, height: int = 512) -> bytes:
    """Create a minimal synthetic GeoTIFF byte buffer for conversion testing."""
    arr = (np.arange(width * height, dtype=np.float32) % 255).reshape(height, width)
    buf = io.BytesIO()
    img = Image.fromarray(arr)
    img.save(buf, format="TIFF")
    return buf.getvalue()


def test_cog_converter_generates_valid_tiled_cog() -> None:
    """Verify COGConverter produces internally tiled TIFF with overviews and valid manifest."""
    raw_tiff = _create_synthetic_geotiff(width=512, height=512)
    meta = RasterMetadata(
        width=512,
        height=512,
        bits_per_sample=32,
        samples_per_pixel=1,
        resolution_m=20.0,
        origin_x=0.0,
        origin_y=0.0,
        bbox=[0.0, -10240.0, 10240.0, 0.0],
        crs_wkt="Lunar_South_Pole_Stereographic",
    )

    converter = COGConverter(tile_size=256)
    result = converter.convert_to_cog(
        raw_raster_bytes=raw_tiff,
        meta=meta,
        dataset_id="00000000-0000-0000-0000-000000000001",
        version=1,
        source_name="lola-dem",
        source_url="https://pds-geosciences.wustl.edu/lro/data.tif",
        source_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        license_text="NASA Open Data",
        terms_note="Scientific use only",
    )

    # 1. Output must pass selene-geo COG validator
    validation = validate_cog_bytes(result.cog_bytes)
    assert validation.is_valid is True
    assert validation.is_tiled is True
    assert validation.tile_width == 256
    assert validation.tile_height == 256
    assert validation.overview_count >= 1

    # 2. Check manifest completeness per SPEC.md
    manifest = result.manifest
    assert manifest["dataset_id"] == "00000000-0000-0000-0000-000000000001"
    assert manifest["version"] == 1
    assert manifest["cog"] is True
    assert manifest["driver"] == "GTiff"
    assert manifest["resolution_m"] == 20.0
    assert manifest["bbox"] == [0.0, -10240.0, 10240.0, 0.0]
    assert manifest["output_sha256"] == result.output_sha256
    assert (
        manifest["source_sha256"]
        == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )
    assert "tool_versions" in manifest
    assert "service" in manifest["tool_versions"]
