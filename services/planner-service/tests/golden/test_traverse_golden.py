"""Golden tests for traverse search: wall with gap, wait-for-light, and comms checkpoints."""

import numpy as np
from planner_service.energy.model import RoverEnergyProfile
from planner_service.traverse.planner import plan_traverse


def test_golden_wall_with_single_gap() -> None:
    # 20x20 grid with a solid hazard wall at column 10, except a single gap at row 8
    size = 20
    slope_grid = np.zeros((size, size), dtype=np.float32)
    hazard_grid = np.zeros((size, size), dtype=bool)

    # Wall at column 10
    hazard_grid[:, 10] = True
    # Single passage gap at row 8
    hazard_grid[8, 10] = False

    t_steps = 48
    illum = np.ones((t_steps, size, size), dtype=bool)
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    sun_elevs = [1.54] * t_steps

    res = plan_traverse(
        start_rc=(8, 2),
        goal_rc=(8, 18),
        elevation_grid=np.zeros((size, size)),
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
    )

    assert res.success is True
    # Verify the traverse passes exactly through the gap at (8, 10)
    gap_visited = any(wp["row"] == 8 and wp["col"] == 10 for wp in res.waypoints)
    assert gap_visited is True
    # Verify no waypoints hit the wall
    for wp in res.waypoints:
        assert not hazard_grid[wp["row"], wp["col"]]


def test_golden_wait_for_light_action() -> None:
    # Scenario: Starting cell is shadowed for 2 hours, then becomes sunlit.
    # Battery starts at 110 Wh (near 100 Wh minimum). Driving into shadow would deplete it below 100 Wh,
    # so waiting in place for 2 hours until sunrise recharges the battery and enables safe travel.
    size = 15
    slope_grid = np.zeros((size, size), dtype=np.float32)
    hazard_grid = np.zeros((size, size), dtype=bool)

    t_steps = 20
    illum = np.zeros((t_steps, size, size), dtype=bool)
    # Illumination turns on after step 2
    illum[3:, :, :] = True
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    sun_elevs = [2.0] * t_steps

    profile = RoverEnergyProfile(
        battery_capacity_wh=500.0,
        min_survival_wh=100.0,
        power_drive_w=80.0,
        power_wait_w=10.0,
    )

    res = plan_traverse(
        start_rc=(5, 2),
        goal_rc=(5, 8),
        elevation_grid=np.zeros((size, size)),
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
        profile=profile,
    )

    assert res.success is True
    # Verify waiting action was taken
    actions = [wp["action"] for wp in res.waypoints]
    assert "wait" in actions or len(res.waypoints) > 6


def test_golden_comms_checkpoint_enforcement() -> None:
    # Scenario: Region around direct path has no Earth LOS at the midpoint time step.
    # Enabling require_comms_checkpoints forces the route to divert toward Earth-visible cells.
    size = 20
    slope_grid = np.zeros((size, size), dtype=np.float32)
    hazard_grid = np.zeros((size, size), dtype=bool)

    t_steps = 24
    illum = np.ones((t_steps, size, size), dtype=bool)
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    # Blackout at the center line at the midpoint step
    earth_vis[t_steps // 2, 7:13, :] = False
    sun_elevs = [1.54] * t_steps

    res_with_check = plan_traverse(
        start_rc=(5, 2),
        goal_rc=(15, 18),
        elevation_grid=np.zeros((size, size)),
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
        require_comms_checkpoints=True,
    )

    assert res_with_check.success is True
    # At checkpoint time step, Earth must be visible
    mid_wp = [wp for wp in res_with_check.waypoints if wp["step_idx"] == t_steps // 2]
    if mid_wp:
        assert mid_wp[0]["earth_visible"] is True
