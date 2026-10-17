"""Circular Non-Maximum Suppression (NMS) for crater detection deduplication."""

import math
from typing import Any


def circle_intersection_area(r1: float, r2: float, d: float) -> float:
    """Calculate the area of intersection between two circles of radii r1, r2 separated by distance d."""
    if d >= r1 + r2:
        return 0.0
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2

    # Circular lens intersection formula
    r1_sq = r1 * r1
    r2_sq = r2 * r2
    d_sq = d * d

    alpha = math.acos(max(-1.0, min(1.0, (d_sq + r1_sq - r2_sq) / (2.0 * d * r1))))
    beta = math.acos(max(-1.0, min(1.0, (d_sq + r2_sq - r1_sq) / (2.0 * d * r2))))

    part1 = r1_sq * alpha
    part2 = r2_sq * beta
    part3 = 0.5 * math.sqrt(
        max(0.0, (-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
    )

    return part1 + part2 - part3


def circle_iou(r1: float, r2: float, d: float) -> float:
    """Calculate Intersection over Union (IoU) of two circular regions."""
    area1 = math.pi * r1 * r1
    area2 = math.pi * r2 * r2
    area_int = circle_intersection_area(r1, r2, d)
    union = area1 + area2 - area_int
    if union <= 0.0:
        return 0.0
    return area_int / union


def non_maximum_suppression_circles(
    detections: list[dict[str, Any]],
    iou_threshold: float = 0.35,
    center_dist_ratio: float = 0.60,
) -> list[dict[str, Any]]:
    """Deduplicate overlapping circular detections across tile boundaries.

    Each detection dict must have:
      - 'center_x': float
      - 'center_y': float
      - 'radius_px': float
      - 'confidence': float
    """
    if not detections:
        return []

    # Sort descending by confidence
    sorted_dets = sorted(detections, key=lambda d: d.get("confidence", 0.0), reverse=True)
    kept: list[dict[str, Any]] = []

    for det in sorted_dets:
        cx1 = det["center_x"]
        cy1 = det["center_y"]
        r1 = det["radius_px"]

        suppress = False
        for k in kept:
            cx2 = k["center_x"]
            cy2 = k["center_y"]
            r2 = k["radius_px"]

            d = math.hypot(cx1 - cx2, cy1 - cy2)
            # Direct proximity check: centers within fraction of combined radii
            if d < center_dist_ratio * (r1 + r2):
                suppress = True
                break

            iou = circle_iou(r1, r2, d)
            if iou >= iou_threshold:
                suppress = True
                break

        if not suppress:
            kept.append(det)

    return kept
