"""Property tests for terrain-service algorithms: invariant symmetries.

1. Constant offset invariance: Adding a uniform elevation delta C to a DEM
   must produce identical slope, aspect, roughness, and hazard products.
2. 90-degree rotation invariance:
   Rotating a DEM by 90 degrees must rotate the resulting slope and roughness
   arrays by the same 90 degrees.
"""

import numpy as np
import pytest
from selene_testing.synthetic import make_bowl_crater
from terrain_service.algorithms.aspect import compute_aspect_horn
from terrain_service.algorithms.hazard import compute_terrain_hazard
from terrain_service.algorithms.roughness import compute_roughness_tri
from terrain_service.algorithms.slope import compute_slope_horn


@pytest.mark.parametrize("offset_m", [-1000.0, 50.0, 3456.78])
def test_constant_offset_invariance(offset_m: float) -> None:
    """Adding uniform elevation offset should not alter slope, roughness, or hazard."""
    res_m = 20.0
    base_dem = make_bowl_crater(
        shape=(128, 128),
        radius_m=600.0,
        depth_m=120.0,
        rim_height_m=20.0,
        resolution_m=res_m,
    ).elevation
    shifted_dem = base_dem + float(offset_m)

    slope1 = compute_slope_horn(base_dem, resolution_m=res_m)
    slope2 = compute_slope_horn(shifted_dem, resolution_m=res_m)
    np.testing.assert_allclose(slope1, slope2, atol=1e-5)

    rough1 = compute_roughness_tri(base_dem)
    rough2 = compute_roughness_tri(shifted_dem)
    np.testing.assert_allclose(rough1, rough2, atol=1e-5)

    aspect1 = compute_aspect_horn(base_dem, resolution_m=res_m)
    aspect2 = compute_aspect_horn(shifted_dem, resolution_m=res_m)
    np.testing.assert_allclose(aspect1, aspect2, atol=1e-3)

    hazard1 = compute_terrain_hazard(slope1, rough1, max_slope_deg=12.0, max_roughness=0.3)
    hazard2 = compute_terrain_hazard(slope2, rough2, max_slope_deg=12.0, max_roughness=0.3)
    np.testing.assert_array_equal(hazard1, hazard2)


def test_90_degree_rotation_invariance() -> None:
    """Rotating DEM by 90 degrees counter-clockwise rotates slope and roughness by 90 degrees."""
    res_m = 20.0
    dem = make_bowl_crater(
        shape=(128, 128),
        radius_m=500.0,
        depth_m=150.0,
        rim_height_m=25.0,
        resolution_m=res_m,
    ).elevation

    # Rotate DEM 90 deg counter-clockwise (k=1)
    dem_rot = np.rot90(dem, k=1)

    slope_orig = compute_slope_horn(dem, resolution_m=res_m)
    slope_rot = compute_slope_horn(dem_rot, resolution_m=res_m)

    rough_orig = compute_roughness_tri(dem)
    rough_rot = compute_roughness_tri(dem_rot)

    hazard_orig = compute_terrain_hazard(slope_orig, rough_orig)
    hazard_rot = compute_terrain_hazard(slope_rot, rough_rot)

    # Interior cells after rotating original by 90 deg must match rotated computation
    rotated_slope_orig = np.rot90(slope_orig, k=1)
    rotated_rough_orig = np.rot90(rough_orig, k=1)
    rotated_hazard_orig = np.rot90(hazard_orig, k=1)

    # Comparing interior regions (ignore outermost 1-pixel boundary)
    np.testing.assert_allclose(
        slope_rot[2:-2, 2:-2],
        rotated_slope_orig[2:-2, 2:-2],
        atol=1e-5,
    )
    np.testing.assert_allclose(
        rough_rot[2:-2, 2:-2],
        rotated_rough_orig[2:-2, 2:-2],
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        hazard_rot[2:-2, 2:-2],
        rotated_hazard_orig[2:-2, 2:-2],
    )
