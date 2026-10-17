"""SelenePlan geospatial library: lunar constants, stereographic CRS, raster tiling, and COG validation."""

from selene_geo.cog import COGValidationResult, validate_cog_bytes
from selene_geo.constants import (
    MOON_GRAVITY_M_S2,
    MOON_RADIUS_M,
    SOLAR_CONSTANT_1AU_W_M2,
    deg_to_rad,
    km_to_m,
    m_to_km,
    rad_to_deg,
)
from selene_geo.crs import (
    LUNAR_SOUTH_POLE_STEREOGRAPHIC_PROJ4,
    LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    assert_lunar_crs,
    is_lunar_crs,
    polar_stereographic_scale_factor,
)
from selene_geo.spice import (
    KernelInfo,
    SpiceManager,
    compute_local_az_el,
    compute_local_enu_basis,
    compute_sun_trajectory,
    default_spice_manager,
    et_to_str,
    get_body_position_moon_fixed,
    str_to_et,
)
from selene_geo.tiling import (
    TileWindow,
    assemble_tiles,
    extract_tile_with_halo,
    generate_tile_windows,
)

__all__ = [
    "LUNAR_SOUTH_POLE_STEREOGRAPHIC_PROJ4",
    "LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT",
    "MOON_GRAVITY_M_S2",
    "MOON_RADIUS_M",
    "SOLAR_CONSTANT_1AU_W_M2",
    "COGValidationResult",
    "KernelInfo",
    "SpiceManager",
    "TileWindow",
    "assemble_tiles",
    "assert_lunar_crs",
    "compute_local_az_el",
    "compute_local_enu_basis",
    "compute_sun_trajectory",
    "default_spice_manager",
    "deg_to_rad",
    "et_to_str",
    "extract_tile_with_halo",
    "generate_tile_windows",
    "get_body_position_moon_fixed",
    "is_lunar_crs",
    "km_to_m",
    "m_to_km",
    "polar_stereographic_scale_factor",
    "rad_to_deg",
    "str_to_et",
    "validate_cog_bytes",
]
