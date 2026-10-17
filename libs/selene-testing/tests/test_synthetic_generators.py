"""Unit and golden tests for synthetic terrain generators."""

import math

import numpy as np
import pytest

from selene_testing import (
    add_seeded_noise,
    make_bowl_crater,
    make_cone,
    make_flat_plane,
    make_inclined_plane,
    make_ridge,
)


def test_flat_plane_analytic_properties() -> None:
    """Golden test: Flat plane has 0 slope and constant elevation everywhere."""
    plane = make_flat_plane(shape=(50, 50), resolution_m=20.0, elevation_m=-1234.5)
    assert plane.shape == (50, 50)
    assert plane.resolution_m == 20.0
    assert np.all(plane.elevation == -1234.5)
    assert plane.metadata["analytic_slope_deg"] == 0.0

    # Finite difference gradients must be identically zero
    grad_y, grad_x = np.gradient(plane.elevation, 20.0)
    np.testing.assert_allclose(grad_x, 0.0, atol=1e-12)
    np.testing.assert_allclose(grad_y, 0.0, atol=1e-12)


@pytest.mark.parametrize("slope_deg", [5.0, 10.0, 15.0, 25.0])
@pytest.mark.parametrize("aspect_deg", [0.0, 90.0, 180.0, 270.0, 45.0])
def test_inclined_plane_exact_gradients(slope_deg: float, aspect_deg: float) -> None:
    """Golden test: Inclined plane has analytic slope matching arctan(sqrt(p^2 + q^2))."""
    res = 10.0
    plane = make_inclined_plane(
        shape=(60, 60),
        resolution_m=res,
        slope_deg=slope_deg,
        aspect_deg=aspect_deg,
        base_elevation_m=500.0,
    )

    # Compute central difference gradient on interior cells
    # Note: row index increases downwards (-Northing), col index increases rightwards (+Easting)
    # np.gradient along axis 0 (rows) computes dz / drow.
    # Since dy = -drow * res, dz/dy = -(dz/drow) / res
    dz_drow, dz_dcol = np.gradient(plane.elevation, edge_order=2)
    dz_dx = dz_dcol / res
    dz_dy = -dz_drow / res

    # Interior region (exclude boundary cells for exact central difference)
    interior_x = dz_dx[2:-2, 2:-2]
    interior_y = dz_dy[2:-2, 2:-2]

    grad_mag = np.sqrt(interior_x**2 + interior_y**2)
    computed_slope_deg = np.degrees(np.arctan(grad_mag))

    # Must match the requested slope within 1e-5 degrees on the linear surface
    np.testing.assert_allclose(computed_slope_deg, slope_deg, atol=1e-5)

    # Check aspect azimuth for non-zero slopes
    # Aspect angle clockwise from North: azimuth = arctan2(dx, dy)
    computed_aspect_rad = np.arctan2(interior_x, interior_y)
    computed_aspect_deg = (np.degrees(computed_aspect_rad) + 360.0) % 360.0
    expected_aspect = aspect_deg % 360.0

    np.testing.assert_allclose(computed_aspect_deg, expected_aspect, atol=1e-4)


def test_cone_analytic_properties() -> None:
    """Golden test: Conical mountain flank slope matches arctan(H / R)."""
    res = 5.0
    radius_m = 200.0
    height_m = 50.0
    cone = make_cone(shape=(101, 101), resolution_m=res, radius_m=radius_m, height_m=height_m)

    expected_flank_slope_deg = math.degrees(
        math.atan(height_m / radius_m)
    )  # atan(50/200) = ~14.036 deg
    assert math.isclose(cone.metadata["analytic_flank_slope_deg"], expected_flank_slope_deg)

    # Peak elevation
    center_r, center_c = int(cone.metadata["center_row"]), int(cone.metadata["center_col"])
    assert math.isclose(cone.elevation[center_r, center_c], height_m)

    # Outside radius, elevation must be 0
    # Corner (0, 0): dist = sqrt(50^2 + 50^2) * 5 = 70.7 * 5 = 353 m > 200 m
    assert cone.elevation[0, 0] == 0.0

    # Along horizontal radial transect from center: check flank slope
    # Sample between r = 40m and r = 160m (away from peak singularity and base transition)
    cols = np.arange(center_c + 8, center_c + 32)
    elev_transect = cone.elevation[center_r, cols]
    dx = (cols - cols[0]) * res
    dz = elev_transect[0] - elev_transect
    slope_measured_deg = math.degrees(math.atan(np.mean(dz[1:] / dx[1:])))
    assert math.isclose(slope_measured_deg, expected_flank_slope_deg, abs_tol=0.01)


