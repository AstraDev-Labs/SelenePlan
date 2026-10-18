"""Property-based invariance tests for traverse planning constraints."""

import numpy as np
import pytest
from planner_service.energy.model import RoverEnergyProfile
from planner_service.traverse.planner import plan_traverse


@pytest.mark.parametrize("seed", [42, 101, 2024, 7777])
def test_traverse_invariance_never_enters_hazards_or_exceeds_max_slope(seed: int) -> None:
    rng = np.random.RandomState(seed)
    size = 25
    max_slope = 14.0

    # Random slope grid
    slope_grid = rng.uniform(2.0, 25.0, (size, size)).astype(np.float32)
    # Random hazard mask (10% of cells)
    hazard_grid = (rng.rand(size, size) < 0.12) | (slope_grid > max_slope)

    # Clear start and goal
    hazard_grid[2, 2] = False
    slope_grid[2, 2] = 5.0
    hazard_grid[22, 22] = False
    slope_grid[22, 22] = 5.0

    t_steps = 30
    illum = np.ones((t_steps, size, size), dtype=bool)
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    sun_elevs = [1.54] * t_steps

    profile = RoverEnergyProfile(min_survival_wh=100.0)

    res = plan_traverse(
        start_rc=(2, 2),
        goal_rc=(22, 22),
        elevation_grid=np.zeros((size, size)),
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
        profile=profile,
        max_slope_deg=max_slope,
    )

    if res.success:
        assert len(res.waypoints) > 0
        for wp in res.waypoints:
            r, c = wp["row"], wp["col"]
            # Invariant 1: Never enters hazard cell
            assert not hazard_grid[r, c], f"Waypoint at ({r}, {c}) hit hazard cell!"
            # Invariant 2: Never exceeds maximum slope
            slope_val = slope_grid[r, c]
            assert (
                slope_val <= max_slope
            ), f"Waypoint at ({r}, {c}) slope {slope_val} > {max_slope}!"
            # Invariant 3: Battery >= survival minimum
            bat_val = wp["battery_wh"]
            assert bat_val >= profile.min_survival_wh, f"Battery {bat_val} < survival minimum!"
    else:
        # If infeasible, explanation must identify why
        assert res.explanation is not None
        assert len(res.explanation_text) > 0
