"""FastAPI application factory for illumination-service."""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from illumination_service.api.routes import router

REQUEST_COUNT = Counter(
    "illumination_http_requests_total",
    "Total HTTP requests handled by illumination-service",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "illumination_http_request_duration_seconds",
    "HTTP request latency in seconds for illumination-service",
    ["endpoint"],
)


def create_app() -> FastAPI:
    """Create and configure the illumination-service FastAPI instance."""
    app = FastAPI(
        title="SelenePlan Illumination Service",
        version="0.1.0",
        description="Lunar south pole time-varying illumination and shadow engine",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Any) -> Response:
        start_time = time.perf_counter()
        trace_id = request.headers.get("X-Trace-ID", "unknown-trace")
        response = await call_next(request)
        latency = time.perf_counter() - start_time
        response.headers["X-Trace-ID"] = trace_id

        endpoint = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
        return response

    @app.get("/healthz", tags=["System"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "illumination-service"}

    @app.get("/readyz", tags=["System"])
    async def readyz() -> dict[str, str]:
        return {"status": "ready", "service": "illumination-service"}

    @app.get("/metrics", tags=["System"])
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router)
    return app


app = create_app()
