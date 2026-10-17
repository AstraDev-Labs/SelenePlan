"""API routes for terrain products, stats, and synchronous analysis."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from selene_auth.dependencies import get_current_principal
from selene_auth.principal import Principal
from terrain_service.models import (
    ProductRegistry,
    get_product_registry,
)
from terrain_service.worker.terrain_pipeline import TerrainPipeline

router = APIRouter()


class ProductMetadataResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    storage_uri: str
    sha256: str
    size_bytes: int
    dimensions: dict[str, int]
    resolution_m: float
    crs_wkt: str
    parent_dataset_version_id: uuid.UUID
    parameters: dict[str, Any]
    created_at: str


class ProductStatsResponse(BaseModel):
    id: uuid.UUID
    kind: str
    stats: dict[str, Any]


class AnalyzeRequest(BaseModel):
    dataset_version_id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    elevation_grid: list[list[float]]
    resolution_m: float = Field(default=10.0, gt=0)
    origin_x: float = 0.0
    origin_y: float = 0.0
    max_slope_deg: float | None = Field(default=None, ge=0, le=90)
    max_roughness: float | None = Field(default=None, ge=0)
    nodata_is_hazard: bool = True
    tile_size: int = Field(default=256, ge=16)


class AnalyzeResponse(BaseModel):
    dataset_version_id: uuid.UUID
    products: dict[str, ProductMetadataResponse]
    metrics: dict[str, Any]


def check_project_access(principal: Principal, product_project_id: uuid.UUID) -> None:
    """Ensure principal is authorized to access products for the given project."""
    if "admin" in principal.roles or "auditor" in principal.roles:
        return

    prod_proj_str = str(product_project_id)
    user_proj = principal.claims.get("project_id")
    if user_proj and str(user_proj) == prod_proj_str:
        return

    user_projects = principal.claims.get("projects", [])
    if isinstance(user_projects, list) and prod_proj_str in [str(p) for p in user_projects]:
        return

    if "service" in principal.roles:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access denied: principal is not a member of project {product_project_id}",
    )


@router.get("/v1/products/{product_id}", response_model=ProductMetadataResponse)
async def get_product_metadata(
    product_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ProductRegistry, Depends(get_product_registry)],
) -> ProductMetadataResponse:
    """Retrieve metadata and storage URIs for a terrain product."""
    record = registry.get(product_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found.",
        )

    check_project_access(principal, record.project_id)

    return ProductMetadataResponse(
        id=record.id,
        org_id=record.org_id,
        project_id=record.project_id,
        kind=record.kind,
        storage_uri=record.storage_uri,
        sha256=record.sha256,
        size_bytes=record.size_bytes,
        dimensions={"width": record.width, "height": record.height},
        resolution_m=record.resolution_m,
        crs_wkt=record.crs_wkt,
        parent_dataset_version_id=record.parent_dataset_version_id,
        parameters=record.parameters,
        created_at=record.created_at.isoformat(),
    )


@router.get("/v1/products/{product_id}/stats", response_model=ProductStatsResponse)
async def get_product_stats(
    product_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ProductRegistry, Depends(get_product_registry)],
) -> ProductStatsResponse:
    """Retrieve summary statistics (min, max, mean, percentiles, hazard fraction) for a product."""
    record = registry.get(product_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found.",
        )

    check_project_access(principal, record.project_id)

    return ProductStatsResponse(
        id=record.id,
        kind=record.kind,
        stats=record.stats,
    )


@router.post(
    "/internal/v1/terrain/analyze",
    status_code=status.HTTP_200_OK,
    response_model=AnalyzeResponse,
)
async def analyze_terrain_synchronous(
    payload: AnalyzeRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ProductRegistry, Depends(get_product_registry)],
) -> AnalyzeResponse:
    """Synchronously derive slope, aspect, roughness, and hazard products for small AOIs."""
    elevation_arr = np.array(payload.elevation_grid, dtype=np.float32)
    pipeline = TerrainPipeline(registry=registry)

    result = pipeline.run_analysis(
        elevation=elevation_arr,
        dataset_version_id=payload.dataset_version_id,
        org_id=payload.org_id,
        project_id=payload.project_id,
        resolution_m=payload.resolution_m,
        origin_x=payload.origin_x,
        origin_y=payload.origin_y,
        max_slope_deg=payload.max_slope_deg,
        max_roughness=payload.max_roughness,
        nodata_is_hazard=payload.nodata_is_hazard,
        tile_size=payload.tile_size,
    )

    out_products: dict[str, ProductMetadataResponse] = {}
    for kind, rec in result.products.items():
        out_products[kind] = ProductMetadataResponse(
            id=rec.id,
            org_id=rec.org_id,
            project_id=rec.project_id,
            kind=rec.kind,
            storage_uri=rec.storage_uri,
            sha256=rec.sha256,
            size_bytes=rec.size_bytes,
            dimensions={"width": rec.width, "height": rec.height},
            resolution_m=rec.resolution_m,
            crs_wkt=rec.crs_wkt,
            parent_dataset_version_id=rec.parent_dataset_version_id,
            parameters=rec.parameters,
            created_at=rec.created_at.isoformat(),
        )

    return AnalyzeResponse(
        dataset_version_id=result.dataset_version_id,
        products=out_products,
        metrics=result.metrics,
    )
