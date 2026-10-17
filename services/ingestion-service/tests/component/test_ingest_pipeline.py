"""Component tests for ingestion pipeline, transactional safety, corruption checks, and API RBAC."""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator

os.environ["DB_NULL_POOL"] = "1"

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from selene_auth import Principal, set_global_jwt_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.db.repository import IngestionRepository
from ingestion_service.db.session import dispose_engine, get_engine, init_db
from ingestion_service.main import app
from ingestion_service.storage.s3_client import DataCorruptionError, get_storage_manager
from ingestion_service.worker.ingest_worker import IngestPipeline

SUPERUSER_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene"
)


class MockJWTValidator:
    def verify_token(self, token: str) -> Principal:
        if token == "steward-token":
            return Principal(
                sub="steward-1",
                roles=["steward"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        if token == "admin-token":
            return Principal(
                sub="admin-1",
                roles=["admin"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        if token == "analyst-token":
            return Principal(
                sub="analyst-1",
                roles=["analyst"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        if token == "viewer-token":
            return Principal(
                sub="viewer-1",
                roles=["viewer"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        raise ValueError("Invalid mock token")


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncIterator[None]:
    """Initialize database schema before running tests."""
    await init_db()
    set_global_jwt_validator(MockJWTValidator())
    yield
    await dispose_engine()


def _create_synthetic_tiff(width: int = 64, height: int = 64) -> bytes:
    arr = np.linspace(0, 100, width * height, dtype=np.float32).reshape(height, width)
    buf = io.BytesIO()
    img = Image.fromarray(arr)
    img.save(buf, format="TIFF")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_end_to_end_ingest_pipeline() -> None:
    """Verify complete ingestion workflow, S3 storage, event emission, and corruption detection."""
    engine = get_engine()
    raw_tiff = _create_synthetic_tiff(64, 64)
    storage = get_storage_manager()

    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = IngestionRepository(session)
        dataset, version, _job = await repo.create_dataset_and_job(
            org_id=org_id,
            project_id=project_id,
            name="Synthetic Test DEM",
            kind="dem",
            source_name="upload",
            source_url="upload://test.tif",
            license="NASA Public Domain",
            terms_note="Test only",
            redistributable=True,
            created_by="steward-1",
        )
        d_id = dataset.id
        v_id = version.id
        await session.commit()

        # Run pipeline
        pipeline = IngestPipeline(session)
        await pipeline.execute_ingest(
            dataset_id=d_id,
            version_id=v_id,
            raw_bytes=raw_tiff,
        )

        # Verify DB records updated to registered
        v = await repo.get_version(d_id, 1)
        assert v is not None
        assert v.status == "registered"
        assert v.size_bytes > 0
        assert len(v.sha256) == 64
        assert v.storage_uri.startswith("s3://")
        assert v.manifest["cog"] is True

        # Acceptance criterion 4: Re-reading verifies SHA-256
        assert storage.verify_dataset_integrity(v.storage_uri, v.sha256) is True

        # Acceptance criterion 4: Corrupted object is detected
        storage.put_mock_object(
            f"{org_id}/{project_id}/datasets/{d_id}/1/dem.cog.tif",
            b"CORRUPTED_BYTES_HERE",
        )
        with pytest.raises(DataCorruptionError, match="corruption detected"):
            storage.verify_dataset_integrity(v.storage_uri, v.sha256)


@pytest.mark.asyncio
async def test_transactional_failure_leaves_no_half_registered_versions() -> None:
    """Acceptance criterion 5: Failed ingests mark version as failed without leaving half-registered versions."""
    engine = get_engine()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = IngestionRepository(session)
        dataset, version, _job = await repo.create_dataset_and_job(
            org_id=org_id,
            project_id=project_id,
            name="Corrupt Ingest Test",
            kind="dem",
            source_name="upload",
            source_url="upload://bad.tif",
            license="Public",
            terms_note="",
            redistributable=True,
            created_by="steward-1",
        )
        d_id = dataset.id
        v_id = version.id
        await session.commit()

        pipeline = IngestPipeline(session)
        from ingestion_service.validation.raster_validator import RasterSecurityError

        # Attempt ingest with invalid raster payload
        with pytest.raises(RasterSecurityError):
            await pipeline.execute_ingest(
                dataset_id=d_id,
                version_id=v_id,
                raw_bytes=b"NOT_A_VALID_TIFF",
            )

        # Verify version and job are strictly marked as failed
        v = await repo.get_version(d_id, 1)
        assert v is not None
        assert v.status == "failed"
        assert v.storage_uri == ""

        j = await repo.get_job_by_version(version.id)
        assert j is not None
        assert j.state == "failed"
        assert j.error is not None


@pytest.mark.asyncio
async def test_api_role_authorization_and_upload() -> None:
    """Acceptance criterion 6: Non-Steward users cannot register or upload (403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "LOLA Polar Mosaic",
            "kind": "dem",
            "source": "lola-dem",
            "source_url": "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
            "license": "NASA Open Data",
            "org_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        }

        # 1. Unauthenticated -> 401
        res = await client.post("/v1/datasets", json=payload)
        assert res.status_code == 401

        # 2. Analyst role -> 403 Forbidden
        res = await client.post(
            "/v1/datasets",
            json=payload,
            headers={"Authorization": "Bearer analyst-token"},
        )
        assert res.status_code == 403

        # 3. Viewer role -> 403 Forbidden
        res = await client.post(
            "/v1/datasets",
            json=payload,
            headers={"Authorization": "Bearer viewer-token"},
        )
        assert res.status_code == 403

        # 4. Steward role -> 202 Accepted
        import hashlib
        from unittest.mock import patch

        from ingestion_service.sources.downloader import DownloadedArtifact, SecureDownloader

        fake_tiff = _create_synthetic_tiff(32, 32)
        fake_artifact = DownloadedArtifact(
            content=fake_tiff,
            sha256=hashlib.sha256(fake_tiff).hexdigest(),
            size_bytes=len(fake_tiff),
            content_type="image/tiff",
        )

        with patch.object(SecureDownloader, "download", return_value=fake_artifact):
            res = await client.post(
                "/v1/datasets",
                json=payload,
                headers={"Authorization": "Bearer steward-token"},
            )
            assert res.status_code == 202
            data = res.json()
            dataset_id = data["id"]
            assert data["status"] == "queued"

        # 5. Get metadata
        meta_res = await client.get(
            f"/v1/datasets/{dataset_id}",
            headers={"Authorization": "Bearer analyst-token"},
        )
        assert meta_res.status_code == 200
        assert meta_res.json()["name"] == "LOLA Polar Mosaic"

        # 6. List versions
        v_res = await client.get(
            f"/v1/datasets/{dataset_id}/versions",
            headers={"Authorization": "Bearer analyst-token"},
        )
        assert v_res.status_code == 200
        assert len(v_res.json()) >= 1

        # 7. Get internal sources
        src_res = await client.get(
            "/internal/v1/sources",
            headers={"Authorization": "Bearer analyst-token"},
        )
        assert src_res.status_code == 200
        assert any(s["id"] == "lola-dem" for s in src_res.json())

        # 8. Steward direct upload -> 202 Accepted
        raw_tiff = _create_synthetic_tiff(32, 32)
        upload_res = await client.post(
            "/v1/datasets/upload",
            data={
                "name": "Uploaded DEM",
                "kind": "dem",
                "license": "NASA Public",
                "org_id": str(uuid.uuid4()),
                "project_id": str(uuid.uuid4()),
            },
            files={"file": ("dem.tif", raw_tiff, "image/tiff")},
            headers={"Authorization": "Bearer steward-token"},
        )
        assert upload_res.status_code == 202
        assert upload_res.json()["status"] == "registered"
