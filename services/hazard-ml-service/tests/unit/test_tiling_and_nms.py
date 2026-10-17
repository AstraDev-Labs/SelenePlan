"""Unit tests for overlapping tiling, NMS deduplication, and heatmap stitching."""

import math

import numpy as np
from hazard_ml_service.inference.nms import (
    circle_iou,
    non_maximum_suppression_circles,
)
from hazard_ml_service.inference.tiler import generate_overlapping_tiles, stitch_hazard_heatmap


def test_circle_iou_math() -> None:
    # Identical circles
    iou_identical = circle_iou(10.0, 10.0, 0.0)
    assert math.isclose(iou_identical, 1.0, abs_tol=1e-5)

    # Disjoint circles
    iou_disjoint = circle_iou(10.0, 10.0, 25.0)
    assert math.isclose(iou_disjoint, 0.0, abs_tol=1e-5)

    # Overlapping circles
    iou_overlap = circle_iou(10.0, 10.0, 10.0)
    assert 0.20 < iou_overlap < 0.45


def test_tile_boundary_deduplication() -> None:
    # Two detections of the exact same crater from overlapping adjacent tiles
    raw_detections = [
        {
            "center_x": 222.0,
            "center_y": 100.0,
            "radius_px": 14.0,
            "confidence": 0.88,
            "tile_index": 0,
        },
        {
            "center_x": 224.0,
            "center_y": 101.0,
            "radius_px": 14.0,
            "confidence": 0.81,
            "tile_index": 1,
        },
        # Distinct crater elsewhere
        {
            "center_x": 50.0,
            "center_y": 50.0,
            "radius_px": 10.0,
            "confidence": 0.90,
            "tile_index": 0,
        },
    ]

    deduped = non_maximum_suppression_circles(raw_detections, iou_threshold=0.35)
    # The duplicate from tile 1 should be suppressed
    assert len(deduped) == 2
    # Verify the higher confidence detection (0.88) was kept
    matched = [d for d in deduped if abs(d["center_x"] - 222.0) < 5.0]
    assert len(matched) == 1
    assert matched[0]["confidence"] == 0.88


def test_tiling_and_stitching_geometry() -> None:
    full_image = np.ones((400, 400), dtype=np.float32)
    tiles = generate_overlapping_tiles(full_image, tile_size=256, overlap=32)
    assert len(tiles) >= 4

    # Verify tile coordinate ranges cover full bounds
    max_y = max(t.y_max for t in tiles)
    max_x = max(t.x_max for t in tiles)
    assert max_y == 400
    assert max_x == 400

    # Test seamless stitching
    heatmaps = [np.ones((256, 256), dtype=np.float32) * 0.7 for _ in tiles]
    stitched = stitch_hazard_heatmap(tiles, heatmaps, (400, 400))
    assert stitched.shape == (400, 400)
    assert np.allclose(stitched, 0.7, atol=1e-3)
