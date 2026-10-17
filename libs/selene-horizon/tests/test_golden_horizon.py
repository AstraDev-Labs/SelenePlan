"""Golden tests for selene-horizon: flat plane, conical peak, and bowl crater."""

import math

import numpy as np
from selene_horizon.horizon import (
    compute_horizon_profile,
    compute_padding_margin_m,
    evaluate_lit_mask,
)


def test_golden_flat_plane() -> None:
    """Golden Test 1: Flat plane must have horizon elevation angle == 0.0 everywhere."""
    # 50x50 cells at 20 m/pixel = 1000m x 1000m flat plane at elevation 0m
    dem = np.full((50, 50), 100.0, dtype=np.float64)
    cell_size_m = 20.0
    azimuth_bins = 36  # every 10 degrees

    horizon, azimuths = compute_horizon_profile(
        dem=dem,
        cell_size_m=cell_size_m,
        azimuth_bins=azimuth_bins,
        max_ray_dist_m=600.0,
    )

    # Flat plane must have 0.0 horizon angle everywhere (curvature only makes horizon negative or zero)
    assert np.all(horizon == 0.0)

    # With Sun above horizon (e.g. +2 degrees), lit everywhere
    lit = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=math.radians(2.0))
    assert np.all(lit)

    # With Sun below horizon (e.g. -1 degree), dark everywhere
    dark = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=math.radians(-1.0))
    assert not np.any(dark)


def test_golden_conical_peak() -> None:
    """Golden Test 2: Conical mountain shadow length and horizon angle match analytic theta = arctan(H/D)."""
    # 101x101 grid, center at (50, 50), peak height 500m, base radius 400m (20 cells at 20m/cell)
    rows, cols = 101, 101
    center_r, center_c = 50, 50
    cell_size_m = 20.0
    h_peak = 500.0
    r_base_m = 400.0

    r_idx, c_idx = np.ogrid[:rows, :cols]
    dist_m = np.sqrt((r_idx - center_r) ** 2 + (c_idx - center_c) ** 2) * cell_size_m
    dem = np.maximum(0.0, h_peak * (1.0 - dist_m / r_base_m))

    azimuth_bins = 72  # every 5 degrees
    horizon, azimuths = compute_horizon_profile(
        dem=dem,
        cell_size_m=cell_size_m,
        azimuth_bins=azimuth_bins,
        max_ray_dist_m=2000.0,
    )

    # Observer outside the cone directly South of the peak (higher row index):
    # center is at (50, 50). Observer at (80, 50) -> dist = 30 cells = 600m
    # Direction toward center is North (azimuth = 0.0 rad)
    obs_r, obs_c = 80, 50
    dist_to_peak = 30 * cell_size_m  # 600m
    analytic_tan = h_peak / dist_to_peak
    analytic_angle = math.atan(analytic_tan)

    # Find the bin corresponding to North (azimuth 0.0)
    north_bin = 0  # azimuths[0] == 0.0

    computed_angle = horizon[obs_r, obs_c, north_bin]
    # Allow small tolerance for discrete ray step / pixel quantization (< 0.03 rad / ~1.5 deg)
    assert math.isclose(computed_angle, analytic_angle, abs_tol=0.03)

    # Illumination check:
    # If Sun is from North at elevation slightly below analytic peak angle, observer is shadowed!
    sun_el_dark = analytic_angle - 0.05
    lit_dark = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=sun_el_dark)
    assert not lit_dark[obs_r, obs_c]

    # If Sun is from North at elevation above analytic peak angle, observer is lit!
    sun_el_lit = analytic_angle + 0.05
    lit_bright = evaluate_lit_mask(horizon, azimuths, sun_az_rad=0.0, sun_el_rad=sun_el_lit)
    assert lit_bright[obs_r, obs_c]


def test_golden_bowl_crater() -> None:
    """Golden Test 3: Bowl crater floor horizon matches analytic rim angle in all azimuths."""
    # 101x101 grid, center at (50, 50), depth 300m, rim radius 500m (25 cells at 20m/cell)
    rows, cols = 101, 101
    center_r, center_c = 50, 50
    cell_size_m = 20.0
    depth_m = 300.0
    r_rim_m = 500.0

    r_idx, c_idx = np.ogrid[:rows, :cols]
    dist_m = np.sqrt((r_idx - center_r) ** 2 + (c_idx - center_c) ** 2) * cell_size_m

    # Parabolic crater: floor at -depth_m, rim at 0.0m
    dem = np.where(dist_m < r_rim_m, -depth_m * (1.0 - (dist_m / r_rim_m) ** 2), 0.0)

    azimuth_bins = 36
    horizon, azimuths = compute_horizon_profile(
        dem=dem,
        cell_size_m=cell_size_m,
        azimuth_bins=azimuth_bins,
        max_ray_dist_m=1000.0,
    )

    # At crater floor center (50, 50): rim is at distance r_rim_m (500m) with height diff depth_m (300m)
    # Rim elevation angle: arctan(300 / 500) = arctan(0.6) = ~30.96 deg
    expected_rim_angle = math.atan(depth_m / r_rim_m)

    floor_horizons = horizon[center_r, center_c, :]
    for b in range(azimuth_bins):
        # All azimuths should see the rim at approximately expected_rim_angle
        assert math.isclose(floor_horizons[b], expected_rim_angle, abs_tol=0.04)

    # Floor is dark when Sun elevation < rim angle, lit when Sun elevation > rim angle
    lit_floor_dark = evaluate_lit_mask(horizon, azimuths, 0.0, expected_rim_angle - 0.05)
    assert not lit_floor_dark[center_r, center_c]

    lit_floor_lit = evaluate_lit_mask(horizon, azimuths, 0.0, expected_rim_angle + 0.05)
    assert lit_floor_lit[center_r, center_c]


def test_compute_padding_margin() -> None:
    """Verify padding reach calculation from relief and minimum sun elevation."""
    # 2000 m relief at 1.5 deg minimum elevation:
    # 2000 / tan(1.5 deg) ~ 76,375 metres
    pad = compute_padding_margin_m(max_relief_m=2000.0, min_elevation_deg=1.5)
    assert 75_000.0 < pad < 78_000.0
