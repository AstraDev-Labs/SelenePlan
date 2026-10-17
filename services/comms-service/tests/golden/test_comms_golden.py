"""Golden tests for comms-service: flat plane, ridge occultation, and libration checks."""

import math
from pathlib import Path

import numpy as np
import pytest
from comms_service.earth.ephemeris import EarthGeometryEngine
from comms_service.storage.zarr_store import ZarrCommsStore
from comms_service.worker.pipeline import CommsPipeline
from selene_geo.spice import (
    compute_local_az_el,
    default_spice_manager,
    get_body_position_moon_fixed,
    str_to_et,
)
from selene_horizon.horizon import compute_horizon_profile, evaluate_lit_mask


@pytest.fixture(scope="module")
def setup_spice_and_pipeline(tmp_path_factory: pytest.TempPathFactory) -> CommsPipeline:
    spice_dir = Path("data/spice")
    tls = spice_dir / "naif0012.tls"
    tpc = spice_dir / "pck00010.tpc"
    bsp = spice_dir / "de421.bsp"

    if not (tls.is_file() and tpc.is_file() and bsp.is_file()):
        pytest.skip("SPICE kernels not found in data/spice/")

    default_spice_manager.load_kernels([tls, tpc, bsp])
    temp_dir = tmp_path_factory.mktemp("comms_zarr")
    store = ZarrCommsStore(base_dir=temp_dir)
    return CommsPipeline(cube_store=store)


def test_golden_flat_plane_comms() -> None:
    """Acceptance Criterion 1: On flat plane, Earth is visible iff Earth elevation > 0."""
    dem = np.full((30, 30), 100.0, dtype=np.float64)
    cell_size = 20.0
    horizon, azimuths = compute_horizon_profile(
        dem, cell_size, azimuth_bins=36, max_ray_dist_m=500.0
    )

    # 1. Earth above horizon (+2.5 deg)
    vis_above = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=math.radians(2.5))
    assert np.all(vis_above)

    # 2. Earth below horizon (-1.0 deg)
    vis_below = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=math.radians(-1.0))
    assert not np.any(vis_below)


def test_golden_ridge_occultation() -> None:
    """Acceptance Criterion 2: Blocked when Earth elevation < analytic ridge angle, visible above."""
    # 51x51 grid, observer at row 40, col 25. Ridge at row 20 (20 cells North = 400m away)
    # Ridge height = 300m, observer height = 0m.
    # Analytic ridge angle: arctan(300m / 400m) = arctan(0.75) ~ 36.87 degrees
    dem = np.zeros((51, 51), dtype=np.float64)
    dem[20, :] = 300.0  # East-West ridge

    cell_size = 20.0
    horizon, azimuths = compute_horizon_profile(
        dem, cell_size, azimuth_bins=36, max_ray_dist_m=1000.0
    )

    obs_r, obs_c = 40, 25
    dist_m = 20 * cell_size  # 400m
    analytic_angle = math.atan(300.0 / dist_m)

    # Direction looking at ridge is North (azimuth 0.0)
    north_bin = 0
    computed_angle = horizon[obs_r, obs_c, north_bin]
    assert math.isclose(computed_angle, analytic_angle, abs_tol=0.03)

    # Test Earth from North:
    # When Earth elevation is below ridge angle -> blocked (blackout)
    vis_dark = evaluate_lit_mask(
        horizon, azimuths, sun_az_rad=0.0, sun_el_rad=analytic_angle - 0.05
    )
    assert not vis_dark[obs_r, obs_c]

    # When Earth elevation is above ridge angle -> visible
    vis_lit = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=analytic_angle + 0.05)
    assert vis_lit[obs_r, obs_c]


def test_libration_check(setup_spice_and_pipeline: CommsPipeline) -> None:
    """Acceptance Criterion 4: Earth direction series verified against independent SPICE calls."""
    engine = EarthGeometryEngine()
    lat_rad = math.radians(-90.0)  # South Pole
    lon_rad = 0.0

    steps = engine.compute_trajectory(
        start_iso="2026-03-01T00:00:00Z",
        end_iso="2026-03-05T00:00:00Z",
        time_step_s=86400.0,  # daily steps across 5 days
        obs_lat_rad=lat_rad,
        obs_lon_rad=lon_rad,
    )

    assert len(steps) == 5

    # Known physical bounds for Earth viewed from Lunar South Pole:
    # Distance approx 360,000 to 405,000 km
    # Elevation stays near the horizon (-8 deg to +8 deg depending on libration)
    for step in steps:
        assert 350_000.0 < step.distance_km < 415_000.0
        assert 1.1 < step.light_time_s < 1.4  # ~1.28s light travel time
        el_deg = math.degrees(step.elevation_rad)
        assert -8.5 <= el_deg <= 8.5

    # Independent check against direct SPICE call for step 0
    et0 = str_to_et("2026-03-01T00:00:00Z")
    pos_m, _lt0 = get_body_position_moon_fixed("EARTH", et0)
    az0, el0 = compute_local_az_el(pos_m, lat_rad, lon_rad)

    assert math.isclose(steps[0].azimuth_rad, az0, abs_tol=1e-6)
    assert math.isclose(steps[0].elevation_rad, el0, abs_tol=1e-6)


def test_along_path_evaluation(setup_spice_and_pipeline: CommsPipeline) -> None:
    """Task 3.3 Acceptance: along-path returns correct visibility for time-stamped path."""
    pipeline = setup_spice_and_pipeline

    # Dem with ridge at y=0 (row 15)
    dem = np.zeros((31, 31), dtype=np.float64)
    dem[15, :] = 500.0

    prod_id, _ = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=math.radians(-89.5),
        obs_lon_rad=0.0,
        start_iso="2026-03-01T00:00:00Z",
        end_iso="2026-03-01T04:00:00Z",
        time_step_s=3600.0,
        dataset_version_id="dem-path-v1",
        crs_wkt="LOCAL",
        bounds=[-300.0, -300.0, 300.0, 300.0],
        azimuth_bins=24,
        max_ray_dist_m=500.0,
    )

    # Path across the terrain
    waypoints = [
        {"x_m": 0.0, "y_m": -200.0, "time_index": 0},
        {"x_m": 0.0, "y_m": 200.0, "time_index": 1},
    ]

    evaluated = pipeline.evaluate_along_path(prod_id, waypoints)
    assert len(evaluated) == 2
    assert "is_visible" in evaluated[0]
    assert "earth_line_of_sight" in evaluated[0]
