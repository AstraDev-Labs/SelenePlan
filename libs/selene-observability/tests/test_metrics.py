from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY
from selene_observability.metrics import PrometheusMetricsMiddleware


@pytest.mark.asyncio
async def test_metrics_middleware_records_with_route_templates() -> None:
    app = FastAPI()
    app.add_middleware(PrometheusMetricsMiddleware)

    @app.get("/v1/projects/{project_id}")
    async def get_project(project_id: str) -> dict[str, str]:
        return {"id": project_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Call parameterized route
        res = await client.get("/v1/projects/proj-123")
        assert res.status_code == 200

        # Call non-existent route
        res_404 = await client.get("/v1/unknown")
        assert res_404.status_code == 404

    # Check metrics recorded with route template, NOT raw path
    sample_200 = REGISTRY.get_sample_value(
        "http_requests_total",
        labels={"method": "GET", "route": "/v1/projects/{project_id}", "status_code": "200"},
    )
    assert sample_200 is not None
    assert sample_200 >= 1.0

    # Check raw path was NOT used
    sample_raw = REGISTRY.get_sample_value(
        "http_requests_total",
        labels={"method": "GET", "route": "/v1/projects/proj-123", "status_code": "200"},
    )
    assert sample_raw is None

    # Check 404 template
    sample_404 = REGISTRY.get_sample_value(
        "http_requests_total",
        labels={"method": "GET", "route": "not_found", "status_code": "404"},
    )
    assert sample_404 is not None
    assert sample_404 >= 1.0
