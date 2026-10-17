"""Component tests for tile seams and no-data propagation in terrain processing."""

import numpy as np
from selene_testing.synthetic import make_bowl_crater
from terrain_service.algorithms.aspect import compute_aspect_horn
from terrain_service.algorithms.hazard import compute_terrain_hazard
from terrain_service.algorithms.roughness import compute_roughness_tri
from terrain_service.algorithms.slope import compute_slope_horn
from terrain_service.algorithms.tiled_processor import TiledTerrainProcessor


def test_tile_processing_seam_free() -> None:
    """Tiled execution with halo=1 must produce identical output to monolithic execution.

    Verifies across multiple tile boundaries (tile_size=64 on a 192x192 DEM).
    """
    res_m = 20.0
    dem = make_bowl_crater(
        shape=(192, 192),
        radius_m=800.0,
        depth_m=200.0,
        resolution_m=res_m,
    ).elevation.astype(np.float32)

    processor = TiledTerrainProcessor(
        tile_size=64,
        halo=1,
        max_slope_deg=15.0,
        max_roughness=0.35,
    )
    tiled_res = processor.process(dem, resolution_m=res_m)

    # Monolithic ground truth
    mono_slope = compute_slope_horn(dem, resolution_m=res_m)
    mono_aspect = compute_aspect_horn(dem, resolution_m=res_m)
    mono_rough = compute_roughness_tri(dem)
    mono_hazard = compute_terrain_hazard(mono_slope, mono_rough)

    # Compare interior cells (since outermost border has boundary handling)
    np.testing.assert_allclose(tiled_res.slope_deg[1:-1, 1:-1], mono_slope[1:-1, 1:-1], atol=1e-6)
    np.testing.assert_allclose(tiled_res.aspect_deg[1:-1, 1:-1], mono_aspect[1:-1, 1:-1], atol=1e-4)
    np.testing.assert_allclose(tiled_res.roughness[1:-1, 1:-1], mono_rough[1:-1, 1:-1], atol=1e-6)
    np.testing.assert_array_equal(tiled_res.hazard_mask[1:-1, 1:-1], mono_hazard[1:-1, 1:-1])


def test_nodata_propagation_and_fail_closed_hazard() -> None:
    """No-data cells (NaN) must propagate to 3x3 neighborhood and be marked hazardous."""
    res_m = 20.0
    dem = np.full((30, 30), 100.0, dtype=np.float32)

    # Inject single no-data pixel at (15, 15)
    dem[15, 15] = np.nan

    slope = compute_slope_horn(dem, resolution_m=res_m)
    rough = compute_roughness_tri(dem)
    aspect = compute_aspect_horn(dem, resolution_m=res_m)

    # All cells in the 3x3 window around (15, 15) must be NaN
    window_slope = slope[14:17, 14:17]
    assert np.all(np.isnan(window_slope))

    window_rough = rough[14:17, 14:17]
    assert np.all(np.isnan(window_rough))

    window_aspect = aspect[14:17, 14:17]
    assert np.all(np.isnan(window_aspect))

    # Cells outside the 3x3 window remain valid (0.0 slope on flat plane)
    assert not np.isnan(slope[10, 10])
    assert slope[10, 10] == 0.0

    # Fail-closed hazard evaluation (nodata_is_hazard=True)
    hazard_fail_closed = compute_terrain_hazard(slope, rough, nodata_is_hazard=True)
    # The NaN window must be marked hazardous (1)
    assert np.all(hazard_fail_closed[14:17, 14:17] == 1)
    # Valid flat cells are safe (0)
    assert hazard_fail_closed[10, 10] == 0

    # Test open policy (nodata_is_hazard=False)
    hazard_open = compute_terrain_hazard(slope, rough, nodata_is_hazard=False)
    assert np.all(hazard_open[14:17, 14:17] == 0)
