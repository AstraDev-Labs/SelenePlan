"""Component tests for synthetic pipeline lineage, replay-spec, and cross-project access checks."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from provenance_service.api.routes import get_current_principal
from provenance_service.main import app
from selene_auth.principal import Principal


@pytest.mark.asyncio
async def test_ac2_and_ac6_synthetic_pipeline_lineage_and_cross_project() -> None:
    """AC 2 & AC 6: Verify full synthetic pipeline lineage, replay-spec, and cross-project isolation."""
    org_id = uuid.uuid4()
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()

    # Synthetic pipeline node UUIDs
    dataset_id = uuid.uuid4()
    terrain_slope_id = uuid.uuid4()
    hazard_map_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    service_principal = Principal(
        sub="service-worker",
        roles=["service"],
        org_id=str(org_id),
        claims={"project_id": str(project_a)},
    )
    app.dependency_overrides[get_current_principal] = lambda: service_principal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register Dataset
        await client.post(
            "/internal/v1/artifacts",
            json={
                "artifact_id": str(dataset_id),
                "org_id": str(org_id),
                "project_id": str(project_a),
                "kind": "dataset",
                "uri": f"s3://selene-data/{org_id}/{project_a}/datasets/lola_dem.tif",
                "sha256": "11" * 32,
                "size_bytes": 10000,
                "created_by_service": "ingestion-service",
            },
        )

        # 2. Register Terrain Slope deriving from Dataset
        await client.post(
            "/internal/v1/artifacts",
            json={
                "artifact_id": str(terrain_slope_id),
                "org_id": str(org_id),
                "project_id": str(project_a),
                "kind": "terrain_slope",
                "uri": f"s3://selene-data/{org_id}/{project_a}/products/slope.tif",
                "sha256": "22" * 32,
                "size_bytes": 8000,
                "created_by_service": "terrain-service",
                "parent_edges": [
                    {
                        "parent_id": str(dataset_id),
                        "relation": "derived_from",
                        "params_hash": "aa" * 32,
                    }
                ],
            },
        )

        # 3. Register Hazard Map deriving from Terrain Slope
        await client.post(
            "/internal/v1/artifacts",
            json={
                "artifact_id": str(hazard_map_id),
                "org_id": str(org_id),
                "project_id": str(project_a),
                "kind": "hazard_map",
                "uri": f"s3://selene-data/{org_id}/{project_a}/products/hazard.tif",
                "sha256": "33" * 32,
                "size_bytes": 5000,
                "created_by_service": "hazard-service",
                "parent_edges": [
                    {
                        "parent_id": str(terrain_slope_id),
                        "relation": "derived_from",
                        "params_hash": "bb" * 32,
                    }
                ],
            },
        )

        # 4. Register Plan deriving from Hazard Map
        await client.post(
            "/internal/v1/artifacts",
            json={
                "artifact_id": str(plan_id),
                "org_id": str(org_id),
                "project_id": str(project_a),
                "kind": "plan",
                "uri": f"s3://selene-data/{org_id}/{project_a}/plans/plan.json",
                "sha256": "44" * 32,
                "size_bytes": 1200,
                "created_by_service": "planner-service",
                "metadata": {"parameters": {"max_slope_deg": 15.0, "rover_speed_mps": 0.05}},
                "manifest": {"plan_version": 1},
                "parent_edges": [
                    {
                        "parent_id": str(hazard_map_id),
                        "relation": "derived_from",
                        "params_hash": "cc" * 32,
                    }
                ],
            },
        )

        # 5. Query Lineage (direction=up) for Plan as authorized user in Project A
        user_proj_a = Principal(
            sub="analyst-a",
            roles=["analyst"],
            org_id=str(org_id),
            claims={"project_id": str(project_a)},
        )
        app.dependency_overrides[get_current_principal] = lambda: user_proj_a

        resp_lineage = await client.get(f"/v1/lineage/{plan_id}?direction=up&depth=10")
        assert resp_lineage.status_code == 200
        lineage_data = resp_lineage.json()

        node_ids = {n["id"] for n in lineage_data["nodes"]}
        expected_chain = {str(plan_id), str(hazard_map_id), str(terrain_slope_id), str(dataset_id)}
        assert node_ids == expected_chain

        edges = lineage_data["edges"]
        assert len(edges) == 3

        # 6. Query Replay Spec
        resp_replay = await client.get(f"/v1/lineage/{plan_id}/replay-spec")
        assert resp_replay.status_code == 200
        replay_data = resp_replay.json()
        assert replay_data["schema"] == "selene.replay.v1"
        assert replay_data["artifact_id"] == str(plan_id)
        assert replay_data["parameters"]["max_slope_deg"] == 15.0
        # Source input is root dataset
        source_inputs = replay_data["source_inputs"]
        assert len(source_inputs) == 1
        assert source_inputs[0]["id"] == str(dataset_id)

        # 7. AC 6: Cross-project access denied (User in Project B attempting to access Project A's artifact)
        user_proj_b = Principal(
            sub="analyst-b",
            roles=["analyst"],
            org_id=str(org_id),
            claims={"project_id": str(project_b)},
        )
        app.dependency_overrides[get_current_principal] = lambda: user_proj_b

        resp_forbidden_art = await client.get(f"/v1/artifacts/{plan_id}")
        assert resp_forbidden_art.status_code == 403
        assert "not a member of project" in resp_forbidden_art.json()["detail"]

        resp_forbidden_lineage = await client.get(f"/v1/lineage/{plan_id}")
        assert resp_forbidden_lineage.status_code == 403

        resp_forbidden_replay = await client.get(f"/v1/lineage/{plan_id}/replay-spec")
        assert resp_forbidden_replay.status_code == 403

        # 8. Auditor can access across projects
        auditor_principal = Principal(
            sub="auditor-1",
            roles=["auditor"],
            org_id=str(org_id),
            claims={"project_id": str(project_b)},
        )
        app.dependency_overrides[get_current_principal] = lambda: auditor_principal

        resp_auditor = await client.get(f"/v1/lineage/{plan_id}")
        assert resp_auditor.status_code == 200
