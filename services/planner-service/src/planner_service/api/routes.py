"""FastAPI router for planner-service endpoints."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from planner_service.energy.model import RoverEnergyProfile
from planner_service.ranking.ranker import rank_landing_sites
from planner_service.traverse.planner import plan_traverse
from pydantic import BaseModel

router = APIRouter(prefix="/v1/planner", tags=["Planner & Traverse"])

# In-memory storage for rankings and routes
RANKING_STORE: dict[str, dict[str, Any]] = {}
ROUTE_STORE: dict[str, dict[str, Any]] = {}


class RankingRequest(BaseModel):
    aoi_id: str = "shackleton-polar-01"
    footprint_radius_m: float = 40.0
    max_slope_deg: float = 12.0
    min_lit_fraction: float = 0.40
    min_earth_vis_fraction: float = 0.40
    weights: dict[str, float] | None = None


class RouteRequest(BaseModel):
    start_point: tuple[int, int] = (10, 10)  # row, col
    goal_point: tuple[int, int] = (40, 40)
    max_slope_deg: float = 15.0
    max_blackout_hours: float = 24.0
    require_comms_checkpoints: bool = False
    profile_override: RoverEnergyProfile | None = None


class WhatIfRequest(BaseModel):
    base_route_id: str
    max_slope_deg: float | None = None
    max_blackout_hours: float | None = None
    battery_capacity_wh: float | None = None


@router.post("/rankings", status_code=201)
async def generate_rankings(payload: RankingRequest) -> dict[str, Any]:
    """Generate landing site rankings with hard constraints and soft scores."""
    # Synthetic 50x50 test AOI grids
    size = 50
    y, x = np.ogrid[:size, :size]
    dist = np.sqrt((x - 25) ** 2 + (y - 25) ** 2)

    slope_grid = 3.0 + 15.0 * (dist / 25.0)
    hazard_grid = (dist < 10) | (slope_grid > payload.max_slope_deg)
    lit_fraction_grid = np.clip(1.0 - (dist / 35.0), 0.0, 1.0)
    earth_vis_grid = np.ones((size, size), dtype=np.float32) * 0.85
    roughness_grid = slope_grid * 0.08
    longest_dark_grid = (1.0 - lit_fraction_grid) * 300.0

    res = rank_landing_sites(
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        lit_fraction_grid=lit_fraction_grid,
        earth_vis_grid=earth_vis_grid,
        roughness_grid=roughness_grid,
        longest_dark_grid=longest_dark_grid,
        footprint_radius_m=payload.footprint_radius_m,
        max_slope_deg=payload.max_slope_deg,
        min_lit_fraction=payload.min_lit_fraction,
        min_earth_vis_fraction=payload.min_earth_vis_fraction,
        weights=payload.weights,
    )

    ranking_id = f"rank-{uuid.uuid4().hex[:8]}"
    RANKING_STORE[ranking_id] = {
        "ranking_id": ranking_id,
        "aoi_id": payload.aoi_id,
        "total_evaluated": res.total_evaluated,
        "ranked_count": len(res.ranked_sites),
        "rejected_count": len(res.rejected_sites),
        "ranked_sites": [vars(s) for s in res.ranked_sites],
        "rejected_sites": [vars(s) for s in res.rejected_sites],
    }

    return {
        "ranking_id": ranking_id,
        "total_evaluated": res.total_evaluated,
        "ranked_count": len(res.ranked_sites),
        "rejected_count": len(res.rejected_sites),
        "top_site": vars(res.top_site) if res.top_site else None,
    }


@router.get("/rankings/{ranking_id}")
async def get_ranking(ranking_id: str) -> dict[str, Any]:
    """Retrieve landing site rankings, score breakdown, and rejected candidates."""
    if ranking_id not in RANKING_STORE:
        raise HTTPException(status_code=404, detail=f"Ranking {ranking_id} not found")
    return RANKING_STORE[ranking_id]


@router.post("/routes", status_code=201)
async def generate_route(payload: RouteRequest) -> dict[str, Any]:
    """Compute time-expanded traverse plan respecting energy, slope, and comms."""
    size = 50
    t_steps = 48
    elev_grid = np.zeros((size, size), dtype=np.float32)
    slope_grid = np.ones((size, size), dtype=np.float32) * 5.0
    hazard_grid = np.zeros((size, size), dtype=bool)

    illum = np.ones((t_steps, size, size), dtype=bool)
    earth_vis = np.ones((t_steps, size, size), dtype=bool)
    sun_elevs = [1.54] * t_steps

    res = plan_traverse(
        start_rc=payload.start_point,
        goal_rc=payload.goal_point,
        elevation_grid=elev_grid,
        slope_grid=slope_grid,
        hazard_grid=hazard_grid,
        illum_timestack=illum,
        earth_vis_timestack=earth_vis,
        sun_elev_series=sun_elevs,
        profile=payload.profile_override,
        max_slope_deg=payload.max_slope_deg,
        max_blackout_hours=payload.max_blackout_hours,
        require_comms_checkpoints=payload.require_comms_checkpoints,
    )

    route_id = f"route-{uuid.uuid4().hex[:8]}"
    ROUTE_STORE[route_id] = {
        "route_id": route_id,
        "success": res.success,
        "waypoints": res.waypoints,
        "total_distance_m": res.total_distance_m,
        "total_duration_hours": res.total_duration_hours,
        "min_battery_wh": res.min_battery_wh,
        "final_battery_wh": res.final_battery_wh,
        "explanation": res.explanation,
        "explanation_text": res.explanation_text,
    }

    return {
        "route_id": route_id,
        "success": res.success,
        "total_distance_m": res.total_distance_m,
        "total_duration_hours": res.total_duration_hours,
        "min_battery_wh": res.min_battery_wh,
        "explanation_text": res.explanation_text,
    }


@router.get("/routes/{route_id}")
async def get_route(route_id: str) -> dict[str, Any]:
    """Retrieve traverse plan waypoints, metrics, and explanations."""
    if route_id not in ROUTE_STORE:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return ROUTE_STORE[route_id]


@router.post("/whatif", status_code=200)
async def whatif_analysis(payload: WhatIfRequest) -> dict[str, Any]:
    """Re-plan against base scenario with parameter overrides and return comparison."""
    if payload.base_route_id not in ROUTE_STORE:
        raise HTTPException(status_code=404, detail=f"Base route {payload.base_route_id} not found")

    base = ROUTE_STORE[payload.base_route_id]

    # Re-plan with modified parameters
    profile = RoverEnergyProfile()
    if payload.battery_capacity_wh:
        profile.battery_capacity_wh = payload.battery_capacity_wh

    res = plan_traverse(
        start_rc=(10, 10),
        goal_rc=(40, 40),
        elevation_grid=np.zeros((50, 50)),
        slope_grid=np.ones((50, 50)) * 5.0,
        hazard_grid=np.zeros((50, 50), dtype=bool),
        illum_timestack=np.ones((48, 50, 50), dtype=bool),
        earth_vis_timestack=np.ones((48, 50, 50), dtype=bool),
        sun_elev_series=[1.54] * 48,
        profile=profile,
        max_slope_deg=payload.max_slope_deg or 15.0,
        max_blackout_hours=payload.max_blackout_hours or 24.0,
    )

    alt_id = f"route-alt-{uuid.uuid4().hex[:8]}"
    ROUTE_STORE[alt_id] = {
        "route_id": alt_id,
        "success": res.success,
        "waypoints": res.waypoints,
        "total_distance_m": res.total_distance_m,
        "total_duration_hours": res.total_duration_hours,
        "min_battery_wh": res.min_battery_wh,
        "final_battery_wh": res.final_battery_wh,
        "explanation": res.explanation,
        "explanation_text": res.explanation_text,
    }

    comparison = {
        "base_route_id": payload.base_route_id,
        "alternative_route_id": alt_id,
        "base_distance_m": base["total_distance_m"],
        "alt_distance_m": res.total_distance_m,
        "delta_distance_m": res.total_distance_m - base["total_distance_m"],
        "base_duration_h": base["total_duration_hours"],
        "alt_duration_h": res.total_duration_hours,
        "delta_duration_h": res.total_duration_hours - base["total_duration_hours"],
        "base_min_battery_wh": base["min_battery_wh"],
        "alt_min_battery_wh": res.min_battery_wh,
    }

    return comparison


@router.get("/compare")
async def compare_routes(
    a: str = Query(..., description="Route ID A"),
    b: str = Query(..., description="Route ID B"),
) -> dict[str, Any]:
    """Compare two routes side-by-side."""
    if a not in ROUTE_STORE:
        raise HTTPException(status_code=404, detail=f"Route {a} not found")
    if b not in ROUTE_STORE:
        raise HTTPException(status_code=404, detail=f"Route {b} not found")

    r_a = ROUTE_STORE[a]
    r_b = ROUTE_STORE[b]

    return {
        "route_a": {
            "id": a,
            "distance_m": r_a["total_distance_m"],
            "duration_h": r_a["total_duration_hours"],
            "min_battery_wh": r_a["min_battery_wh"],
            "success": r_a["success"],
        },
        "route_b": {
            "id": b,
            "distance_m": r_b["total_distance_m"],
            "duration_h": r_b["total_duration_hours"],
            "min_battery_wh": r_b["min_battery_wh"],
            "success": r_b["success"],
        },
        "delta": {
            "distance_m": r_b["total_distance_m"] - r_a["total_distance_m"],
            "duration_h": r_b["total_duration_hours"] - r_a["total_duration_hours"],
            "min_battery_wh": r_b["min_battery_wh"] - r_a["min_battery_wh"],
        },
    }
