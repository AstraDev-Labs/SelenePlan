"""Component tests for illumination service REST API and authz enforcement."""

import math
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from illumination_service.api.app import app
from illumination_service.api.routes import get_current_principal, store
from illumination_service.worker.pipeline import IlluminationPipeline
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
def seeded_product(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Seed a test illumination product into the store."""
    spice_dir = Path("data/spice")
    tls = spice_dir / "naif0012.tls"
    tpc = spice_dir / "pck00010.tpc"
    bsp = spice_dir / "de421.bsp"

    if tls.is_file() and tpc.is_file() and bsp.is_file():
        default_spice_manager.load_kernels([tls, tpc, bsp])

    temp_dir = tmp_path_factory.mktemp("api_zarr")
    store.base_dir = temp_dir

    pipeline = IlluminationPipeline(cube_store=store)
    dem = np.zeros((20, 20), dtype=np.float64)
    dem[10, 10] = 50.0  # slight peak

    prod_id, _ = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=math.radians(-89.5),
        obs_lon_rad=0.0,
        start_iso="2026-03-01T00:00:00Z",
        end_iso="2026-03-01T04:00:00Z",
        time_step_s=3600.0,
        dataset_version_id="seed-v1",
        crs_wkt="LOCAL",
        bounds=[-200.0, -200.0, 200.0, 200.0],
        azimuth_bins=24,
        max_ray_dist_m=500.0,
    )
    return prod_id


@pytest.fixture
def auth_client() -> Generator[TestClient, None, None]:
    """Client with analyst role authorized."""
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
    """Client without authorization headers (negative test)."""
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
    assert b"http_requests_total" in res_m.content


def test_get_product_metadata(auth_client: TestClient, seeded_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_product}")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == seeded_product
    assert "summary_stats" in data
    assert len(data["time_axis"]) == 5


def test_get_slice_json_and_png(auth_client: TestClient, seeded_product: str) -> None:
    # JSON slice
    res_json = auth_client.get(f"/v1/products/{seeded_product}/slice?t=0&format=json")
    assert res_json.status_code == 200
    j_data = res_json.json()
    assert j_data["time_index"] == 0
    assert j_data["total_cells"] == 400
    assert "mask_base64" in j_data

    # PNG slice
    res_png = auth_client.get(f"/v1/products/{seeded_product}/slice?t=0&format=png")
    assert res_png.status_code == 200
    assert res_png.headers["content-type"] == "image/png"
    assert len(res_png.content) > 50


def test_get_timeseries(auth_client: TestClient, seeded_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_product}/timeseries?x=5&y=5&crs=grid")
    assert res.status_code == 200
    data = res.json()
    assert data["row"] == 5
    assert data["col"] == 5
    assert len(data["series"]) == 5


def test_get_stats(auth_client: TestClient, seeded_product: str) -> None:
    res = auth_client.get(f"/v1/products/{seeded_product}/stats?geom=aoi")
    assert res.status_code == 200
    data = res.json()
    assert "summary_stats" in data
    assert "mean_lit_fraction" in data["summary_stats"]


def test_authz_negative_without_token(unauth_client: TestClient, seeded_product: str) -> None:
    """Negative test: unauthenticated requests must be denied 401."""
    res = unauth_client.get(f"/v1/products/{seeded_product}")
    assert res.status_code in (401, 403)
