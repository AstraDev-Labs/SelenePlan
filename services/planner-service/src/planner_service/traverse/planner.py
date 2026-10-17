"""Time-expanded A* traverse planner with multi-physics constraints and structured explanations."""

import heapq
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from planner_service.energy.model import RoverEnergyProfile, compute_step_energy


@dataclass(order=True)
class SearchNode:
    priority: float
    g_cost: float = field(compare=False)
    row: int = field(compare=False)
    col: int = field(compare=False)
    step_idx: int = field(compare=False)
    battery_wh: float = field(compare=False)
    blackout_hours: float = field(compare=False)
    path: list[dict[str, Any]] = field(compare=False, default_factory=list)


@dataclass
class TraversePlanResult:
    success: bool
    waypoints: list[dict[str, Any]]
    total_distance_m: float
    total_duration_hours: float
    min_battery_wh: float
    final_battery_wh: float
    explanation: dict[str, Any]
    explanation_text: str


def plan_traverse(
    start_rc: tuple[int, int],
    goal_rc: tuple[int, int],
    elevation_grid: np.ndarray,
    slope_grid: np.ndarray,
    hazard_grid: np.ndarray,
    illum_timestack: np.ndarray,  # [T, H, W] bool (True = lit)
    earth_vis_timestack: np.ndarray,  # [T, H, W] bool (True = visible)
    sun_elev_series: list[float],  # [T] solar elevation angles in degrees
    profile: RoverEnergyProfile | None = None,
    resolution_m: float = 20.0,
    time_step_hours: float = 1.0,
    max_slope_deg: float = 15.0,
    max_blackout_hours: float = 24.0,
    require_comms_checkpoints: bool = False,
    max_search_states: int = 15000,
) -> TraversePlanResult:
    """Execute time-expanded A* search respecting terrain, illumination, battery, and Earth LOS constraints."""
    if profile is None:
        profile = RoverEnergyProfile()

    h, w = slope_grid.shape
    t_max = illum_timestack.shape[0]

    sr, sc = start_rc
    gr, gc = goal_rc

    # 1. Start / Goal Feasibility Pre-checks
    if hazard_grid[sr, sc]:
        text = f"Start position ({sr}, {sc}) is located inside a hazardous cell."
        return TraversePlanResult(
            success=False,
            waypoints=[],
            total_distance_m=0.0,
            total_duration_hours=0.0,
            min_battery_wh=profile.battery_capacity_wh,
            final_battery_wh=profile.battery_capacity_wh,
            explanation={
                "dominant_violation": "START_HAZARD",
                "location": [sr, sc],
                "time_step": 0,
            },
            explanation_text=text,
        )

    if hazard_grid[gr, gc]:
        text = f"Goal position ({gr}, {gc}) is located inside a hazardous cell."
        return TraversePlanResult(
            success=False,
            waypoints=[],
            total_distance_m=0.0,
            total_duration_hours=0.0,
            min_battery_wh=profile.battery_capacity_wh,
            final_battery_wh=profile.battery_capacity_wh,
            explanation={"dominant_violation": "GOAL_HAZARD", "location": [gr, gc], "time_step": 0},
            explanation_text=text,
        )

    # Admissible Euclidean heuristic
    rover_speed_mps = 0.1  # nominal speed
    speed_m_per_hr = rover_speed_mps * 3600.0

    def heuristic(r: int, c: int) -> float:
        dist_m = math.hypot(r - gr, c - gc) * resolution_m
        return dist_m / speed_m_per_hr  # travel time in hours

    # 8-connected movement deltas
    moves = [
        (-1, 0, 1.0),
        (1, 0, 1.0),
        (0, -1, 1.0),
        (0, 1, 1.0),
        (-1, -1, math.sqrt(2)),
        (-1, 1, math.sqrt(2)),
        (1, -1, math.sqrt(2)),
        (1, 1, math.sqrt(2)),
        (0, 0, 0.0),  # Wait / charge action
    ]

    initial_point = {
        "step_idx": 0,
        "row": sr,
        "col": sc,
        "x_m": float((sc - w / 2) * resolution_m),
        "y_m": float((h / 2 - sr) * resolution_m),
        "t_hours": 0.0,
        "battery_wh": profile.battery_capacity_wh,
        "sun_elev_deg": float(sun_elev_series[0]) if sun_elev_series else 1.5,
        "is_lit": bool(illum_timestack[0, sr, sc]),
        "earth_visible": bool(earth_vis_timestack[0, sr, sc]),
        "action": "start",
    }

    initial_node = SearchNode(
        priority=heuristic(sr, sc),
        g_cost=0.0,
        row=sr,
        col=sc,
        step_idx=0,
        battery_wh=profile.battery_capacity_wh,
        blackout_hours=0.0,
        path=[initial_point],
    )

    open_set: list[SearchNode] = [initial_node]
    # Visited state table: (row, col, step_idx, battery_bucket)
    # Quantize battery into 20 Wh buckets to prune dominated states
    visited: set[tuple[int, int, int, int]] = set()

    states_evaluated = 0
    worst_violation = {"dominant_violation": "NO_FEASIBLE_PATH", "reason": "Search space exhausted"}

    while open_set and states_evaluated < max_search_states:
        curr = heapq.heappop(open_set)
        states_evaluated += 1

        r, c, s_idx = curr.row, curr.col, curr.step_idx
        b_bucket = int(curr.battery_wh // 20.0)
        state_key = (r, c, s_idx, b_bucket)

        if state_key in visited:
            continue
        visited.add(state_key)

        # Check Goal Reached
        if r == gr and c == gc:
            # Plan Succeeded!
            total_dist = sum(
                math.hypot(
                    curr.path[i]["x_m"] - curr.path[i - 1]["x_m"],
                    curr.path[i]["y_m"] - curr.path[i - 1]["y_m"],
                )
                for i in range(1, len(curr.path))
            )
            min_bat = min(p["battery_wh"] for p in curr.path)

            return TraversePlanResult(
                success=True,
                waypoints=curr.path,
                total_distance_m=float(total_dist),
                total_duration_hours=float(curr.path[-1]["t_hours"]),
                min_battery_wh=float(min_bat),
                final_battery_wh=float(curr.path[-1]["battery_wh"]),
                explanation={"status": "FEASIBLE", "states_evaluated": states_evaluated},
                explanation_text="Traverse plan successfully computed satisfying all physical and operational constraints.",
            )

        # Explore actions
        for dr, dc, dist_factor in moves:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w):
                continue

            # Hard Constraint 1: Hazard mask
            if hazard_grid[nr, nc]:
                worst_violation = {
                    "dominant_violation": "TERRAIN_HAZARD",
                    "location": [nr, nc],
                    "time_step": s_idx,
                    "reason": f"Traverse blocked by terrain hazard at grid ({nr}, {nc})",
                }
                continue

            # Hard Constraint 2: Slope limit
            slope = float(slope_grid[nr, nc])
            if slope > max_slope_deg:
                worst_violation = {
                    "dominant_violation": "MAX_SLOPE_EXCEEDED",
                    "location": [nr, nc],
                    "time_step": s_idx,
                    "slope_deg": slope,
                    "reason": f"Slope {slope:.1f}° exceeds maximum traversable limit {max_slope_deg:.1f}°",
                }
                continue

            # Move duration based on rover speed (dist / speed) or time_step_hours if waiting
            move_duration_hours = (
                (dist_factor * resolution_m) / speed_m_per_hr
                if dist_factor > 0
                else time_step_hours
            )
            next_t_hours = curr.path[-1]["t_hours"] + move_duration_hours
            next_s_idx = min(t_max - 1, int(next_t_hours // time_step_hours))

            # Illumination & Earth LOS at next step
            is_lit = bool(illum_timestack[next_s_idx, nr, nc])
            earth_vis = bool(earth_vis_timestack[next_s_idx, nr, nc])
            sun_el = (
                float(sun_elev_series[next_s_idx]) if next_s_idx < len(sun_elev_series) else 1.5
            )

            # Energy step transition
            mode = "wait" if (dr == 0 and dc == 0) else "drive"
            next_battery, survival_violated = compute_step_energy(
                current_battery_wh=curr.battery_wh,
                mode=mode,
                sun_elev_deg=sun_el,
                duration_hours=move_duration_hours,
                profile=profile,
                is_lit=is_lit,
                slope_deg=slope if mode == "drive" else 0.0,
            )

            # Hard Constraint 3: Battery Survival Minimum
            if survival_violated:
                worst_violation = {
                    "dominant_violation": "ENERGY_DEPLETION",
                    "location": [nr, nc],
                    "time_step": next_s_idx,
                    "battery_wh": next_battery,
                    "reason": f"Battery charge dropped to {next_battery:.1f} Wh (below {profile.min_survival_wh:.1f} Wh survival limit)",
                }
                continue

            # Hard Constraint 4: Maximum Consecutive Blackout
            next_blackout = 0.0 if earth_vis else (curr.blackout_hours + time_step_hours)
            if next_blackout > max_blackout_hours:
                worst_violation = {
                    "dominant_violation": "COMMS_BLACKOUT_EXCEEDED",
                    "location": [nr, nc],
                    "time_step": next_s_idx,
                    "blackout_hours": next_blackout,
                    "reason": f"Consecutive Earth blackout duration {next_blackout:.1f}h exceeds limit {max_blackout_hours:.1f}h",
                }
                continue

            # Hard Constraint 5: Comms Checkpoint (if requested, must be visible at midpoint)
            if require_comms_checkpoints and next_s_idx == t_max // 2 and not earth_vis:
                worst_violation = {
                    "dominant_violation": "COMMS_CHECKPOINT_MISSED",
                    "location": [nr, nc],
                    "time_step": next_s_idx,
                    "reason": "Required communication checkpoint lacked Earth line-of-sight visibility",
                }
                continue

            # Step Cost (Time in hours + small slope penalty)
            move_cost = move_duration_hours + (slope / 45.0) * 0.01
            new_g = curr.g_cost + move_cost
            priority = new_g + heuristic(nr, nc)

            next_point = {
                "step_idx": next_s_idx,
                "row": nr,
                "col": nc,
                "x_m": float((nc - w / 2) * resolution_m),
                "y_m": float((h / 2 - nr) * resolution_m),
                "t_hours": next_t_hours,
                "battery_wh": float(next_battery),
                "sun_elev_deg": float(sun_el),
                "is_lit": is_lit,
                "earth_visible": earth_vis,
                "action": "wait" if (dr == 0 and dc == 0) else "drive",
            }

            next_node = SearchNode(
                priority=priority,
                g_cost=new_g,
                row=nr,
                col=nc,
                step_idx=next_s_idx,
                battery_wh=next_battery,
                blackout_hours=next_blackout,
                path=curr.path + [next_point],
            )
            heapq.heappush(open_set, next_node)

    # Infeasible: Build structured explanation
    explanation_text = f"Route rejected: {worst_violation.get('reason', 'Search space exhausted without finding feasible path')}."
    return TraversePlanResult(
        success=False,
        waypoints=[],
        total_distance_m=0.0,
        total_duration_hours=0.0,
        min_battery_wh=profile.battery_capacity_wh,
        final_battery_wh=profile.battery_capacity_wh,
        explanation=worst_violation,
        explanation_text=explanation_text,
    )
