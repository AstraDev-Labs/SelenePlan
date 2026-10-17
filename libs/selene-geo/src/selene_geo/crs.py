"""Lunar Coordinate Reference System (CRS) definitions, validation, and scale helpers.

Enforces strict planetary geodesy: The Moon is NOT an Earth ellipsoid (docs/08 Section 1).
All analysis in the south polar region uses explicit Lunar Polar Stereographic projections
anchored to the IAU 1,737.4 km reference sphere. Earth CRS definitions (WGS 84, EPSG:4326,
EPSG:3857) are rejected by default.
"""

from __future__ import annotations

import math
import re
from typing import Any

from selene_geo.constants import MOON_RADIUS_M, deg_to_rad

# Standard WKT1 representation for Lunar South Pole Stereographic projection (metres)
LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT: str = (
    'PROJCS["Moon_South_Pole_Stereographic",'
    'GEOGCS["GCS_Moon_2000",'
    'DATUM["D_Moon_2000",'
    f'SPHEROID["Moon_2000_IAU_IAG",{MOON_RADIUS_M:.1f},0.0]],'
    'PRIMEM["Reference_Meridian",0.0],'
    'UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Polar_Stereographic"],'
    'PARAMETER["latitude_of_origin",-90.0],'
    'PARAMETER["central_meridian",0.0],'
    'PARAMETER["scale_factor",1.0],'
    'PARAMETER["false_easting",0.0],'
    'PARAMETER["false_northing",0.0],'
    'UNIT["metre",1.0]]'
)

# PROJ.4 string for quick transforms and rasterio integration
LUNAR_SOUTH_POLE_STEREOGRAPHIC_PROJ4: str = (
    f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 "
    f"+R={int(MOON_RADIUS_M)} +units=m +no_defs"
)

# Common forbidden Earth identifiers (case-insensitive)
EARTH_CRS_PATTERNS: list[str] = [
    r"wgs\s*84",
    r"wgs_1984",
    r"epsg:4326",
    r"epsg:3857",
    r"grs\s*80",
    r"6378137",  # Earth semi-major axis in metres
    r"6378245",
    r"earth",
]


def is_lunar_crs(crs_input: str | dict[str, Any]) -> bool:
    """Determine whether a CRS definition represents a valid lunar coordinate reference system.

    Rejects Earth datums (WGS 84, GRS 80, EPSG:4326, EPSG:3857, Earth radius ~6378 km)
    and verifies lunar reference parameters (radius 1,737.4 km or Moon identifiers).
    """
    if isinstance(crs_input, dict):
        crs_str = " ".join(f"{k}={v}" for k, v in crs_input.items()).lower()
    else:
        crs_str = str(crs_input).lower()

    # 1. Deny any Earth indicators
    for pattern in EARTH_CRS_PATTERNS:
        if re.search(pattern, crs_str, re.IGNORECASE):
            return False

    # 2. Require Lunar indicators
    lunar_indicators = ["moon", "luna", "1737400", "1737.4", "iau2000:30100", "iau:30100"]
    return any(ind in crs_str for ind in lunar_indicators)


def assert_lunar_crs(crs_input: str | dict[str, Any]) -> None:
    """Raise ValueError if the CRS is an Earth coordinate system or not recognized as lunar."""
    if not is_lunar_crs(crs_input):
        raise ValueError(
            f"Invalid CRS: '{crs_input}' is not a recognized Lunar CRS. "
            "The Moon is not an Earth ellipsoid. Earth datums (e.g. WGS 84, EPSG:4326) are strictly forbidden."
        )


def polar_stereographic_scale_factor(
    latitude_deg: float,
    lat_ts_deg: float = -90.0,
) -> float:
    """Compute local point scale factor k for polar stereographic projection on a spherical body.

    Formula for spherical body with true scale at latitude lat_ts:
        k(phi) = (1 + sin(|lat_ts|)) / (1 + sin(|phi|))

    At the pole (latitude = -90 deg): k = 1.0000 (0% distortion)
    At latitude = -80 deg: k = 1.0076 (0.76% stretch)
    At latitude = -70 deg: k = 1.0311 (3.11% stretch)

    Args:
        latitude_deg: Latitude of interest in degrees (-90 to 0).
        lat_ts_deg: Latitude of true scale in degrees (standard parallel, default -90).

    Returns:
        Scale factor k >= 1.0.
    """
    if not (-90.0 <= latitude_deg <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90 degrees, got {latitude_deg}")
    if not (-90.0 <= lat_ts_deg <= 90.0):
        raise ValueError(
            f"Latitude of true scale must be between -90 and 90 degrees, got {lat_ts_deg}"
        )

    phi_abs = abs(deg_to_rad(latitude_deg))
    phi_ts_abs = abs(deg_to_rad(lat_ts_deg))

    numerator = 1.0 + math.sin(phi_ts_abs)
    denominator = 1.0 + math.sin(phi_abs)

    return numerator / denominator
