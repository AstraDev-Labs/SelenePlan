"""Property test: window extraction verified against independent brute-force reference.

Acceptance Criterion 3 (comms SPEC.md).
"""

import numpy as np
import pytest

from comms_service.windows.extractor import extract_visibility_windows


def brute_force_find_contiguous_true_spans(series: list[bool]) -> list[tuple[int, int]]:
    """Ground-truth reference: finds all [start, end] inclusive contiguous True intervals."""
    spans: list[tuple[int, int]] = []
    n = len(series)
    i = 0
    while i < n:
        if series[i]:
            j = i
            while j < n and series[j]:
                j += 1
            spans.append((i, j - 1))
            i = j
        else:
            i += 1
    return spans


@pytest.mark.parametrize("seed", [7, 42, 101, 2024, 9999])
def test_window_extraction_property_against_brute_force(seed: int) -> None:
    """Property test: window extraction matches brute-force contiguous interval finder on random binary series."""
    np.random.seed(seed)

    # Random series length from 5 to 150
    n = np.random.randint(5, 150)
    p_vis = np.random.uniform(0.05, 0.95)
    series = [bool(v) for v in np.random.choice([True, False], size=n, p=[p_vis, 1.0 - p_vis])]
    timestamps = [f"2026-03-01T{i:04d}:00Z" for i in range(n)]
    dt_s = 3600.0

    # Under test
    windows = extract_visibility_windows(series, timestamps, dt_s)

    # Reference
    expected_spans = brute_force_find_contiguous_true_spans(series)

    assert len(windows) == len(expected_spans)

    for win, (exp_start, exp_end) in zip(windows, expected_spans):
        assert win.start_index == exp_start
        assert win.end_index == exp_end
        assert win.steps_count == (exp_end - exp_start + 1)
        assert win.start_iso == timestamps[exp_start]
        assert win.end_iso == timestamps[exp_end]
