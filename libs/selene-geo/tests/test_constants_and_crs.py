"""Unit tests for lunar constants and CRS validations."""

import math

import pytest

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


def test_moon_constants() -> None:
    """Verify physical constants conform to IAU/NASA standards."""
    assert MOON_RADIUS_M == 1_737_400.0  # Exactly 1737.4 km
    assert MOON_GRAVITY_M_S2 == 1.62
    assert SOLAR_CONSTANT_1AU_W_M2 == 1361.0


def test_unit_conversions() -> None:
    """Verify SI unit conversion helpers."""
    assert math.isclose(deg_to_rad(180.0), math.pi)
    assert math.isclose(rad_to_deg(math.pi / 2), 90.0)
    assert m_to_km(1737400.0) == 1737.4
    assert km_to_m(1.7374) == 1737.4


def test_lunar_crs_wkt_and_proj() -> None:
    """Verify standard Lunar South Pole Stereographic definitions."""
    assert "Moon" in LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT
    assert "1737400" in LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT
    assert "Polar_Stereographic" in LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT
    assert is_lunar_crs(LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT) is True
    assert is_lunar_crs(LUNAR_SOUTH_POLE_STEREOGRAPHIC_PROJ4) is True
    assert_lunar_crs(LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT)


def test_rejection_of_earth_crs() -> None:
    """Verify that Earth CRS definitions (WGS 84, EPSG:4326, EPSG:3857) are rejected."""
    earth_crss = [
        "EPSG:4326",
        "epsg:3857",
        "WGS 84 / World Mercator",
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]]]',
        "+proj=longlat +datum=WGS84 +no_defs",
        {"init": "epsg:4326"},
    ]
    for earth_crs in earth_crss:
        assert is_lunar_crs(earth_crs) is False
        with pytest.raises(ValueError, match="not an Earth ellipsoid"):
            assert_lunar_crs(earth_crs)


def test_polar_stereographic_scale_factor() -> None:
    """Verify scale distortion calculation for Lunar polar stereographic projection."""
    # At pole (-90 deg), scale factor must be exactly 1.0
    k_90 = polar_stereographic_scale_factor(-90.0)
    assert math.isclose(k_90, 1.0, rel_tol=1e-6)

    # At -80 deg latitude (approx 303 km from pole): ~0.76% stretch
    k_80 = polar_stereographic_scale_factor(-80.0)
    assert 1.007 < k_80 < 1.008

    # At -70 deg latitude (approx 606 km from pole): ~3.11% stretch
    k_70 = polar_stereographic_scale_factor(-70.0)
    assert 1.030 < k_70 < 1.032

    # Scale factor must strictly increase as latitude moves away from the pole
    assert k_90 < k_80 < k_70

    with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
        polar_stereographic_scale_factor(-95.0)

    with pytest.raises(ValueError, match="Latitude of true scale must be between -90 and 90"):
        polar_stereographic_scale_factor(-80.0, lat_ts_deg=-100.0)
