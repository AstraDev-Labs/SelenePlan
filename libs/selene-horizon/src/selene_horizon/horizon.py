"""Horizon profile computation kernel for lunar terrain with spherical curvature correction.

Accelerated via Numba parallel JIT.
SI Units: Metres, radians.
Moon Reference Radius: 1,737,400.0 m (docs/08-science-notes.md, Section 1).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit, prange
from selene_geo.constants import MOON_RADIUS_M


@njit(fastmath=True, nogil=True)
def _bilinear_interpolate(
    dem: np.ndarray,
    r: float,
    c: float,
    rows: int,
    cols: int,
) -> float:
    """Sample DEM with bilinear interpolation and clamping."""
    r0 = math.floor(r)
    c0 = math.floor(c)

    r0 = max(r0, 0)
    c0 = max(c0, 0)
    r1 = r0 + 1
    c1 = c0 + 1
    if r1 >= rows:
        r1 = rows - 1
    if c1 >= cols:
        c1 = cols - 1

    dr = r - r0
    dc = c - c0

    v00 = dem[r0, c0]
    v01 = dem[r0, c1]
    v10 = dem[r1, c0]
    v11 = dem[r1, c1]

    top = (1.0 - dc) * v00 + dc * v01
    bot = (1.0 - dc) * v10 + dc * v11
    return (1.0 - dr) * top + dr * bot


@njit(parallel=True, fastmath=True, nogil=True)
def _compute_horizon_numba(
    dem: np.ndarray,
    cell_size_m: float,
    azimuth_rads: np.ndarray,
    max_ray_steps: int,
    moon_radius_m: float,
    step_pixel: float,
) -> np.ndarray:
    """Parallel ray-marching kernel for horizon elevation profiles."""
    rows, cols = dem.shape
    num_bins = len(azimuth_rads)
    # Output array: shape (rows, cols, num_bins) in float32 radians
    horizon = np.zeros((rows, cols, num_bins), dtype=np.float32)

    # Precompute ray step components (North: d_row=-1, d_col=0; East: d_row=0, d_col=+1)
    d_cols = np.zeros(num_bins, dtype=np.float64)
    d_rows = np.zeros(num_bins, dtype=np.float64)
    for b in range(num_bins):
        az = azimuth_rads[b]
        d_cols[b] = math.sin(az) * step_pixel
        d_rows[b] = -math.cos(az) * step_pixel

    step_dist_m = step_pixel * cell_size_m
    inv_2_rmoon = 1.0 / (2.0 * moon_radius_m)

    for r in prange(rows):
        for c in range(cols):
            z0 = dem[r, c]

            for b in range(num_bins):
                dc_step = d_cols[b]
                dr_step = d_rows[b]

                max_tan_theta = -1e9

                curr_r = float(r)
                curr_c = float(c)

                for step in range(1, max_ray_steps + 1):
                    curr_r += dr_step
                    curr_c += dc_step

                    # Ray exits raster boundary
                    if curr_r < 0.0 or curr_r >= rows - 1.0 or curr_c < 0.0 or curr_c >= cols - 1.0:
                        break

                    z_sample = _bilinear_interpolate(dem, curr_r, curr_c, rows, cols)
                    dist_m = step * step_dist_m

                    # Spherical curvature correction: drop = d^2 / (2 * R_moon)
                    curv_drop = (dist_m * dist_m) * inv_2_rmoon
                    effective_diff = (z_sample - curv_drop) - z0

                    tan_theta = effective_diff / dist_m
                    max_tan_theta = max(max_tan_theta, tan_theta)

                # Angle in radians, bounded below by zero (local horizontal)
                if max_tan_theta > 0.0:
                    horizon[r, c, b] = np.float32(math.atan(max_tan_theta))
                else:
                    horizon[r, c, b] = np.float32(0.0)

    return horizon


def compute_padding_margin_m(max_relief_m: float, min_elevation_deg: float) -> float:
    """Calculate the required DEM halo padding in metres based on maximum expected relief.

    Args:
        max_relief_m: Maximum topographic relief difference in metres.
        min_elevation_deg: Minimum Sun elevation considered for shadows (e.g. 1.0 deg).

    Returns:
        Halo reach distance in metres: max_relief / tan(min_elevation).
    """
    min_elevation_deg = max(0.1, min_elevation_deg)
    tan_el = math.tan(math.radians(min_elevation_deg))
    return max_relief_m / tan_el


def compute_horizon_profile(
    dem: np.ndarray,
    cell_size_m: float,
    azimuth_bins: int = 360,
    max_ray_dist_m: float = 50_000.0,
    moon_radius_m: float = MOON_RADIUS_M,
    step_pixel: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute terrain horizon elevation angles across discrete azimuth bins for each cell.

    Args:
        dem: 2D array of elevations in metres.
        cell_size_m: Pixel spatial resolution in metres.
        azimuth_bins: Number of discrete azimuthal angles (e.g. 360 or 720).
        max_ray_dist_m: Maximum ray reach in metres (default 50 km).
        moon_radius_m: Lunar reference sphere radius in metres.
        step_pixel: Fractional or integral step length in pixels along ray.

    Returns:
        Tuple of:
            - horizon: 3D float32 array of shape (rows, cols, azimuth_bins) in radians.
            - azimuths_rad: 1D array of azimuth angles in radians [0, 2*pi).
    """
    if dem.ndim != 2:
        raise ValueError(f"dem must be a 2D array, got shape {dem.shape}")
    if cell_size_m <= 0:
        raise ValueError("cell_size_m must be positive")

    azimuths_rad = np.linspace(0.0, 2.0 * math.pi, azimuth_bins, endpoint=False, dtype=np.float64)
    max_steps = math.ceil(max_ray_dist_m / (cell_size_m * step_pixel))

    # Ensure contiguous float64 array for Numba
    dem_c = np.ascontiguousarray(dem, dtype=np.float64)

    horizon = _compute_horizon_numba(
        dem=dem_c,
        cell_size_m=float(cell_size_m),
        azimuth_rads=azimuths_rad,
        max_ray_steps=max_steps,
        moon_radius_m=float(moon_radius_m),
        step_pixel=float(step_pixel),
    )

    return horizon, azimuths_rad


def evaluate_lit_mask(
    horizon: np.ndarray,
    azimuths_rad: np.ndarray,
    sun_az_rad: float,
    sun_el_rad: float,
) -> np.ndarray:
    """Evaluate binary lit/shadow mask for a given Sun position from precomputed horizon.

    Args:
        horizon: Precomputed 3D horizon array (rows, cols, azimuth_bins) in radians.
        azimuths_rad: 1D array of azimuth bin centers in radians.
        sun_az_rad: Sun azimuth angle in radians [0, 2*pi).
        sun_el_rad: Sun elevation angle in radians above horizontal.

    Returns:
        2D boolean array where True indicates illuminated and False indicates shadowed.
    """
    # Sun below local horizontal is shadowed everywhere
    if sun_el_rad <= 0.0:
        return np.zeros((horizon.shape[0], horizon.shape[1]), dtype=bool)

    # Nearest or interpolated azimuth bin
    num_bins = len(azimuths_rad)
    norm_az = sun_az_rad % (2.0 * math.pi)
    bin_idx = round(norm_az / (2.0 * math.pi) * num_bins) % num_bins

    # Lit if Sun elevation exceeds terrain horizon angle
    horizon_slice = horizon[:, :, bin_idx]
    return sun_el_rad > horizon_slice
