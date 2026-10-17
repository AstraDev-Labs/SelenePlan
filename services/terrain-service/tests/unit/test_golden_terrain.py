"""Golden tests for terrain-service algorithms per SPEC.md and science notes.

Validates that:
1. 10.0-degree inclined plane yields 10.0 +/- 0.1 degrees on interior cells.
2. Flat plane yields 0.0 degrees slope and 0.0 m roughness.
3. Aspect matches gradient compass direction.
4. Hazard threshold correctly separates safe vs hazardous terrain.
"""

import numpy as np
import pytest
from selene_testing.synthetic import make_flat_plane, make_inclined_plane
from terrain_service.algorithms.aspect import compute_aspect_horn
from terrain_service.algorithms.hazard import compute_terrain_hazard
from terrain_service.algorithms.roughness import compute_roughness_tri
from terrain_service.algorithms.slope import compute_slope_horn


def test_golden_flat_plane() -> None:
    """A completely flat plane must have 0 slope, 0 roughness, and safe hazard."""
    dem = make_flat_plane(shape=(100, 100), elevation_m=1250.0).elevation.astype(np.float32)
    res_m = 20.0

    slope = compute_slope_horn(dem, resolution_m=res_m)
    roughness = compute_roughness_tri(dem)
    aspect = compute_aspect_horn(dem, resolution_m=res_m)
    hazard = compute_terrain_hazard(slope, roughness, max_slope_deg=15.0, max_roughness=0.35)

    # Interior cells (1:-1, 1:-1)
    interior_slope = slope[1:-1, 1:-1]
    interior_roughness = roughness[1:-1, 1:-1]
    interior_aspect = aspect[1:-1, 1:-1]
    interior_hazard = hazard[1:-1, 1:-1]

    # Slope on flat plane must be strictly 0.0
    np.testing.assert_allclose(interior_slope, 0.0, atol=1e-6)

    # Roughness on flat plane must be strictly 0.0
    np.testing.assert_allclose(interior_roughness, 0.0, atol=1e-6)

    # Aspect on flat plane is conventionally -1.0 (undefined flat)
    np.testing.assert_allclose(interior_aspect, -1.0, atol=1e-6)

    # All interior cells are completely safe (0)
    assert np.all(interior_hazard == 0)


@pytest.mark.parametrize("aspect_deg", [0.0, 45.0, 90.0, 180.0, 270.0])
def test_golden_inclined_plane_10_degrees(aspect_deg: float) -> None:
    """A 10.0 degree inclined plane must produce 10.0 +/- 0.1 deg slope on interior cells."""
    target_slope = 10.0
    res_m = 20.0
    dem = make_inclined_plane(
        shape=(120, 120),
        slope_deg=target_slope,
        aspect_deg=aspect_deg,
        resolution_m=res_m,
        base_elevation_m=500.0,
    ).elevation.astype(np.float32)

    slope = compute_slope_horn(dem, resolution_m=res_m)
    aspect = compute_aspect_horn(dem, resolution_m=res_m)

    interior_slope = slope[5:-5, 5:-5]
    interior_aspect = aspect[5:-5, 5:-5]

    # Slope must be 10.0 deg within 0.1 deg
    np.testing.assert_allclose(interior_slope, target_slope, atol=0.1)

    # Aspect must match aspect_deg within 0.5 degrees
    diff = np.abs(interior_aspect - aspect_deg)
    diff = np.minimum(diff, 360.0 - diff)
    assert np.all(diff < 0.5)


def test_golden_hazard_thresholds() -> None:
    """Hazard mask must flag cells where slope > max_slope or roughness > max_roughness."""
    res_m = 20.0
    # Create plane with 20.0 degrees slope (exceeding default 15.0 deg limit)
    dem_steep = make_inclined_plane(
        shape=(50, 50),
        slope_deg=20.0,
        aspect_deg=90.0,
        resolution_m=res_m,
    ).elevation.astype(np.float32)
    slope_steep = compute_slope_horn(dem_steep, resolution_m=res_m)
    roughness_steep = compute_roughness_tri(dem_steep)

    hazard_steep = compute_terrain_hazard(
        slope_steep,
        roughness_steep,
        max_slope_deg=15.0,
        max_roughness=0.35,
    )
    # Interior must be 100% hazardous
    assert np.all(hazard_steep[1:-1, 1:-1] == 1)

    # Create plane with 8.0 degrees slope (below 15.0 limit) with max_roughness=5.0
    dem_gentle = make_inclined_plane(
        shape=(50, 50),
        slope_deg=8.0,
        aspect_deg=90.0,
        resolution_m=res_m,
    ).elevation.astype(np.float32)
    slope_gentle = compute_slope_horn(dem_gentle, resolution_m=res_m)
    roughness_gentle = compute_roughness_tri(dem_gentle)

    hazard_gentle = compute_terrain_hazard(
        slope_gentle,
        roughness_gentle,
        max_slope_deg=15.0,
        max_roughness=5.0,
    )
    # Interior must be 100% safe
    assert np.all(hazard_gentle[1:-1, 1:-1] == 0)

    # Test roughness threshold specifically
    flat_slope = np.zeros((20, 20), dtype=np.float32)
    rough_excessive = np.full((20, 20), 0.5, dtype=np.float32)
    rough_acceptable = np.full((20, 20), 0.2, dtype=np.float32)

    hazard_rough = compute_terrain_hazard(
        flat_slope, rough_excessive, max_slope_deg=15.0, max_roughness=0.35
    )
    assert np.all(hazard_rough == 1)

    hazard_smooth = compute_terrain_hazard(
        flat_slope, rough_acceptable, max_slope_deg=15.0, max_roughness=0.35
    )
    assert np.all(hazard_smooth == 0)
