# selene-geo

SelenePlan geospatial library implementing planetary constants, lunar Coordinate Reference Systems (CRS), raster tiling with halo support, and Cloud Optimized GeoTIFF (COG) validation.

## Features

- **Lunar Reference Sphere:** Implements the IAU lunar reference sphere radius ($R = 1,737,400.0\text{ m}$) per `docs/08-science-notes.md`. Never relies on Earth datums.
- **Lunar CRS & Scale Distortion:**
  - Standard WKT1 and PROJ.4 definitions for Lunar South Polar Stereographic (`+lat_0=-90`).
  - Validation routines (`is_lunar_crs`, `assert_lunar_crs`) that strictly reject Earth coordinate systems (WGS 84, EPSG:4326, EPSG:3857).
  - Point scale distortion calculator for polar stereographic projections:
    $$k(\phi) = \frac{1 + \sin(|\phi_{\text{ts}}|)}{1 + \sin(|\phi|)}$$
- **Raster Tiling with Halos:**
  - `generate_tile_windows()` partitions large rasters into tiles with configurable halo overlap padding.
  - `extract_tile_with_halo()` handles edge boundary padding (`edge`, `constant`, `reflect`).
  - `assemble_tiles()` stitches computed cores back into full rasters with zero edge seams.
- **COG Validation:** Pure-Python TIFF/BigTIFF parser verifying internal tiling, overviews, and IFD placement.

## Usage

```python
from selene_geo import (
    MOON_RADIUS_M,
    LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    assert_lunar_crs,
    generate_tile_windows,
    extract_tile_with_halo,
    assemble_tiles,
    validate_cog_bytes,
)

# 1. Assert lunar CRS
assert_lunar_crs(LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT)

# 2. Iterate tiles with 1-pixel halo
for window in generate_tile_windows(full_width=1000, full_height=1000, tile_size=256, halo=1):
    tile = extract_tile_with_halo(dem, window, pad_mode="edge")
    # Process tile (e.g., Horn slope) ...

# 3. Validate a COG
result = validate_cog_bytes(Path("elevation_cog.tif"))
assert result.is_valid and result.is_tiled
```
