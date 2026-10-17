"""Horn's 3x3 aspect calculation algorithm."""

from __future__ import annotations

import numpy as np


def compute_aspect_horn(
    elevation: np.ndarray,
    resolution_m: float = 10.0,
    nodata_val: float = np.nan,
) -> np.ndarray:
    """Compute terrain aspect (azimuth of slope gradient) in degrees.

    Azimuth is expressed as compass bearing clockwise from North (0 to 360):
    - 0 deg = North
    - 90 deg = East
    - 180 deg = South
    - 270 deg = West
    Flat areas (slope = 0) are assigned -1.0.
    Border cells and cells with invalid/no-data neighbors are set to np.nan.

    Parameters:
        elevation: 2D array of elevation values in metres.
        resolution_m: Spatial resolution in metres.
        nodata_val: Sentinel value for no-data cells.

    Returns:
        2D float32 array of aspect values in degrees.
    """
    if elevation.ndim != 2:
        raise ValueError(f"Elevation array must be 2-dimensional, got shape {elevation.shape}")
    if resolution_m <= 0:
        raise ValueError(f"Resolution must be positive, got {resolution_m}")

    h, w = elevation.shape
    aspect_deg = np.full((h, w), np.nan, dtype=np.float32)

    if h < 3 or w < 3:
        return aspect_deg

    elev = elevation.astype(np.float64, copy=True)
    if not np.isnan(nodata_val):
        elev[elev == nodata_val] = np.nan

    z11 = elev[0:-2, 0:-2]
    z12 = elev[0:-2, 1:-1]
    z13 = elev[0:-2, 2:]
    z21 = elev[1:-1, 0:-2]
    z22 = elev[1:-1, 1:-1]
    z23 = elev[1:-1, 2:]
    z31 = elev[2:, 0:-2]
    z32 = elev[2:, 1:-1]
    z33 = elev[2:, 2:]

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

    # dx is dz/dx (Eastward)
    dx = ((z13 + 2.0 * z23 + z33) - (z11 + 2.0 * z21 + z31)) / (8.0 * resolution_m)
    # dy_north is dz/dy (Northward, opposite of row increment)
    dy_north = ((z11 + 2.0 * z12 + z13) - (z31 + 2.0 * z32 + z33)) / (8.0 * resolution_m)

    # Compass aspect alpha = atan2(dx, dy_north)
    aspect_rad = np.arctan2(dx, dy_north)
    aspect_interior = (np.degrees(aspect_rad) + 360.0) % 360.0

    # Handle exact flat areas (gradient is 0)
    flat_mask = (np.abs(dx) < 1e-9) & (np.abs(dy_north) < 1e-9)
    aspect_interior[flat_mask] = -1.0

    aspect_interior[~valid_mask] = np.nan
    aspect_deg[1:-1, 1:-1] = aspect_interior.astype(np.float32)

    return aspect_deg
