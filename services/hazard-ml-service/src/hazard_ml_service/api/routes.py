"""REST API endpoints for hazard-ml-service."""

from __future__ import annotations

import base64
import uuid
from typing import Any
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from hazard_ml_service.registry.models import (
    GLOBAL_MODEL_REGISTRY,
    ModelCard,
    SecurityIntegrityError,
    ApprovalGateError,
)
from hazard_ml_service.inference.validator import validate_onnx_model, ModelValidationError
from hazard_ml_service.inference.engine import InferenceEngine
from hazard_ml_service.fusion.fuser import fuse_hazards
from hazard_ml_service.events.publisher import create_hazard_completed_event

router = APIRouter(prefix="/v1", tags=["Hazard ML & Registry"])

# In-memory product storage for detection and fused products
PRODUCT_STORE: dict[str, dict[str, Any]] = {}


class RegisterModelRequest(BaseModel):
    model_card: ModelCard
    onnx_base64: str | None = None
    created_by: str = "steward-001"
    signature: str | None = None


class ApproveModelRequest(BaseModel):
    approver_id: str = "steward-002"


class RunInferenceRequest(BaseModel):
    model_id: str = "crater_detector_v1"
    aoi_id: str = "shackleton-polar-01"
    image_grid: list[list[float]] | None = None  # Optional [H, W] float array
    conf_threshold: float = 0.75
    batch_size: int = 4


class FusionRequest(BaseModel):
    terrain_product_id: str = "terrain-prod-001"
    ml_product_id: str = "ml-prod-001"
    model_id: str = "crater_detector_v1"
    ml_confidence_threshold: float = 0.60
    terrain_hazard_grid: list[list[int]] | None = None  # 0 or 1
    ml_hazard_grid: list[list[float]] | None = None  # 0.0 to 1.0


@router.post("/models", status_code=201)
async def register_model(payload: RegisterModelRequest) -> dict[str, Any]:
    """Register a new candidate model in the registry (SEC-09)."""
    onnx_bytes = b""
    if payload.onnx_base64:
        try:
            onnx_bytes = base64.b64decode(payload.onnx_base64)
            # Validate ONNX graph and operator allowlist
            validate_onnx_model(onnx_bytes)
        except ModelValidationError as err:
            raise HTTPException(status_code=422, detail=f"Model validation error: {err}") from err
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {err}") from err

    record = GLOBAL_MODEL_REGISTRY.register_model(
        model_card=payload.model_card,
        onnx_bytes=onnx_bytes,
        created_by=payload.created_by,
        signature=payload.signature,
    )
    return record.model_dump()


@router.get("/models")
async def list_models() -> list[dict[str, Any]]:
    """List all registered models in the registry."""
    return [m.model_dump() for m in GLOBAL_MODEL_REGISTRY.list_models()]


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict[str, Any]:
    """Retrieve model details, metrics, and card."""
    try:
        return GLOBAL_MODEL_REGISTRY.get_model(model_id).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")


@router.post("/models/{model_id}/approve")
async def approve_model(model_id: str, payload: ApproveModelRequest) -> dict[str, Any]:
    """Approve candidate model enforcing metric gate and two-person rule."""
    try:
        record = GLOBAL_MODEL_REGISTRY.approve_model(model_id, payload.approver_id)
        return record.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    except ApprovalGateError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err


