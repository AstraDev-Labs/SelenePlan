#!/usr/bin/env python3
"""Replay CLI tool for reproducing and validating SelenePlan mission plans from lineage recipes.

Per services/provenance-service/SPEC.md & Phase 5 Task 5.8:
- Verifies input hashes against recorded provenance before execution.
- Deliberately altered input hash causes replay to fail loudly.
- Re-executes the deterministic search algorithm.
- Compares recomputed waypoints and metrics within documented tolerance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from planner_service.energy.model import RoverEnergyProfile
from planner_service.traverse.planner import plan_traverse


class ReplayVerificationError(Exception):
    pass


class InputHashMismatchError(ReplayVerificationError):
    pass


def verify_input_hashes(
    source_inputs: list[dict[str, Any]], input_data_map: dict[str, bytes]
) -> None:
    """Verify that all input data buffers match the exact recorded provenance hashes."""
    for inp in source_inputs:
        art_id = inp["id"]
        expected_hash = inp.get("sha256")
        if not expected_hash:
            continue

        if art_id not in input_data_map:
            raise ReplayVerificationError(
                f"Missing required input artifact data for '{art_id}' ({inp.get('kind')})"
            )

        data_bytes = input_data_map[art_id]
        actual_hash = hashlib.sha256(data_bytes).hexdigest()
        if actual_hash != expected_hash:
            raise InputHashMismatchError(
                f"Input artifact '{art_id}' SHA-256 mismatch! Actual: {actual_hash} != Expected: {expected_hash}"
            )


def replay_plan(
    replay_spec: dict[str, Any],
    input_grids: dict[str, Any],
    distance_tolerance_m: float = 0.01,
    duration_tolerance_hours: float = 0.001,
) -> tuple[bool, str]:
    """Recompute plan from replay spec and verify exact match with stored plan."""
    source_inputs = replay_spec.get("source_inputs", [])
    raw_bytes_map = input_grids.get("raw_bytes", {})

    # 1. Verify input integrity
    verify_input_hashes(source_inputs, raw_bytes_map)

    # 2. Extract parameters
    params = replay_spec.get("parameters", {})
    start_rc = tuple(params.get("start_rc", [8, 2]))
    goal_rc = tuple(params.get("goal_rc", [8, 18]))
    max_slope_deg = float(params.get("max_slope_deg", 15.0))
    require_comms = bool(params.get("require_comms_checkpoints", False))

    profile_dict = params.get("profile", {})
    profile = RoverEnergyProfile(**profile_dict) if profile_dict else RoverEnergyProfile()

    # 3. Retrieve rasters
    elevation_grid = input_grids["elevation"]
    slope_grid = input_grids["slope"]
    hazard_grid = input_grids["hazard"]
    illum_timestack = input_grids["illumination"]
    earth_vis_timestack = input_grids["earth_vis"]
    sun_elev_series = input_grids.get("sun_elev_series", [1.54] * illum_timestack.shape[0])

    # 4. Re-run traverse planner
    res = plan_traverse(
        start_rc=start_rc,
        goal_rc=goal_rc,
        elevation_grid=elevation_grid,
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum_timestack,
        earth_vis_timestack=earth_vis_timestack,
        sun_elev_series=sun_elev_series,
        profile=profile,
        max_slope_deg=max_slope_deg,
        require_comms_checkpoints=require_comms,
    )

    if not res.success:
        return False, f"Replay execution failed to compute feasible plan: {res.explanation}"

    # 5. Compare with stored plan in manifest or metadata
    manifest = replay_spec.get("manifest", {})
    stored_waypoints = manifest.get("waypoints", [])
    stored_dist_m = float(manifest.get("total_distance_m", 0.0))
    stored_dur_h = float(manifest.get("total_duration_hours", 0.0))

    if stored_waypoints:
        if len(res.waypoints) != len(stored_waypoints):
            return (
                False,
                f"Waypoint count mismatch: recomputed {len(res.waypoints)} != stored {len(stored_waypoints)}",
            )

        for i, (wp_re, wp_st) in enumerate(zip(res.waypoints, stored_waypoints)):
            if (wp_re["row"], wp_re["col"]) != (wp_st["row"], wp_st["col"]):
                return (
                    False,
                    f"Waypoint {i} position mismatch: recomputed ({wp_re['row']}, {wp_re['col']}) != stored ({wp_st['row']}, {wp_st['col']})",
                )

    if abs(res.total_distance_m - stored_dist_m) > distance_tolerance_m:
        return (
            False,
            f"Distance discrepancy: recomputed {res.total_distance_m:.3f}m != stored {stored_dist_m:.3f}m",
        )

    if abs(res.total_duration_hours - stored_dur_h) > duration_tolerance_hours:
        return (
            False,
            f"Duration discrepancy: recomputed {res.total_duration_hours:.4f}h != stored {stored_dur_h:.4f}h",
        )

    return (
        True,
        f"Replay successful! All {len(res.waypoints)} waypoints and metrics match stored plan.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay and verify SelenePlan mission plan from lineage spec"
    )
    parser.add_argument("replay_spec_file", help="Path to replay-spec.json")

    args = parser.parse_args()
    path = Path(args.replay_spec_file)
    if not path.exists():
        print(f"Error: file not found {path}", file=sys.stderr)
        sys.exit(2)

    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    print(f"Loaded replay spec for artifact {spec.get('artifact_id')}")


if __name__ == "__main__":
    main()
