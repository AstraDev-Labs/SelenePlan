"""FastAPI routes for illumination-service."""

from __future__ import annotations

import base64
import math
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from illumination_service.storage.slice_cache import default_slice_cache
from illumination_service.storage.zarr_store import ZarrCubeStore
from selene_auth import Principal, get_current_principal

router = APIRouter(prefix="/v1")
store = ZarrCubeStore()


class AnalyzeRequest(BaseModel):
    dataset_version_id: str
    obs_lat_deg: float = Field(..., ge=-90.0, le=90.0)
    obs_lon_deg: float = Field(..., ge=-180.0, le=180.0)
    start_iso: str
    end_iso: str
    time_step_s: float = Field(default=3600.0, gt=0.0)
    azimuth_bins: int = Field(default=72, ge=8, le=720)
    max_ray_dist_m: float = Field(default=20000.0, gt=0.0)
    sun_model: str = Field(default="point")


@router.get("/products/{product_id}")
async def get_product_metadata(
    product_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve metadata, parameters, and summary statistics for an illumination product."""
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
async def get_product_slice(
    product_id: str,
    t: int = Query(..., ge=0, description="Time step index"),
    format: str = Query("json", description="Output format: 'json' or 'png'"),
    principal: Principal = Depends(get_current_principal),
) -> Any:
    """Retrieve a 2D spatial illumination slice for a specific time step."""
    # Check cache
    cached_png = default_slice_cache.get_slice_bytes(product_id, t)
    if format == "png" and cached_png:
        return Response(content=cached_png, media_type="image/png")

    try:
        slice_arr = store.read_slice(product_id, t)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )
    except IndexError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    png_bytes = default_slice_cache.render_slice_png(slice_arr)
    default_slice_cache.put_slice_bytes(product_id, t, png_bytes)

    if format == "png":
        return Response(content=png_bytes, media_type="image/png")

    meta = store.load_metadata(product_id)
    timestamp_iso = meta.time_axis_iso[t] if t < len(meta.time_axis_iso) else ""

    return {
        "product_id": product_id,
        "time_index": t,
        "timestamp_iso": timestamp_iso,
        "rows": slice_arr.shape[0],
        "cols": slice_arr.shape[1],
        "lit_count": int(np.sum(slice_arr)),
        "total_cells": int(slice_arr.size),
        "lit_fraction": float(np.mean(slice_arr)),
        "mask_base64": base64.b64encode(png_bytes).decode("ascii"),
    }


@router.get("/products/{product_id}/timeseries")
async def get_point_timeseries(
    product_id: str,
    x: float = Query(..., description="Projected Easting (m) or Column index"),
    y: float = Query(..., description="Projected Northing (m) or Row index"),
    crs: str = Query("grid", description="Coordinate frame: 'grid' (row/col) or 'polar_stereo'"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve 1D point time-series showing lit/dark states across time."""
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
        # Map from projected bounds [minx, miny, maxx, maxy] to row/col
        minx, miny, maxx, maxy = meta.bounds
        res = meta.resolution_m
        col = int(math.floor((x - minx) / res))
        row = int(math.floor((maxy - y) / res))

    try:
        series = store.read_timeseries(product_id, row, col)
    except IndexError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "product_id": product_id,
        "row": row,
        "col": col,
        "total_steps": len(series),
        "lit_steps": int(np.sum(series)),
        "lit_fraction": float(np.mean(series)),
        "series": [bool(v) for v in series],
    }


@router.get("/products/{product_id}/stats")
async def get_region_stats(
    product_id: str,
    geom: str = Query("aoi", description="Sub-region geometry (GeoJSON or 'aoi')"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Retrieve illumination summary metrics for an AOI or subregion."""
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