@router.post("/inference", status_code=202)
async def run_inference(payload: RunInferenceRequest) -> dict[str, Any]:
    """Execute tiled inference for a registered, signed, approved model."""
    try:
        session = GLOBAL_MODEL_REGISTRY.load_model_session(payload.model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {payload.model_id} not found")
    except SecurityIntegrityError as err:
        raise HTTPException(status_code=403, detail=f"Security Integrity Violation: {err}") from err

    # Image input or default synthetic test tile
    if payload.image_grid:
        img_arr = np.array(payload.image_grid, dtype=np.float32)
    else:
        # Generate 256x256 test image
        img_arr = np.ones((256, 256), dtype=np.float32) * 0.5

    engine = InferenceEngine(
        session=session,
        conf_threshold=payload.conf_threshold,
    )
    result = engine.run_image(img_arr, batch_size=payload.batch_size)

    product_id = f"ml-prod-{uuid.uuid4().hex[:8]}"
    model_record = GLOBAL_MODEL_REGISTRY.get_model(payload.model_id)

    PRODUCT_STORE[product_id] = {
        "product_id": product_id,
        "model_id": payload.model_id,
        "model_sha256": model_record.sha256,
        "model_version": model_record.version,
        "aoi_id": payload.aoi_id,
        "detection_count": len(result.detections),
        "detections": result.detections,
        "hazard_raster": result.hazard_raster.tolist(),
        "throughput": {
            "tiles_processed": result.tiles_processed,
            "elapsed_seconds": result.elapsed_seconds,
            "tiles_per_second": result.tiles_per_second,
            "megapixels_per_second": result.megapixels_per_second,
        },
        "advisory_notice": "ML crater and obstacle detections are advisory. Always consult terrain slope hazards independently.",
    }

    # Emit completion event
    create_hazard_completed_event(
        product_id=product_id,
        model_id=payload.model_id,
        model_sha256=model_record.sha256,
        detection_count=len(result.detections),
        aoi_id=payload.aoi_id,
    )

    return {
        "product_id": product_id,
        "model_id": payload.model_id,
        "detection_count": len(result.detections),
        "tiles_processed": result.tiles_processed,
        "tiles_per_second": result.tiles_per_second,
        "advisory_notice": "ML crater detections are advisory.",
    }


@router.get("/products/{product_id}")
async def get_product(product_id: str) -> dict[str, Any]:
    """Retrieve metadata and parameters of a hazard product."""
    if product_id not in PRODUCT_STORE:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    prod = PRODUCT_STORE[product_id]
    return {
        "product_id": prod["product_id"],
        "model_id": prod.get("model_id"),
        "model_version": prod.get("model_version"),
        "model_sha256": prod.get("model_sha256"),
        "detection_count": prod.get("detection_count", 0),
        "advisory_notice": prod.get("advisory_notice"),
        "throughput": prod.get("throughput"),
    }


@router.get("/products/{product_id}/detections")
async def get_detections_geojson(
    product_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """Return paginated GeoJSON FeatureCollection of crater circle detections."""
    if product_id not in PRODUCT_STORE:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    all_dets = PRODUCT_STORE[product_id].get("detections", [])
    total = len(all_dets)
    start = (page - 1) * page_size
    paged = all_dets[start : start + page_size]

    features = []
    for d in paged:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [d["center_x"], d["center_y"]],
                },
                "properties": {
                    "radius_px": d["radius_px"],
                    "confidence": d["confidence"],
                    "tile_index": d.get("tile_index", 0),
                    "classification": "crater",
                    "is_advisory": True,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "total": total,
        "page": page,
        "page_size": page_size,
        "features": features,
    }


@router.post("/fusion", status_code=201)
async def perform_fusion(payload: FusionRequest) -> dict[str, Any]:
    """Fuse physical terrain hazard raster and ML hazard detections with max-pooling (FR-13)."""
    # Terrain grid
    if payload.terrain_hazard_grid:
        terrain_arr = np.array(payload.terrain_hazard_grid, dtype=bool)
    else:
        terrain_arr = np.zeros((100, 100), dtype=bool)
        terrain_arr[10:30, 10:30] = True  # slope hazard zone

    # ML grid
    if payload.ml_hazard_grid:
        ml_arr = np.array(payload.ml_hazard_grid, dtype=np.float32)
    else:
        ml_arr = np.zeros((100, 100), dtype=np.float32)
        ml_arr[25:45, 25:45] = 0.85  # ML crater detection zone

    fused_res = fuse_hazards(
        terrain_hazard=terrain_arr,
        ml_hazard_confidence=ml_arr,
        ml_confidence_threshold=payload.ml_confidence_threshold,
        terrain_product_id=payload.terrain_product_id,
        ml_product_id=payload.ml_product_id,
        model_id=payload.model_id,
    )

    fused_id = f"fused-prod-{uuid.uuid4().hex[:8]}"
    PRODUCT_STORE[fused_id] = {
        "product_id": fused_id,
        "params": fused_res.params,
        "stats": fused_res.stats,
        "fused_mask": fused_res.fused_mask.tolist(),
        "advisory_notice": "Fused hazard map combines deterministic terrain slope with advisory ML detections.",
    }

    return {
        "fused_product_id": fused_id,
        "params": fused_res.params,
        "stats": fused_res.stats,
    }
