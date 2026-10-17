"""Terrain hazard mask evaluation based on rover profile thresholds."""

from __future__ import annotations

import numpy as np


def compute_terrain_hazard(
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    max_slope_deg: float = 15.0,
    max_roughness: float = 0.35,
    nodata_is_hazard: bool = True,
) -> np.ndarray:
    """Evaluate binary terrain hazard mask based on slope and roughness thresholds.

    Parameters:
        slope_deg: 2D array of slope values in degrees.
        roughness: 2D array of surface roughness values (TRI) in metres.
        max_slope_deg: Maximum allowable slope for rover trafficability.
        max_roughness: Maximum allowable roughness for rover wheel clearance.
        nodata_is_hazard: If True, missing or border NaN cells are marked hazardous (1).

    Returns:
        2D uint8 array where 1 indicates hazardous (untraversable) and 0 indicates safe.
    """
    if slope_deg.shape != roughness.shape:
        raise ValueError(f"Shape mismatch: slope {slope_deg.shape} vs roughness {roughness.shape}")

    # Initialize mask to 0 (safe)
    hazard_mask = np.zeros(slope_deg.shape, dtype=np.uint8)

    # Identify valid and nodata cells
    slope_valid = np.isfinite(slope_deg)
    roughness_valid = np.isfinite(roughness)
    both_valid = slope_valid & roughness_valid

    # Threshold checks on valid cells
    slope_hazard = both_valid & (slope_deg > max_slope_deg)
    roughness_hazard = both_valid & (roughness > max_roughness)

    hazard_mask[slope_hazard | roughness_hazard] = 1

    # Nodata treatment (fail-closed policy)
    if nodata_is_hazard:
        hazard_mask[~both_valid] = 1

    return hazard_mask
