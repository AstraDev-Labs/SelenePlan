"""Unit tests for comms window extraction and blackout analysis."""

from comms_service.windows.extractor import (
    compute_blackout_stats,
    extract_visibility_windows,
)


def test_window_extraction_edge_cases() -> None:
    # 5 steps: True, False, True, True, True
    # Window 1: step 0 (1 step = 3600s)
    # Window 2: steps 2 to 4 (3 steps = 10800s)
    series = [True, False, True, True, True]
    timestamps = [f"2026-03-01T0{i}:00:00Z" for i in range(5)]
    dt = 3600.0

    windows = extract_visibility_windows(series, timestamps, dt)
    assert len(windows) == 2
    assert windows[0].start_index == 0
    assert windows[0].end_index == 0
    assert windows[0].duration_hours == 1.0

    assert windows[1].start_index == 2
    assert windows[1].end_index == 4
    assert windows[1].duration_hours == 3.0


def test_window_extraction_all_dark() -> None:
    series = [False, False, False]
    timestamps = ["T0", "T1", "T2"]
    windows = extract_visibility_windows(series, timestamps, 1800.0)
    assert len(windows) == 0

    stats = compute_blackout_stats(series, 1800.0)
    assert stats["visible_fraction"] == 0.0
    assert stats["longest_blackout_hours"] == 1.5
    assert stats["total_windows"] == 0


def test_window_extraction_all_visible() -> None:
    series = [True, True, True, True]
    timestamps = ["T0", "T1", "T2", "T3"]
    windows = extract_visibility_windows(series, timestamps, 3600.0)
    assert len(windows) == 1
    assert windows[0].start_index == 0
    assert windows[0].end_index == 3
    assert windows[0].duration_hours == 4.0

    stats = compute_blackout_stats(series, 3600.0)
    assert stats["visible_fraction"] == 1.0
    assert stats["longest_blackout_hours"] == 0.0
    assert stats["total_windows"] == 1
