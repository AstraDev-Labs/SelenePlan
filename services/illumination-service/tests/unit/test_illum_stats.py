"""Unit tests for illumination statistical calculations."""

import numpy as np

from illumination_service.stats.illum_stats import (
    compute_aggregate_summary,
    compute_lit_fraction,
    compute_longest_dark_s,
    compute_longest_lit_s,
    compute_psr_mask,
    compute_transitions_count,
)


def test_compute_lit_fraction_simple() -> None:
    # 4 time steps, 2x2 grid
    cube = np.array(
        [
            [[True, False], [True, True]],
            [[True, False], [False, True]],
            [[False, False], [True, True]],
            [[False, False], [False, False]],
        ],
        dtype=bool,
    )

    lit_f = compute_lit_fraction(cube)
    assert lit_f[0, 0] == 0.5  # 2 out of 4
    assert lit_f[0, 1] == 0.0  # 0 out of 4 (PSR)
    assert lit_f[1, 0] == 0.5  # 2 out of 4
    assert lit_f[1, 1] == 0.75  # 3 out of 4


def test_longest_dark_and_lit() -> None:
    # Cube: cell (0, 0) is lit, dark, dark, lit, dark (steps = 5, dt = 100s)
    # Dark intervals: [dark, dark] -> length 2 steps = 200s; [dark] -> length 1 step = 100s -> max = 200s
    # Lit intervals: [lit] -> 100s, [lit] -> 100s -> max = 100s
    cube = np.zeros((5, 1, 1), dtype=bool)
    cube[0, 0, 0] = True
    cube[1, 0, 0] = False
    cube[2, 0, 0] = False
    cube[3, 0, 0] = True
    cube[4, 0, 0] = False

    dt = 100.0
    dark_s = compute_longest_dark_s(cube, dt)
    lit_s = compute_longest_lit_s(cube, dt)

    assert dark_s[0, 0] == 200.0
    assert lit_s[0, 0] == 100.0


def test_psr_mask() -> None:
    lit_f = np.array([[0.0, 0.25], [1.0, 0.0]], dtype=np.float32)
    psr = compute_psr_mask(lit_f)
    assert np.array_equal(psr, np.array([[True, False], [False, True]]))


def test_transitions_count() -> None:
    # 0 -> 1 -> 0 -> 1 : 3 transitions
    cube = np.zeros((4, 1, 1), dtype=bool)
    cube[0, 0, 0] = False
    cube[1, 0, 0] = True
    cube[2, 0, 0] = False
    cube[3, 0, 0] = True

    transitions = compute_transitions_count(cube)
    assert transitions[0, 0] == 3


def test_aggregate_summary() -> None:
    cube = np.ones((10, 5, 5), dtype=bool)
    summary = compute_aggregate_summary(cube, dt_seconds=3600.0)
    assert summary["mean_lit_fraction"] == 1.0
    assert summary["psr_area_fraction"] == 0.0
    assert summary["max_dark_duration_hours"] == 0.0
    assert summary["max_lit_duration_hours"] == 10.0
