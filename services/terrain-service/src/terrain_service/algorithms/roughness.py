"""Terrain Ruggedness Index (TRI) roughness calculation algorithm."""

from __future__ import annotations

import numpy as np


def compute_roughness_tri(
    elevation: np.ndarray,
    nodata_val: float = np.nan,
) -> np.ndarray:
    """Compute Terrain Ruggedness Index (TRI) roughness in metres over a 3x3 window.

    TRI is defined as the root-mean-square elevation difference between the center cell
    and its 8 adjacent neighbors (Riley et al., 1999):
        TRI = sqrt( (1/8) * sum_{i != center} (z_i - z_center)^2 )

    Parameters:
        elevation: 2D array of elevation values in metres.
        nodata_val: Sentinel value for no-data cells.

    Returns:
        2D float32 array of roughness values in metres.
        Border cells and cells with invalid/no-data neighbors are set to np.nan.
    """
    if elevation.ndim != 2:
        raise ValueError(f"Elevation array must be 2-dimensional, got shape {elevation.shape}")

    h, w = elevation.shape
    roughness = np.full((h, w), np.nan, dtype=np.float32)

    if h < 3 or w < 3:
        return roughness

    elev = elevation.astype(np.float64, copy=True)
    if not np.isnan(nodata_val):
        elev[elev == nodata_val] = np.nan

    z_center = elev[1:-1, 1:-1]

    # 8 neighbors
    neighbors = [
        elev[0:-2, 0:-2],  # top-left
        elev[0:-2, 1:-1],  # top
        elev[0:-2, 2:],  # top-right
        elev[1:-1, 0:-2],  # left
        elev[1:-1, 2:],  # right
        elev[2:, 0:-2],  # bottom-left
        elev[2:, 1:-1],  # bottom
        elev[2:, 2:],  # bottom-right
    ]

    valid_mask = np.isfinite(z_center)
    for n in neighbors:
        valid_mask &= np.isfinite(n)

    sq_diff_sum = np.zeros_like(z_center)
    for n in neighbors:
        sq_diff_sum += (n - z_center) ** 2

    tri = np.sqrt(sq_diff_sum / 8.0).astype(np.float32)
    tri[~valid_mask] = np.nan
    roughness[1:-1, 1:-1] = tri

    return roughness
