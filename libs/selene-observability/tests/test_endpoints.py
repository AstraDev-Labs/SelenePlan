from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from selene_observability.endpoints import create_health_router


@pytest.mark.asyncio
async def test_health_router_success_flow() -> None:
    async def db_check() -> bool:
        return True

    async def kafka_check() -> bool:
        return True

    app = FastAPI()
    router = create_health_router(ready_checks={"db": db_check, "kafka": kafka_check})
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Liveness
        res_live = await client.get("/healthz")
        assert res_live.status_code == 200
        assert res_live.json() == {"status": "ok"}

        # 2. Readiness - healthy
        res_ready = await client.get("/readyz")
        assert res_ready.status_code == 200
        data = res_ready.json()
        assert data["status"] == "ready"
        assert data["checks"] == {"db": True, "kafka": True}

        # 3. Metrics
        res_metrics = await client.get("/metrics")
        assert res_metrics.status_code == 200
        assert "http_requests_total" in res_metrics.text


@pytest.mark.asyncio
async def test_health_router_degraded_readiness() -> None:
    async def db_check() -> bool:
        return True

    async def redis_check() -> bool:
        return False

    async def throwing_check() -> bool:
        raise ConnectionResetError("Connection refused")

    app = FastAPI()
    router = create_health_router(
        ready_checks={"db": db_check, "redis": redis_check, "flaky": throwing_check}
    )
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_ready = await client.get("/readyz")
        assert res_ready.status_code == 503
        data = res_ready.json()
        assert data["status"] == "degraded"
        assert data["checks"] == {"db": True, "redis": False, "flaky": False}


@pytest.mark.asyncio
async def test_health_router_empty_checks() -> None:
    app = FastAPI()
    router = create_health_router(ready_checks=None)
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_ready = await client.get("/readyz")
        assert res_ready.status_code == 200
        assert res_ready.json() == {"status": "ready", "checks": {}}
