"""Hazard fusion module combining physical terrain hazards with ML detections."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.ndimage import zoom


@dataclass
class FusedHazardResult:
    fused_mask: np.ndarray  # [H, W] bool array: True = hazardous
    terrain_mask_resampled: np.ndarray
    ml_mask_resampled: np.ndarray
    params: dict[str, Any]
    stats: dict[str, Any]


def conservative_max_pool_resample(
    grid: np.ndarray,
    target_shape: tuple[int, int],
) -> np.ndarray:
    """Resample grid to target shape using conservative max-pooling so hazards are never diluted."""
    src_h, src_w = grid.shape
    tgt_h, tgt_w = target_shape
    if (src_h, src_w) == (tgt_h, tgt_w):
        return grid.copy()

    # Determine scaling factors
    zoom_y = tgt_h / src_h
    zoom_x = tgt_w / src_w

    # Order 0 (nearest neighbor) with morphological max dilation
    resampled = zoom(grid.astype(np.float32), (zoom_y, zoom_x), order=0)

    # Clip to exact target dimensions
    out = np.zeros(target_shape, dtype=grid.dtype)
    h_min = min(tgt_h, resampled.shape[0])
    w_min = min(tgt_w, resampled.shape[1])
    out[:h_min, :w_min] = (
        (resampled[:h_min, :w_min] > 0.5) if grid.dtype == bool else resampled[:h_min, :w_min]
    )
    return out


def fuse_hazards(
    terrain_hazard: np.ndarray,
    ml_hazard_confidence: np.ndarray,
    ml_confidence_threshold: float = 0.60,
    terrain_product_id: str = "terrain-prod-001",
    ml_product_id: str = "ml-prod-001",
    model_id: str = "crater_detector_v1",
    model_sha256: str = "unknown",
) -> FusedHazardResult:
    """Combine physical terrain hazard and ML confidence hazard raster into a unified hazard product.

    Fusion Rule (FR-13):
        fused_hazard = terrain_hazard OR (ml_confidence >= ml_confidence_threshold)
    """
    assert 0.0 <= ml_confidence_threshold <= 1.0, "Confidence threshold must be within [0.0, 1.0]"

    # Common grid shape (defaults to terrain resolution)
    common_shape = terrain_hazard.shape[:2]

    # Resample ML raster if shapes differ
    if ml_hazard_confidence.shape[:2] != common_shape:
        ml_resampled = conservative_max_pool_resample(ml_hazard_confidence, common_shape)
    else:
        ml_resampled = ml_hazard_confidence.copy()

    # Resample terrain raster if boolean conversion needed
    terrain_bool = terrain_hazard.astype(bool)

    # Apply ML threshold
    ml_bool = ml_resampled >= ml_confidence_threshold

    # Boolean Fusion: OR logic
    fused_bool = terrain_bool | ml_bool

    # Calculate statistics
    total_cells = int(fused_bool.size)
    terrain_cells = int(np.sum(terrain_bool))
    ml_cells = int(np.sum(ml_bool))
    overlap_cells = int(np.sum(terrain_bool & ml_bool))
    fused_cells = int(np.sum(fused_bool))

    params = {
        "ml_confidence_threshold": float(ml_confidence_threshold),
        "resampling_policy": "conservative_max_pool",
        "terrain_product_id": terrain_product_id,
        "ml_product_id": ml_product_id,
        "model_id": model_id,
        "model_sha256": model_sha256,
        "fusion_rule": "terrain_hazard OR (ml_confidence >= threshold)",
    }

    stats = {
        "total_cells": total_cells,
        "terrain_hazard_cells": terrain_cells,
        "ml_hazard_cells": ml_cells,
        "overlap_cells": overlap_cells,
        "fused_hazard_cells": fused_cells,
        "fused_hazard_fraction": float(fused_cells / max(1, total_cells)),
    }

    return FusedHazardResult(
        fused_mask=fused_bool,
        terrain_mask_resampled=terrain_bool,
        ml_mask_resampled=ml_bool,
        params=params,
        stats=stats,
    )
