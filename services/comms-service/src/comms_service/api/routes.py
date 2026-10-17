"""FastAPI routes for comms-service."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from comms_service.storage.zarr_store import ZarrCommsStore
from comms_service.windows.extractor import (
    compute_blackout_stats,
    extract_visibility_windows,
)
from comms_service.worker.pipeline import CommsPipeline
from selene_auth import Principal, get_current_principal

router = APIRouter(prefix="/v1")
store = ZarrCommsStore()
pipeline = CommsPipeline(cube_store=store)


class WaypointItem(BaseModel):
    x_m: float
    y_m: float
    time_index: int = Field(default=0, ge=0)


class AlongPathRequest(BaseModel):
    waypoints: list[WaypointItem] = Field(..., max_length=2000)


@router.get("/products/{product_id}")
async def get_product_metadata(
    product_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve metadata and parameters for a communications visibility product."""
    try:
        meta = store.load_metadata(product_id)
        return {
            "product_id": meta.product_id,
            "dataset_version_id": meta.dataset_version_id,
            "crs_wkt": meta.crs_wkt,
            "resolution_m": meta.resolution_m,
            "bounds": meta.bounds,
            "shape": meta.shape,
            "time_axis": meta.time_axis_iso,
            "time_step_s": meta.time_step_s,
            "azimuth_bins": meta.azimuth_bins,
            "params": meta.params,
            "summary_stats": meta.summary_stats,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )


@router.get("/products/{product_id}/slice")
async def get_visibility_slice(
    product_id: str,
    t: int = Query(..., ge=0, description="Time step index"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve a 2D spatial visibility mask for a given time step."""
    try:
        slice_arr = store.read_slice(product_id, t)
        meta = store.load_metadata(product_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )
    except IndexError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    timestamp_iso = meta.time_axis_iso[t] if t < len(meta.time_axis_iso) else ""

    return {
        "product_id": product_id,
        "time_index": t,
        "timestamp_iso": timestamp_iso,
        "rows": slice_arr.shape[0],
        "cols": slice_arr.shape[1],
        "visible_count": int(np.sum(slice_arr)),
        "total_cells": int(slice_arr.size),
        "visible_fraction": float(np.mean(slice_arr)),
    }


@router.get("/products/{product_id}/windows")
async def get_point_visibility_windows(
    product_id: str,
    x: float = Query(..., description="Projected Easting (m) or Column index"),
    y: float = Query(..., description="Projected Northing (m) or Row index"),
    crs: str = Query("grid", description="Coordinate frame: 'grid' (row/col) or 'polar_stereo'"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve line-of-sight communication windows and blackout statistics for a point."""
    try:
        meta = store.load_metadata(product_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )

    if crs == "grid":
        row = int(y)
        col = int(x)
    else:
        minx, miny, maxx, maxy = meta.bounds
        res = meta.resolution_m
        col = int(math.floor((x - minx) / res))
        row = int(math.floor((maxy - y) / res))

    try:
        series = store.read_timeseries(product_id, row, col)
    except IndexError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    windows = extract_visibility_windows(series, meta.time_axis_iso, meta.time_step_s)
    stats = compute_blackout_stats(series, meta.time_step_s)

    return {
        "product_id": product_id,
        "row": row,
        "col": col,
        "total_steps": len(series),
        "visible_fraction": stats["visible_fraction"],
        "longest_blackout_hours": stats["longest_blackout_hours"],
        "longest_window_hours": stats["longest_window_hours"],
        "total_windows": len(windows),
        "windows": [
            {
                "start_iso": w.start_iso,
                "end_iso": w.end_iso,
                "duration_hours": w.duration_hours,
                "steps_count": w.steps_count,
            }
            for w in windows
        ],
    }


@router.post("/products/{product_id}/along-path")
async def evaluate_along_path(
    product_id: str,
    req: AlongPathRequest,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Evaluate communication line-of-sight visibility for an arbitrary time-stamped path."""
    try:
        waypoints_dicts = [wp.model_dump() for wp in req.waypoints]
        evaluated = pipeline.evaluate_along_path(product_id, waypoints_dicts)
        return {
            "product_id": product_id,
            "total_waypoints": len(evaluated),
            "visible_waypoints": sum(1 for w in evaluated if w["is_visible"]),
            "waypoints": evaluated,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )


@router.get("/products/{product_id}/stats")
async def get_comms_stats(
    product_id: str,
    geom: str = Query("aoi", description="Sub-region geometry (GeoJSON or 'aoi')"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve communication visibility summary statistics for the AOI."""
    try:
        meta = store.load_metadata(product_id)
        return {
            "product_id": product_id,
            "region": geom,
            "summary_stats": meta.summary_stats,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )
