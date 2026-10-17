"""Component integration tests for hazard-ml-service REST endpoints."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from hazard_ml_service.api.app import app
from hazard_ml_service.registry.models import GLOBAL_MODEL_REGISTRY, ModelCard


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def registered_approved_model() -> str:
    model_id = "crater_detector_v1"
    onnx_path = (
        Path(__file__).resolve().parent.parent.parent / "model-cards" / "crater_detector_v1.onnx"
    )
    onnx_bytes = onnx_path.read_bytes()

    card = ModelCard(
        model_id=model_id,
        version="1.0.0",
        name="Dual-Head Crater Detector",
        architecture="CNN",
        description="Component test model",
        intended_use="Test",
        thresholds={"min_precision": 0.70, "min_recall": 0.70},
        measured_metrics={"precision": 0.724, "recall": 0.700},
    )
    GLOBAL_MODEL_REGISTRY.register_model(card, onnx_bytes, created_by="steward-001")
    GLOBAL_MODEL_REGISTRY.approve_model(model_id, approver_id="steward-002")
    return model_id


def test_system_endpoints(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"

    res = client.get("/metrics")
    assert res.status_code == 200
    assert "hazard_ml_http_requests_total" in res.text


def test_model_registration_and_approval_flow(client: TestClient) -> None:
    card_data = {
        "model_id": "test_api_reg_model",
        "version": "1.0.0",
        "name": "API Reg Test",
        "architecture": "CNN",
        "description": "API registration test",
        "intended_use": "Test",
        "thresholds": {"min_precision": 0.70},
        "measured_metrics": {"precision": 0.85},
    }

    # Register
    res = client.post(
        "/v1/models",
        json={
            "model_card": card_data,
            "created_by": "alice",
        },
    )
    assert res.status_code == 201
    assert res.json()["approved"] is False

    # List & Get
    res = client.get("/v1/models")
    assert res.status_code == 200
    assert any(m["model_id"] == "test_api_reg_model" for m in res.json())

    res = client.get("/v1/models/test_api_reg_model")
    assert res.status_code == 200

    # Self-approval fails (two-person rule)
    res = client.post("/v1/models/test_api_reg_model/approve", json={"approver_id": "alice"})
    assert res.status_code == 403

    # Distinct approver succeeds
    res = client.post("/v1/models/test_api_reg_model/approve", json={"approver_id": "bob"})
    assert res.status_code == 200
    assert res.json()["approved"] is True


def test_inference_and_detections(client: TestClient, registered_approved_model: str) -> None:
    res = client.post(
        "/v1/inference",
        json={
            "model_id": registered_approved_model,
            "aoi_id": "shackleton-polar-01",
            "conf_threshold": 0.75,
        },
    )
    assert res.status_code == 202
    data = res.json()
    prod_id = data["product_id"]
    assert "advisory_notice" in data

    # Retrieve product metadata
    res = client.get(f"/v1/products/{prod_id}")
    assert res.status_code == 200
    meta = res.json()
    assert meta["model_id"] == registered_approved_model

    # Retrieve GeoJSON detections
    res = client.get(f"/v1/products/{prod_id}/detections?page=1&page_size=50")
    assert res.status_code == 200
    geojson = res.json()
    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson


def test_hazard_fusion_endpoint(client: TestClient) -> None:
    res = client.post(
        "/v1/fusion",
        json={
            "terrain_product_id": "terrain-p1",
            "ml_product_id": "ml-p1",
            "model_id": "crater_detector_v1",
            "ml_confidence_threshold": 0.60,
        },
    )
    assert res.status_code == 201
    fused = res.json()
    assert "fused_product_id" in fused
    assert "stats" in fused
    assert "fused_hazard_cells" in fused["stats"]
