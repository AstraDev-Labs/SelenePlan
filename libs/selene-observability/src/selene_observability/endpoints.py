from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def create_health_router(
    ready_checks: dict[str, Callable[[], Awaitable[bool]]] | None = None,
) -> APIRouter:
    """Create a standard health and metrics router for FastAPI microservices."""
    router = APIRouter(tags=["observability"])
    checks = ready_checks or {}

    @router.get("/healthz", summary="Liveness probe", include_in_schema=False)
    async def liveness() -> dict[str, str]:
        """Simple liveness check indicating process is alive."""
        return {"status": "ok"}

    @router.get(
        "/readyz",
        summary="Readiness probe",
        include_in_schema=False,
        responses={
            200: {"description": "Service and all dependencies ready"},
            503: {"description": "Service dependencies degraded or not ready"},
        },
    )
    async def readiness(response: Response) -> dict[str, Any]:
        """Readiness check validating underlying dependencies (DB, Kafka, Redis)."""
        if not checks:
            return {"status": "ready", "checks": {}}

        results: dict[str, bool] = {}
        all_passed = True

        for name, check_fn in checks.items():
            try:
                passed = await check_fn()
                results[name] = bool(passed)
                if not passed:
                    all_passed = False
            except Exception:  # noqa: BLE001 - any failure in readiness check marks dependency down
                results[name] = False
                all_passed = False

        if not all_passed:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "degraded", "checks": results}

        return {"status": "ready", "checks": results}

    @router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Prometheus scrape endpoint."""
        body = generate_latest()
        return Response(content=body, media_type=CONTENT_TYPE_LATEST)

    return router
