"""Component tests for artifact verification and storage corruption detection."""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from provenance_service.api.routes import get_current_principal
from provenance_service.main import app
from provenance_service.storage.s3_client import StorageClient
from selene_auth.principal import Principal


@pytest.mark.asyncio
async def test_ac1_corrupted_storage_object_makes_verify_artifact_fail() -> None:
    """AC 1: Registering an artifact and then corrupting the storage object makes verify-artifact fail."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    valid_payload = b"GENUINE_LUNAR_COG_DATA_12345"
    corrupted_payload = b"TAMPERED_OR_CORRUPTED_BITS_99999"

    valid_sha256 = hashlib.sha256(valid_payload).hexdigest()
    corrupted_sha256 = hashlib.sha256(corrupted_payload).hexdigest()

    principal = Principal(
        sub="service-test",
        roles=["service"],
        org_id=str(org_id),
        claims={"project_id": str(project_id)},
    )
    app.dependency_overrides[get_current_principal] = lambda: principal

    storage_uri = f"s3://selene-data/{org_id}/{project_id}/products/dem.cog.tif"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register artifact with valid checksum
        register_req = {
            "artifact_id": str(artifact_id),
            "org_id": str(org_id),
            "project_id": str(project_id),
            "kind": "terrain_slope",
            "uri": storage_uri,
            "sha256": valid_sha256,
            "size_bytes": len(valid_payload),
            "created_by_service": "terrain-service",
        }
        resp = await client.post("/internal/v1/artifacts", json=register_req)
        assert resp.status_code == 201

        # 2. Verify with genuine storage contents -> valid = True
        with patch.object(
            StorageClient,
            "compute_object_sha256",
            return_value=(valid_sha256, len(valid_payload)),
        ):
            verify_resp = await client.post(
                "/internal/v1/verify-artifact",
                json={"artifact_id": str(artifact_id), "read_storage": True},
            )
            assert verify_resp.status_code == 200
            data = verify_resp.json()
            assert data["valid"] is True
            assert data["actual_sha256"] == valid_sha256
            assert data["reason"] is None

        # 3. Simulate bit corruption or object tampering in storage -> valid = False
        with patch.object(
            StorageClient,
            "compute_object_sha256",
            return_value=(corrupted_sha256, len(corrupted_payload)),
        ):
            verify_corrupt = await client.post(
                "/internal/v1/verify-artifact",
                json={"artifact_id": str(artifact_id), "read_storage": True},
            )
            assert verify_corrupt.status_code == 200
            corrupt_data = verify_corrupt.json()
            assert corrupt_data["valid"] is False
            assert corrupt_data["actual_sha256"] == corrupted_sha256
            assert "Tampered or corrupted object in storage" in corrupt_data["reason"]

        # 4. Caller provided expected_sha256 mismatch
        verify_expected_mismatch = await client.post(
            "/internal/v1/verify-artifact",
            json={
                "artifact_id": str(artifact_id),
                "expected_sha256": "00" * 32,
                "read_storage": False,
            },
        )
        assert verify_expected_mismatch.status_code == 200
        mismatch_data = verify_expected_mismatch.json()
        assert mismatch_data["valid"] is False
        assert "Checksum mismatch" in mismatch_data["reason"]

        # 5. Non-existent artifact ID returns valid = False
        non_existent_id = uuid.uuid4()
        verify_missing = await client.post(
            "/internal/v1/verify-artifact",
            json={"artifact_id": str(non_existent_id)},
        )
        assert verify_missing.status_code == 200
        assert verify_missing.json()["valid"] is False
        assert "not registered" in verify_missing.json()["reason"]
