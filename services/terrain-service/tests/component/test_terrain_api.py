"""Component tests for terrain-service API endpoints, pipeline execution, and RBAC."""

from __future__ import annotations

import os
import uuid
from typing import Any

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from selene_auth import Principal, set_global_jwt_validator
from selene_geo.cog import validate_cog_bytes
from selene_testing.synthetic import make_bowl_crater
from terrain_service.main import app
from terrain_service.models import get_product_registry

PROJECT_1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROJECT_2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
ORG_1 = uuid.UUID("00000000-0000-0000-0000-000000000010")


class MockJWTValidator:
    """Mock JWT validator for API component tests."""

    def verify_token(self, token: str) -> Principal:
        if token == "planner-proj1":
            return Principal(
                sub="planner-1",
                roles=["planner"],
                org_id=str(ORG_1),
                claims={"project_id": str(PROJECT_1)},
            )
        if token == "planner-proj2":
            return Principal(
                sub="planner-2",
                roles=["planner"],
                org_id=str(ORG_1),
                claims={"project_id": str(PROJECT_2)},
            )
        if token == "admin":
            return Principal(
                sub="admin-1",
                roles=["admin"],
                org_id=str(ORG_1),
                claims={},
            )
        raise ValueError(f"Unknown mock token: {token}")


@pytest.fixture(autouse=True)
def setup_auth(tmp_path: Any) -> None:
    """Configure mock JWT validator and clean registry."""
    set_global_jwt_validator(MockJWTValidator())  # type: ignore[arg-type]
    os.environ["DATA_DIR"] = str(tmp_path / "terrain_data")
    registry = get_product_registry()
    registry.clear()


@pytest.mark.asyncio
async def test_health_endpoints() -> None:
    """Health endpoints /healthz and /readyz must return 200 OK without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        resp_ready = await client.get("/readyz")
        assert resp_ready.status_code == 200
        assert resp_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_terrain_analyze_and_products_flow() -> None:
    """End-to-end component test:

    1. POST /internal/v1/terrain/analyze with synthetic elevation DEM.
    2. Validate products (slope, aspect, roughness, hazard) are created and valid COGs.
    3. GET /v1/products/{id} with authorized token returns metadata.
    4. GET /v1/products/{id}/stats returns quantiles and hazard fraction.
    5. GET /v1/products/{id} with unauthorized token returns 403 Forbidden.
    """
    dem = make_bowl_crater(
        shape=(64, 64),
        radius_m=300.0,
        depth_m=100.0,
        resolution_m=10.0,
    ).elevation.astype(np.float32)
    dem_list = dem.tolist()
    dvid = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Trigger analysis
        analyze_payload = {
            "dataset_version_id": str(dvid),
            "org_id": str(ORG_1),
            "project_id": str(PROJECT_1),
            "elevation_grid": dem_list,
            "resolution_m": 10.0,
            "max_slope_deg": 15.0,
            "max_roughness": 0.35,
            "nodata_is_hazard": True,
            "tile_size": 32,
        }
        resp = await client.post(
            "/internal/v1/terrain/analyze",
            json=analyze_payload,
            headers={"Authorization": "Bearer planner-proj1"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["dataset_version_id"] == str(dvid)
        assert "slope" in data["products"]
        assert "aspect" in data["products"]
        assert "roughness" in data["products"]
        assert "hazard_mask" in data["products"]

        # Validate that written files are structurally valid Cloud-Optimized GeoTIFFs
        from terrain_service.io.storage import get_storage_manager

        sm = get_storage_manager()
        slope_meta = data["products"]["slope"]
        slope_bytes = sm.download_uri(slope_meta["storage_uri"])
        val_res = validate_cog_bytes(slope_bytes)
        assert val_res.is_valid, f"Invalid slope COG produced: {val_res.errors}"

        hazard_meta = data["products"]["hazard_mask"]
        hazard_bytes = sm.download_uri(hazard_meta["storage_uri"])
        val_res_hazard = validate_cog_bytes(hazard_bytes)
        assert val_res_hazard.is_valid, f"Invalid hazard COG produced: {val_res_hazard.errors}"

        slope_id = slope_meta["id"]

        # 2. Query product metadata with authorized planner
        meta_resp = await client.get(
            f"/v1/products/{slope_id}",
            headers={"Authorization": "Bearer planner-proj1"},
        )
        assert meta_resp.status_code == 200
        meta = meta_resp.json()
        assert meta["id"] == slope_id
        assert meta["kind"] == "slope"
        assert meta["dimensions"]["width"] == 64
        assert meta["dimensions"]["height"] == 64

        # 3. Query product stats with authorized planner
        stats_resp = await client.get(
            f"/v1/products/{slope_id}/stats",
            headers={"Authorization": "Bearer planner-proj1"},
        )
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert "min" in stats["stats"]
        assert "mean" in stats["stats"]
        assert "percentiles" in stats["stats"]
        assert "p50" in stats["stats"]["percentiles"]
        assert "p90" in stats["stats"]["percentiles"]

        # 4. Query product metadata with unauthorized planner (different project) -> 403
        unauth_resp = await client.get(
            f"/v1/products/{slope_id}",
            headers={"Authorization": "Bearer planner-proj2"},
        )
        assert unauth_resp.status_code == 403

        # 5. Query product stats with unauthorized planner -> 403
        unauth_stats_resp = await client.get(
            f"/v1/products/{slope_id}/stats",
            headers={"Authorization": "Bearer planner-proj2"},
        )
        assert unauth_stats_resp.status_code == 403

        # 6. Admin can query any project's products -> 200
        admin_resp = await client.get(
            f"/v1/products/{slope_id}",
            headers={"Authorization": "Bearer admin"},
        )
        assert admin_resp.status_code == 200

        # 7. Non-existent product -> 404
        missing_id = str(uuid.uuid4())
        not_found_resp = await client.get(
            f"/v1/products/{missing_id}",
            headers={"Authorization": "Bearer admin"},
        )
        assert not_found_resp.status_code == 404
