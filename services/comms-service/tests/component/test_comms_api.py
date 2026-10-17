"""Component tests for comms-service REST API and authz enforcement."""

import math
from pathlib import Path
from typing import Generator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from comms_service.api.app import app
from comms_service.api.routes import get_current_principal, store
from comms_service.worker.pipeline import CommsPipeline
from selene_auth import AuthError, Principal, set_global_jwt_validator
from selene_geo.spice import default_spice_manager


class MockJWTValidator:
    def validate_token(self, token: str) -> Principal:
        if token == "analyst-token":
            return Principal(
                sub="analyst-user",
                roles=["analyst"],
                project_ids=["proj-default"],
            )
        raise AuthError(f"Invalid token: {token}")


set_global_jwt_validator(MockJWTValidator())  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def seeded_comms_product(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Seed a test comms product into the store."""
    spice_dir = Path("data/spice")
    tls = spice_dir / "naif0012.tls"
    tpc = spice_dir / "pck00010.tpc"
    bsp = spice_dir / "de421.bsp"

    if tls.is_file() and tpc.is_file() and bsp.is_file():
        default_spice_manager.load_kernels([tls, tpc, bsp])

    temp_dir = tmp_path_factory.mktemp("comms_api_zarr")
    store.base_dir = temp_dir

    pipeline = CommsPipeline(cube_store=store)
    dem = np.zeros((20, 20), dtype=np.float64)

    prod_id, _ = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=math.radians(-89.5),
        obs_lon_rad=0.0,
        start_iso="2026-03-01T00:00:00Z",
        end_iso="2026-03-01T04:00:00Z",
        time_step_s=3600.0,
        dataset_version_id="seed-comms-v1",
        crs_wkt="LOCAL",
        bounds=[-200.0, -200.0, 200.0, 200.0],
        azimuth_bins=24,
        max_ray_dist_m=500.0,
    )
    return prod_id


@pytest.fixture
def auth_client() -> Generator[TestClient, None, None]:
    """Client with analyst principal authorized."""
    mock_principal = Principal(
        sub="analyst-user",
        roles=["analyst"],
        project_ids=["proj-default"],
    )
    app.dependency_overrides[get_current_principal] = lambda: mock_principal
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client() -> TestClient:
    app.dependency_overrides.clear()
    return TestClient(app)


def test_healthz_and_metrics(auth_client: TestClient) -> None:
    res_h = auth_client.get("/healthz")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "ok"

    res_r = auth_client.get("/readyz")
    assert res_r.status_code == 200
    assert res_r.json()["status"] == "ready"

    res_m = auth_client.get("/metrics")
    assert res_m.status_code == 200
    assert b"comms_http_requests_total" in res_m.content


def test_get_product_metadata(auth_client: TestClient, seeded_comms_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_comms_product}")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == seeded_comms_product
    assert "summary_stats" in data
    assert len(data["time_axis"]) == 5


def test_get_slice(auth_client: TestClient, seeded_comms_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_comms_product}/slice?t=0")
    assert res.status_code == 200
    data = res.json()
    assert data["time_index"] == 0
    assert data["total_cells"] == 400
    assert "visible_fraction" in data


def test_get_windows(auth_client: TestClient, seeded_comms_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_comms_product}/windows?x=5&y=5&crs=grid")
    assert res.status_code == 200
    data = res.json()
    assert "visible_fraction" in data
    assert "longest_blackout_hours" in data
    assert "windows" in data


def test_along_path_endpoint(auth_client: TestClient, seeded_comms_product: str) -> None:
    body = {
        "waypoints": [
            {"x_m": 0.0, "y_m": 0.0, "time_index": 0},
            {"x_m": 50.0, "y_m": 50.0, "time_index": 1},
        ]
    }
    res = auth_client.post(f"/v1/products/{seeded_comms_product}/along-path", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["total_waypoints"] == 2
    assert len(data["waypoints"]) == 2


def test_get_stats(auth_client: TestClient, seeded_comms_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_comms_product}/stats?geom=aoi")
    assert res.status_code == 200
    data = res.json()
    assert "summary_stats" in data


def test_unauth_negative_test(unauth_client: TestClient, seeded_comms_product: str) -> None:
    res = unauth_client.get(f"/v1/products/{seeded_comms_product}")
    assert res.status_code in (401, 403)
