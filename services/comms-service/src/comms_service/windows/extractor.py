"""Visibility window extraction and communications blackout analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class VisibilityWindow:
    """A continuous temporal interval where direct-to-Earth communication is unblocked."""

    start_index: int
    end_index: int
    start_iso: str
    end_iso: str
    duration_seconds: float
    duration_hours: float
    steps_count: int


def extract_visibility_windows(
    series: Sequence[bool] | np.ndarray,
    timestamps_iso: Sequence[str],
    dt_seconds: float,
) -> list[VisibilityWindow]:
    """Extract contiguous time intervals where Earth line-of-sight is continuously open.

    Correctly handles edge cases:
    - Interval open at timeline start (index 0)
    - Interval open at timeline end (index N-1)
    - Isolated single-step windows
    - Zero windows (continuous blackout)
    - Single window spanning full duration (continuous coverage)

    Args:
        series: 1D boolean array/list (True = visible, False = blocked).
        timestamps_iso: List of ISO 8601 strings corresponding to each step.
        dt_seconds: Time interval between steps in seconds.

    Returns:
        List of VisibilityWindow objects.
    """
    if len(series) == 0:
        return []

    windows: list[VisibilityWindow] = []
    in_window = False
    start_idx = 0

    for i, is_vis in enumerate(series):
        if is_vis and not in_window:
            in_window = True
            start_idx = i
        elif not is_vis and in_window:
            in_window = False
            duration_s = (i - start_idx) * dt_seconds
            windows.append(
                VisibilityWindow(
                    start_index=start_idx,
                    end_index=i - 1,
                    start_iso=timestamps_iso[start_idx],
                    end_iso=timestamps_iso[i - 1],
                    duration_seconds=duration_s,
                    duration_hours=duration_s / 3600.0,
                    steps_count=i - start_idx,
                )
            )

    if in_window:
        duration_s = (len(series) - start_idx) * dt_seconds
        windows.append(
            VisibilityWindow(
                start_index=start_idx,
                end_index=len(series) - 1,
                start_iso=timestamps_iso[start_idx],
                end_iso=timestamps_iso[-1],
                duration_seconds=duration_s,
                duration_hours=duration_s / 3600.0,
                steps_count=len(series) - start_idx,
            )
        )

    return windows


def compute_blackout_stats(
    series: Sequence[bool] | np.ndarray,
    dt_seconds: float,
) -> dict[str, float]:
    """Compute communications blackout statistics for a 1D line-of-sight time series."""
    arr = np.asarray(series, dtype=bool)
    if len(arr) == 0:
        return {
            "visible_fraction": 0.0,
            "longest_blackout_hours": 0.0,
            "longest_window_hours": 0.0,
            "total_windows": 0.0,
        }

    vis_fraction = float(np.mean(arr))

    # Longest continuous False (blackout)
    max_blackout = 0
    curr_blackout = 0
    max_window = 0
    curr_window = 0

    for val in arr:
        if not val:
            curr_blackout += 1
            if curr_blackout > max_blackout:
                max_blackout = curr_blackout
            curr_window = 0
        else:
            curr_window += 1
            if curr_window > max_window:
                max_window = curr_window
            curr_blackout = 0

    # Count windows
    diffs = np.diff(arr.astype(np.int8))
    # rising edges: 0 -> 1
    num_windows = int(np.sum(diffs == 1)) + (1 if arr[0] else 0)

    return {
        "visible_fraction": vis_fraction,
        "longest_blackout_hours": (max_blackout * dt_seconds) / 3600.0,
        "longest_window_hours": (max_window * dt_seconds) / 3600.0,
        "total_windows": float(num_windows),
    }