def test_bowl_crater_analytic_properties() -> None:
    """Golden test: Bowl crater has correct rim crest and floor depth."""
    res = 10.0
    radius = 300.0
    depth = 60.0
    rim_h = 15.0
    base_elev = 100.0
    crater = make_bowl_crater(
        shape=(101, 101),
        resolution_m=res,
        radius_m=radius,
        depth_m=depth,
        rim_height_m=rim_h,
        base_elevation_m=base_elev,
    )

    c_r = int(crater.shape[0] // 2)
    c_c = int(crater.shape[1] // 2)

    # Floor at center
    expected_floor = base_elev + rim_h - depth  # 100 + 15 - 60 = 55.0
    assert math.isclose(crater.elevation[c_r, c_c], expected_floor, abs_tol=1e-3)

    # Rim crest at distance radius = 300m (30 pixels from center)
    rim_pixel = c_c + 30
    expected_rim = base_elev + rim_h  # 100 + 15 = 115.0
    assert math.isclose(crater.elevation[c_r, rim_pixel], expected_rim, abs_tol=1e-3)

    # Far exterior decays toward base_elevation_m
    assert crater.elevation[0, 0] > base_elev
    assert crater.elevation[0, 0] < base_elev + 2.0


def test_ridge_analytic_properties() -> None:
    """Verify linear ridge geometry along azimuth."""
    ridge = make_ridge(
        shape=(101, 101),
        resolution_m=10.0,
        length_m=500.0,
        width_m=100.0,
        height_m=40.0,
        azimuth_deg=0.0,  # North-South ridge
        base_elevation_m=200.0,
    )
    c_r, c_c = 50, 50
    # Peak on ridge crest
    assert math.isclose(ridge.elevation[c_r, c_c], 240.0)

    # Far off across ridge (East-West): elevation is base_elevation_m
    assert math.isclose(ridge.elevation[c_r, 0], 200.0)


def test_add_seeded_noise_determinism() -> None:
    """Verify seeded noise is reproducible and strictly bounded."""
    plane = make_flat_plane(shape=(40, 40), resolution_m=10.0, elevation_m=0.0)
    noise_1 = add_seeded_noise(plane, seed=123, amplitude_m=2.0)
    noise_2 = add_seeded_noise(plane, seed=123, amplitude_m=2.0)
    noise_different = add_seeded_noise(plane, seed=999, amplitude_m=2.0)

    # Identical seed -> bitwise identical elevation arrays
    np.testing.assert_array_equal(noise_1.elevation, noise_2.elevation)

    # Different seed -> distinct arrays
    assert not np.array_equal(noise_1.elevation, noise_different.elevation)

    # Noise standard deviation should be close to amplitude
    assert 1.7 < np.std(noise_1.elevation) < 2.3


def test_synthetic_raster_properties_and_coords() -> None:
    """Verify SyntheticRaster properties, geotransform, and coordinate generation."""
    r = make_flat_plane(shape=(20, 30), resolution_m=5.0, origin=(100.0, 200.0))
    assert r.height == 20
    assert r.width == 30
    assert r.shape == (20, 30)
    assert r.geotransform == (100.0, 5.0, 0.0, 200.0, 0.0, -5.0)

    x1d = r.x_coords_1d()
    assert len(x1d) == 30
    assert math.isclose(x1d[0], 102.5)  # origin_x + 0.5 * res

    y1d = r.y_coords_1d()
    assert len(y1d) == 20
    assert math.isclose(y1d[0], 197.5)  # origin_y - 0.5 * res

    xx, yy = r.xy_mesh()
    assert xx.shape == (20, 30)
    assert yy.shape == (20, 30)


def test_generator_validation_errors() -> None:
    """Verify ValueError is raised on invalid geometric parameters."""
    with pytest.raises(ValueError, match="Slope must be between 0 and 90"):
        make_inclined_plane(slope_deg=-5.0)

    with pytest.raises(ValueError, match="Slope must be between 0 and 90"):
        make_inclined_plane(slope_deg=90.0)

    with pytest.raises(ValueError, match="Cone radius and height must be positive"):
        make_cone(radius_m=-10.0, height_m=50.0)

    with pytest.raises(ValueError, match="Crater radius and depth must be positive"):
        make_bowl_crater(radius_m=100.0, depth_m=-20.0)
