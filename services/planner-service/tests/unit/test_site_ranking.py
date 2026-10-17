"""Unit tests for landing site ranking hard constraints and determinism."""

import numpy as np
from planner_service.ranking.ranker import rank_landing_sites


def test_ranking_determinism() -> None:
    size = 40
    slope = np.ones((size, size), dtype=np.float32) * 5.0
    hazard = np.zeros((size, size), dtype=bool)
    lit = np.ones((size, size), dtype=np.float32) * 0.8
    vis = np.ones((size, size), dtype=np.float32) * 0.9
    rough = np.ones((size, size), dtype=np.float32) * 0.5
    dark = np.ones((size, size), dtype=np.float32) * 50.0

    r1 = rank_landing_sites(slope, hazard, lit, vis, rough, dark, spacing_cells=4)
    r2 = rank_landing_sites(slope, hazard, lit, vis, rough, dark, spacing_cells=4)

    assert r1.total_evaluated == r2.total_evaluated
    assert len(r1.ranked_sites) == len(r2.ranked_sites)
    for s1, s2 in zip(r1.ranked_sites, r2.ranked_sites, strict=True):
        assert s1.site_id == s2.site_id
        assert s1.score == s2.score
        assert s1.rank == s2.rank


def test_ranking_hard_constraint_rejections() -> None:
    size = 30
    slope = np.ones((size, size), dtype=np.float32) * 5.0
    hazard = np.zeros((size, size), dtype=bool)
    lit = np.ones((size, size), dtype=np.float32) * 0.8
    vis = np.ones((size, size), dtype=np.float32) * 0.9
    rough = np.ones((size, size), dtype=np.float32) * 0.5
    dark = np.ones((size, size), dtype=np.float32) * 50.0

    # Plant specific constraint violations:
    # 1. High slope zone at (10, 10)
    slope[8:13, 8:13] = 22.0

    # 2. Hazard cell zone at (20, 20)
    hazard[20, 20] = True

    # 3. Low lit fraction zone at (10, 20)
    lit[8:13, 18:23] = 0.15

    res = rank_landing_sites(
        slope_grid=slope,
        hazard_grid=hazard,
        lit_fraction_grid=lit,
        earth_vis_grid=vis,
        roughness_grid=rough,
        longest_dark_grid=dark,
        spacing_cells=5,
        max_slope_deg=12.0,
        min_lit_fraction=0.40,
    )

    assert len(res.rejected_sites) >= 3

    # Verify explicit rejection reasons
    slope_rejects = [
        s for s in res.rejected_sites if any("slope" in r.lower() for r in s.reject_reasons)
    ]
    assert len(slope_rejects) >= 1

    hazard_rejects = [
        s for s in res.rejected_sites if any("hazard" in r.lower() for r in s.reject_reasons)
    ]
    assert len(hazard_rejects) >= 1

    lit_rejects = [
        s for s in res.rejected_sites if any("sunlit" in r.lower() for r in s.reject_reasons)
    ]
    assert len(lit_rejects) >= 1
