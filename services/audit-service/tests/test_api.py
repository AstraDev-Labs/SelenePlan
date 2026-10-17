"""Integration tests for audit service REST endpoints and access control."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

os.environ["DB_NULL_POOL"] = "1"

import pytest
from httpx import ASGITransport, AsyncClient
from selene_auth import Principal, set_global_jwt_validator
from sqlalchemy import text

from audit_service.db.session import dispose_engine, get_engine, init_db
from audit_service.main import app

SUPERUSER_URL = "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene"


class MockJWTValidator:
    def verify_token(self, token: str) -> Principal:
        if token == "auditor-token":
            return Principal(
                sub="auditor-1",
                roles=["auditor"],
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
        if token == "guest-token":
            return Principal(
                sub="guest-1",
                roles=["viewer"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        raise ValueError("Invalid mock token")


@pytest.fixture(scope="module", autouse=True)
async def clean_table_for_module() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(SUPERUSER_URL)
    async with eng.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE audit.audit_log, audit.anchors RESTART IDENTITY"))
    await eng.dispose()


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncIterator[None]:
    eng = get_engine()
    await init_db(eng)
    set_global_jwt_validator(MockJWTValidator())  # type: ignore[arg-type]
    yield
    await dispose_engine()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_internal_ingest_event_success(client: AsyncClient) -> None:
    event_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    payload = {
        "id": event_id,
        "actor_sub": "analyst-1",
        "actor_type": "user",
        "action": "project.created",
        "resource_type": "project",
        "resource_id": proj_id,
        "project_id": proj_id,
        "details": {"name": "Artemis Lunar Base", "secret_token": "SHOULD_BE_SCRUBBED"},
        "source_service": "project-service",
    }
    resp = await client.post("/internal/v1/events", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "appended"
    assert data["id"] == event_id
    assert len(data["row_hash"]) == 64  # 32 bytes hex


@pytest.mark.asyncio
async def test_internal_ingest_unknown_action_rejected(client: AsyncClient) -> None:
    payload = {
        "id": str(uuid.uuid4()),
        "actor_sub": "analyst-1",
        "actor_type": "user",
        "action": "unsupported.bogus.action",
        "resource_type": "something",
        "resource_id": "1",
        "details": {},
        "source_service": "test",
    }
    resp = await client.post("/internal/v1/events", json=payload)
    assert resp.status_code == 400
    assert "Unknown audit action" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_internal_ingest_duplicate_event_id_idempotent(client: AsyncClient) -> None:
    event_id = str(uuid.uuid4())
    payload = {
        "id": event_id,
        "actor_sub": "analyst-1",
        "actor_type": "user",
        "action": "scenario.created",
        "resource_type": "scenario",
        "resource_id": "scen-1",
        "details": {"test": "idempotent"},
        "source_service": "test",
    }
    resp1 = await client.post("/internal/v1/events", json=payload)
    assert resp1.status_code == 201
    seq1 = resp1.json()["seq"]
    hash1 = resp1.json()["row_hash"]

    # Re-send same event_id
    resp2 = await client.post("/internal/v1/events", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["seq"] == seq1
    assert resp2.json()["row_hash"] == hash1


@pytest.mark.asyncio
async def test_query_events_auditor_access(client: AsyncClient) -> None:
    resp = await client.get("/v1/audit/events", headers={"Authorization": "Bearer auditor-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["count"] >= 1


@pytest.mark.asyncio
async def test_query_events_analyst_requires_project_id(client: AsyncClient) -> None:
    # Analyst without project_id must get 403 Forbidden
    resp = await client.get("/v1/audit/events", headers={"Authorization": "Bearer analyst-token"})
    assert resp.status_code == 403
    assert "must specify an explicit project_id" in resp.json()["detail"]

    # Analyst with project_id gets 200
    test_proj = str(uuid.uuid4())
    resp2 = await client.get(
        f"/v1/audit/events?project_id={test_proj}",
        headers={"Authorization": "Bearer analyst-token"},
    )
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_query_events_unauthorized_role_rejected(client: AsyncClient) -> None:
    test_proj = str(uuid.uuid4())
    resp = await client.get(
        f"/v1/audit/events?project_id={test_proj}",
        headers={"Authorization": "Bearer guest-token"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_integrity_check_valid(client: AsyncClient) -> None:
    resp = await client.get(
        "/v1/audit/integrity", headers={"Authorization": "Bearer auditor-token"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["broken_seq"] is None


@pytest.mark.asyncio
async def test_anchor_generation_permissions(client: AsyncClient) -> None:
    # Analyst cannot generate anchor
    resp = await client.post("/v1/audit/anchor", headers={"Authorization": "Bearer analyst-token"})
    assert resp.status_code == 403

    # Auditor can generate anchor
    resp2 = await client.post("/v1/audit/anchor", headers={"Authorization": "Bearer auditor-token"})
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "anchored"
    assert "digest" in data
    assert data["anchor_uri"].startswith("s3://selene-data/")
