"""Component tests for artifact registration, immutability, and checksum conflict rejection."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from provenance_service.api.routes import get_current_principal
from provenance_service.main import app
from selene_auth.principal import Principal


@pytest.mark.asyncio
async def test_artifact_registration_and_immutability() -> None:
    """Verify artifact registration, idempotency, and 409 on conflicting checksum."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    sha256_original = "11" * 32
    sha256_conflicting = "22" * 32

    analyst_principal = Principal(
        sub="test-analyst",
        roles=["analyst"],
        org_id=str(org_id),
        claims={"project_id": str(project_id)},
    )
    app.dependency_overrides[get_current_principal] = lambda: analyst_principal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register new artifact
        register_payload = {
            "artifact_id": str(artifact_id),
            "org_id": str(org_id),
            "project_id": str(project_id),
            "kind": "dataset",
            "uri": "s3://selene-data/datasets/test.cog.tif",
            "sha256": sha256_original,
            "size_bytes": 2048,
            "created_by_service": "ingestion-service",
            "metadata": {"resolution_m": 10.0},
            "manifest": {"tool": "gdal", "version": "3.8"},
        }
        resp = await client.post("/internal/v1/artifacts", json=register_payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["id"] == str(artifact_id)
        assert data["sha256"] == sha256_original

        # 2. Idempotent re-registration with identical checksum succeeds
        resp_idem = await client.post("/internal/v1/artifacts", json=register_payload)
        assert resp_idem.status_code == 201
        assert resp_idem.json()["sha256"] == sha256_original

        # 3. Conflicting checksum for existing artifact ID raises 409 Conflict
        conflict_payload = dict(register_payload)
        conflict_payload["sha256"] = sha256_conflicting
        resp_conflict = await client.post("/internal/v1/artifacts", json=conflict_payload)
        assert resp_conflict.status_code == 409
        assert "already registered with sha256" in resp_conflict.json()["detail"]

        # 4. Fetch artifact metadata
        resp_get = await client.get(f"/v1/artifacts/{artifact_id}")
        assert resp_get.status_code == 200
        get_data = resp_get.json()
        assert get_data["id"] == str(artifact_id)
        assert get_data["kind"] == "dataset"
        assert get_data["metadata"]["resolution_m"] == 10.0
