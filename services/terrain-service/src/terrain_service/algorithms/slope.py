"""Horn's 3x3 slope calculation algorithm."""

from __future__ import annotations

import numpy as np


def compute_slope_horn(
    elevation: np.ndarray,
    resolution_m: float = 10.0,
    nodata_val: float = np.nan,
) -> np.ndarray:
    """Compute slope in degrees using Horn's 3x3 weighted finite-difference method.

    Parameters:
        elevation: 2D array of elevation values in metres.
        resolution_m: Pixel spatial resolution in metres (grid cell size).
        nodata_val: Value representing no-data in the input elevation array.

    Returns:
        2D float32 array of slope values in degrees (0 to 90).
        Border cells and cells with invalid/no-data neighbors are set to np.nan.
    """
    if elevation.ndim != 2:
        raise ValueError(f"Elevation array must be 2-dimensional, got shape {elevation.shape}")
    if resolution_m <= 0:
        raise ValueError(f"Resolution must be positive, got {resolution_m}")

    h, w = elevation.shape
    slope_deg = np.full((h, w), np.nan, dtype=np.float32)

    if h < 3 or w < 3:
        return slope_deg

    # Work with float64 internally for numerical precision
    elev = elevation.astype(np.float64, copy=True)
    if not np.isnan(nodata_val):
        elev[elev == nodata_val] = np.nan

    # Extract 3x3 neighborhood windows
    z11 = elev[0:-2, 0:-2]
    z12 = elev[0:-2, 1:-1]
    z13 = elev[0:-2, 2:]
    z21 = elev[1:-1, 0:-2]
    z22 = elev[1:-1, 1:-1]
    z23 = elev[1:-1, 2:]
    z31 = elev[2:, 0:-2]
    z32 = elev[2:, 1:-1]
    z33 = elev[2:, 2:]

    # Mask of cells where all 9 neighbors are finite (valid)
    valid_mask = (
        np.isfinite(z11)
        & np.isfinite(z12)
        & np.isfinite(z13)
        & np.isfinite(z21)
        & np.isfinite(z22)
        & np.isfinite(z23)
        & np.isfinite(z31)
        & np.isfinite(z32)
        & np.isfinite(z33)
    )

    # Horn finite differences
    dx = ((z13 + 2.0 * z23 + z33) - (z11 + 2.0 * z21 + z31)) / (8.0 * resolution_m)
    dy = ((z31 + 2.0 * z32 + z33) - (z11 + 2.0 * z12 + z13)) / (8.0 * resolution_m)

    grad = np.sqrt(dx**2 + dy**2)
    slope_rad = np.arctan(grad)
    slope_interior = np.degrees(slope_rad).astype(np.float32)

    # Apply valid mask
    slope_interior[~valid_mask] = np.nan
    slope_deg[1:-1, 1:-1] = slope_interior

    return slope_deg
