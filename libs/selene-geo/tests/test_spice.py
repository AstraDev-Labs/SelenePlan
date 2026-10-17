"""Unit and golden tests for SPICE ephemerides and topocentric coordinate geometry."""

import math
from pathlib import Path

import numpy as np
import pytest

from selene_geo.constants import MOON_RADIUS_M
from selene_geo.spice import (
    compute_local_az_el,
    compute_local_enu_basis,
    compute_sun_trajectory,
    default_spice_manager,
    et_to_str,
    get_body_position_moon_fixed,
    str_to_et,
)


def test_enu_basis_orthonormality() -> None:
    """Verify that local ENU basis vectors are orthonormal and right-handed everywhere."""
    test_coords = [
        (-math.pi / 2, 0.0),  # South Pole
        (-math.pi / 2 + 0.05, math.pi / 4),  # Near South Pole
        (-math.pi / 2 + 0.1, -math.pi / 3),  # South polar region
        (0.0, 0.0),  # Equator Prime Meridian
        (0.0, math.pi / 2),  # Equator 90E
        (math.pi / 4, math.pi),  # Northern Mid-latitude
    ]

    for lat, lon in test_coords:
        east, north, up = compute_local_enu_basis(lat, lon)

        # Unit length
        assert math.isclose(np.linalg.norm(east), 1.0, abs_tol=1e-12)
        assert math.isclose(np.linalg.norm(north), 1.0, abs_tol=1e-12)
        assert math.isclose(np.linalg.norm(up), 1.0, abs_tol=1e-12)

        # Mutually orthogonal
        assert math.isclose(np.dot(east, north), 0.0, abs_tol=1e-12)
        assert math.isclose(np.dot(east, up), 0.0, abs_tol=1e-12)
        assert math.isclose(np.dot(north, up), 0.0, abs_tol=1e-12)

        # Right-handed coordinate system: East x North == Up
        cross_en = np.cross(east, north)
        assert np.allclose(cross_en, up, atol=1e-12)


def test_local_az_el_analytic_cardinal_directions() -> None:
    """Verify azimuth and elevation against analytic cardinal targets at the equator."""
    lat = 0.0
    lon = 0.0
    r = MOON_RADIUS_M
    p_obs = np.array([r, 0.0, 0.0])

    # Target straight up (+X)
    target_up = p_obs + np.array([1000.0, 0.0, 0.0])
    az, el = compute_local_az_el(target_up, lat, lon)
    assert math.isclose(math.degrees(el), 90.0, abs_tol=1e-6)

    # Target North (+Z)
    target_north = p_obs + np.array([0.0, 0.0, 1000.0])
    az, el = compute_local_az_el(target_north, lat, lon)
    assert math.isclose(math.degrees(az), 0.0, abs_tol=1e-6)
    assert math.isclose(math.degrees(el), 0.0, abs_tol=1e-6)

    # Target East (+Y)
    target_east = p_obs + np.array([0.0, 1000.0, 0.0])
    az, el = compute_local_az_el(target_east, lat, lon)
    assert math.isclose(math.degrees(az), 90.0, abs_tol=1e-6)
    assert math.isclose(math.degrees(el), 0.0, abs_tol=1e-6)

    # Target South (-Z)
    target_south = p_obs + np.array([0.0, 0.0, -1000.0])
    az, el = compute_local_az_el(target_south, lat, lon)
    assert math.isclose(math.degrees(az), 180.0, abs_tol=1e-6)
    assert math.isclose(math.degrees(el), 0.0, abs_tol=1e-6)

    # Target West (-Y)
    target_west = p_obs + np.array([0.0, -1000.0, 0.0])
    az, el = compute_local_az_el(target_west, lat, lon)
    assert math.isclose(math.degrees(az), 270.0, abs_tol=1e-6)
    assert math.isclose(math.degrees(el), 0.0, abs_tol=1e-6)


@pytest.fixture(scope="module")
def spice_kernels_loaded() -> bool:
    """Load SPICE kernels if available in data/spice/."""
    spice_dir = Path("data/spice")
    tls = spice_dir / "naif0012.tls"
    tpc = spice_dir / "pck00010.tpc"
    bsp = spice_dir / "de421.bsp"

    if tls.is_file() and tpc.is_file() and bsp.is_file():
        default_spice_manager.load_kernels([tls, tpc, bsp])
        return True
    return False


def test_spice_sun_ephemeris(spice_kernels_loaded: bool) -> None:
    """Golden test: verify SPICE Sun position and distance against known astronomical values."""
    if not spice_kernels_loaded:
        pytest.skip("SPICE kernels not downloaded in data/spice/")

    # Epoch 2026-03-01T12:00:00Z
    utc = "2026-03-01T12:00:00Z"
    et = str_to_et(utc)
    assert math.isclose(et, 825638469.185, abs_tol=1.0)

    # Sun position in Moon-fixed frame IAU_MOON
    sun_pos_m, lt = get_body_position_moon_fixed("SUN", et)
    dist_m = float(np.linalg.norm(sun_pos_m))

    # Sun distance should be approx 1 AU (1.47e11 to 1.52e11 metres)
    assert 1.47e11 < dist_m < 1.52e11
    # Light-time approx 490 - 510 seconds (~8.3 minutes)
    assert 490.0 < lt < 510.0

    # Verify time round-trip conversion
    utc_back = et_to_str(et)
    assert "2026-03-01" in utc_back


def test_spice_known_answer_south_pole(spice_kernels_loaded: bool) -> None:
    """Golden test: Known-answer Sun elevation at South Pole near equinox."""
    if not spice_kernels_loaded:
        pytest.skip("SPICE kernels not downloaded in data/spice/")

    # South Pole latitude -90 deg
    lat_rad = math.radians(-90.0)
    lon_rad = 0.0

    ets, _azs, els = compute_sun_trajectory(
        start_iso="2026-03-01T00:00:00Z",
        end_iso="2026-03-01T12:00:00Z",
        step_seconds=3600.0 * 2.0,  # every 2 hours
        lat_rad=lat_rad,
        lon_rad=lon_rad,
    )

    assert len(ets) == 7
    # Near equinox at south pole, Sun elevation should be within +/- 1.6 degrees of horizon
    for el in els:
        el_deg = math.degrees(el)
        assert -1.6 <= el_deg <= 1.6
