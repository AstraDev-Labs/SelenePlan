"""Unit tests for hazard fusion logic, truth tables, and conservative resampling (FR-13)."""

import numpy as np
from hazard_ml_service.fusion.fuser import fuse_hazards, conservative_max_pool_resample


def test_fusion_truth_table() -> None:
    # 2x2 grid testing all 4 truth combinations
    # [ [ (F, F), (T, F) ],
    #   [ (F, T), (T, T) ] ]
    terrain = np.array([[False, True], [False, True]], dtype=bool)
    ml_conf = np.array([[0.20, 0.20], [0.85, 0.85]], dtype=np.float32)

    result = fuse_hazards(
        terrain_hazard=terrain,
        ml_hazard_confidence=ml_conf,
        ml_confidence_threshold=0.60,
        terrain_product_id="terrain-t1",
        ml_product_id="ml-t1",
        model_id="crater_detector_v1",
        model_sha256="abc123sha",
    )

    fused = result.fused_mask
    assert fused[0, 0] is False or fused[0, 0] == 0  # F or F = F
    assert fused[0, 1] is True or fused[0, 1] == 1  # T or F = T
    assert fused[1, 0] is True or fused[1, 0] == 1  # F or T = T
    assert fused[1, 1] is True or fused[1, 1] == 1  # T or T = T

    # Check stats
    assert result.stats["total_cells"] == 4
    assert result.stats["fused_hazard_cells"] == 3
    assert result.stats["overlap_cells"] == 1
    assert result.stats["fused_hazard_fraction"] == 0.75

    # Check lineage parameters
    assert result.params["terrain_product_id"] == "terrain-t1"
    assert result.params["ml_product_id"] == "ml-t1"
    assert result.params["model_id"] == "crater_detector_v1"
    assert result.params["model_sha256"] == "abc123sha"


def test_conservative_max_pool_resample() -> None:
    # Small 2x2 grid with a single isolated hazard point
    small = np.array([[False, False], [False, True]], dtype=bool)
    # Resample up to 4x4
    upsampled = conservative_max_pool_resample(small, (4, 4))
    assert upsampled.shape == (4, 4)
    # The hazard must NOT be erased by resampling
    assert np.any(upsampled)
    assert np.sum(upsampled) >= 1
