"""SelenePlan Terrain Service Main Application."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from selene_auth import JWKSCache, JWTValidator, set_global_jwt_validator
from selene_observability import (
    PrometheusMetricsMiddleware,
    configure_logging,
    create_health_router,
    init_tracing,
)

from terrain_service.api.routes import router as api_router
from terrain_service.config import get_config


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    cfg = get_config()

    # 1. Observability setup
    configure_logging(service_name=cfg.service_name, log_level=os.getenv("LOG_LEVEL", "INFO"))
    init_tracing(service_name=cfg.service_name)

    # 2. Auth JWT validator
    jwks_cache = JWKSCache(jwks_url=cfg.keycloak_jwks_url, min_refetch_interval_s=1.0)
    validator = JWTValidator(
        jwks_cache=jwks_cache,
        expected_issuer=cfg.keycloak_issuer,
        expected_audience=cfg.api_audience,
    )
    set_global_jwt_validator(validator)

    yield


app = FastAPI(
    title="SelenePlan Terrain Service",
    description="Slope, aspect, roughness, and hazard analysis for lunar exploration",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware and Observability
app.add_middleware(PrometheusMetricsMiddleware)
health_router = create_health_router()
app.include_router(health_router)

# Service Endpoints
app.include_router(api_router)
