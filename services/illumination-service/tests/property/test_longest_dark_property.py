"""Property test comparing vectorized longest_dark_s against a brute-force reference algorithm.

Acceptance Criterion 6 (SPEC.md).
"""

import numpy as np
import pytest

from illumination_service.stats.illum_stats import compute_longest_dark_s


def brute_force_longest_dark_1d(series: list[bool] | np.ndarray, dt_s: float) -> float:
    """Independent ground-truth reference for longest consecutive dark period."""
    max_streak = 0
    current_streak = 0
    for is_lit in series:
        if not is_lit:  # dark
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0
    return max_streak * dt_s


@pytest.mark.parametrize("seed", [10, 42, 99, 12345, 98765])
def test_longest_dark_matches_brute_force_property(seed: int) -> None:
    """Property test: vectorized computation equals brute force for arbitrary random binary cubes."""
    np.random.seed(seed)

    # Random cube dimensions: 20 to 100 time steps, 3 to 8 rows and cols
    t_len = np.random.randint(20, 100)
    rows = np.random.randint(3, 8)
    cols = np.random.randint(3, 8)
    dt_s = float(np.random.choice([60.0, 300.0, 1800.0, 3600.0]))

    # Random binary mask with varying probability of light
    p_lit = np.random.uniform(0.1, 0.9)
    cube = np.random.choice([True, False], size=(t_len, rows, cols), p=[p_lit, 1.0 - p_lit])

    # 1. Vectorized implementation under test
    vectorized_result = compute_longest_dark_s(cube, dt_s)

    # 2. Brute-force ground truth for every individual cell
    brute_result = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            brute_result[r, c] = brute_force_longest_dark_1d(cube[:, r, c], dt_s)

    # Bit-for-bit equivalence
    assert np.array_equal(vectorized_result, brute_result)
