"""Vectorized statistical metrics for illumination time stacks."""

from typing import cast

import numpy as np


def compute_lit_fraction(cube: np.ndarray) -> np.ndarray:
    """Calculate the fraction of time illuminated for each cell in [0.0, 1.0].

    Args:
        cube: 3D boolean or uint8 array of shape (time_steps, rows, cols).
              True/1 represents illuminated, False/0 represents shadow.

    Returns:
        2D float32 array of shape (rows, cols).
    """
    if cube.ndim != 3:
        raise ValueError(f"cube must be 3D (T, H, W), got {cube.shape}")
    return np.mean(cube, axis=0, dtype=np.float32)


def compute_longest_interval(cube: np.ndarray, target_val: bool, dt_seconds: float) -> np.ndarray:
    """Compute the longest continuous duration matching target_val for each cell.

    Args:
        cube: 3D boolean array (T, H, W).
        target_val: False for darkness, True for sunlight.
        dt_seconds: Duration of each time step in seconds.

    Returns:
        2D float32 array of shape (rows, cols) representing duration in seconds.
    """
    t_steps, rows, cols = cube.shape
    max_count = np.zeros((rows, cols), dtype=np.int32)
    curr_count = np.zeros((rows, cols), dtype=np.int32)

    for t in range(t_steps):
        mask = cube[t] == target_val
        curr_count = np.where(mask, curr_count + 1, 0)
        max_count = np.maximum(max_count, curr_count)

    return (max_count * dt_seconds).astype(np.float32)


def compute_longest_dark_s(cube: np.ndarray, dt_seconds: float) -> np.ndarray:
    """Compute longest continuous darkness in seconds for each cell."""
    return compute_longest_interval(cube, target_val=False, dt_seconds=dt_seconds)


def compute_longest_lit_s(cube: np.ndarray, dt_seconds: float) -> np.ndarray:
    """Compute longest continuous sunlight in seconds for each cell."""
    return compute_longest_interval(cube, target_val=True, dt_seconds=dt_seconds)


def compute_psr_mask(lit_fraction: np.ndarray) -> np.ndarray:
    """Identify Permanently Shadowed Regions (PSR), where lit fraction is strictly zero.

    Args:
        lit_fraction: 2D array of lit fractions in [0.0, 1.0].

    Returns:
        2D boolean array where True indicates a PSR.
    """
    return cast(np.ndarray, lit_fraction == 0.0)


def compute_transitions_count(cube: np.ndarray) -> np.ndarray:
    """Count total state transitions (sunrise and sunset) for each cell across the period."""
    if cube.shape[0] < 2:
        return np.zeros((cube.shape[1], cube.shape[2]), dtype=np.int32)

    diffs = np.diff(cube.astype(np.int8), axis=0)
    transitions = np.sum(diffs != 0, axis=0, dtype=np.int32)
    return transitions


def compute_aggregate_summary(cube: np.ndarray, dt_seconds: float) -> dict[str, float]:
    """Compute scalar aggregate metrics across the entire spatiotemporal AOI."""
    lit_frac = compute_lit_fraction(cube)
    dark_s = compute_longest_dark_s(cube, dt_seconds)
    lit_s = compute_longest_lit_s(cube, dt_seconds)
    psr = compute_psr_mask(lit_frac)

    return {
        "mean_lit_fraction": float(np.mean(lit_frac)),
        "min_lit_fraction": float(np.min(lit_frac)),
        "max_lit_fraction": float(np.max(lit_frac)),
        "psr_area_fraction": float(np.mean(psr)),
        "max_dark_duration_hours": float(np.max(dark_s) / 3600.0),
        "max_lit_duration_hours": float(np.max(lit_s) / 3600.0),
    }
