"""Integration test for the replay CLI tool.

Per services/provenance-service/SPEC.md & Phase 5 Task 5.8:
- Replay reproduces small plan within tolerance.
- Deliberately altered input hash causes replay to fail loudly.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from planner_service.energy.model import RoverEnergyProfile
from planner_service.traverse.planner import plan_traverse

from tools.replay import InputHashMismatchError, replay_plan


def test_replay_plan_exact_match_and_hash_tamper_detection() -> None:
    size = 20
    slope_grid = np.zeros((size, size), dtype=np.float32)
    hazard_grid = np.zeros((size, size), dtype=bool)
    hazard_grid[:, 10] = True
    hazard_grid[8, 10] = False  # single gap

    t_steps = 48
    illum = np.ones((t_steps, size, size), dtype=bool)
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    sun_elevs = [1.54] * t_steps
    profile = RoverEnergyProfile()

    # 1. Execute original traverse plan
    orig_res = plan_traverse(
        start_rc=(8, 2),
        goal_rc=(8, 18),
        elevation_grid=np.zeros((size, size)),
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
        profile=profile,
        max_slope_deg=15.0,
    )
    assert orig_res.success is True

    # Compute raw bytes and hashes of inputs
    elev_bytes = np.zeros((size, size)).tobytes()
    slope_bytes = slope_grid.tobytes()
    hazard_bytes = hazard_grid.tobytes()
    illum_bytes = illum.tobytes()
    earth_bytes = earth_vis.tobytes()

    elev_hash = hashlib.sha256(elev_bytes).hexdigest()
    slope_hash = hashlib.sha256(slope_bytes).hexdigest()
    hazard_hash = hashlib.sha256(hazard_bytes).hexdigest()
    illum_hash = hashlib.sha256(illum_bytes).hexdigest()
    earth_hash = hashlib.sha256(earth_bytes).hexdigest()

    # 2. Build replay-spec
    replay_spec = {
        "schema": "selene.replay.v1",
        "artifact_id": "art-plan-shackleton-alpha",
        "parameters": {
            "start_rc": [8, 2],
            "goal_rc": [8, 18],
            "max_slope_deg": 15.0,
            "require_comms_checkpoints": False,
        },
        "manifest": {
            "waypoints": orig_res.waypoints,
            "total_distance_m": orig_res.total_distance_m,
            "total_duration_hours": orig_res.total_duration_hours,
        },
        "source_inputs": [
            {"id": "inp-elev", "kind": "elevation", "sha256": elev_hash},
            {"id": "inp-slope", "kind": "slope", "sha256": slope_hash},
            {"id": "inp-hazard", "kind": "hazard", "sha256": hazard_hash},
            {"id": "inp-illum", "kind": "illumination", "sha256": illum_hash},
            {"id": "inp-earth", "kind": "earth_vis", "sha256": earth_hash},
        ],
    }

    input_grids = {
        "elevation": np.zeros((size, size)),
        "slope": slope_grid,
        "hazard": hazard_grid,
        "illumination": illum,
        "earth_vis": earth_vis,
        "sun_elev_series": sun_elevs,
        "raw_bytes": {
            "inp-elev": elev_bytes,
            "inp-slope": slope_bytes,
            "inp-hazard": hazard_bytes,
            "inp-illum": illum_bytes,
            "inp-earth": earth_bytes,
        },
    }

    # 3. Test exact replay matches within tolerance
    success, msg = replay_plan(replay_spec, input_grids)
    assert success is True
    assert "Replay successful" in msg

    # 4. Deliberately alter an input hash -> replay MUST fail loudly!
    tampered_grids = dict(input_grids)
    tampered_bytes = dict(input_grids["raw_bytes"])
    # Modify one byte in hazard input
    tampered_bytes["inp-hazard"] = b"\x01" + hazard_bytes[1:]
    tampered_grids["raw_bytes"] = tampered_bytes

    with pytest.raises(InputHashMismatchError, match="SHA-256 mismatch"):
        replay_plan(replay_spec, tampered_grids)
