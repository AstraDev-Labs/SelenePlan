"""SelenePlan Ingestion Service Main Application."""

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
from sqlalchemy import text

from ingestion_service.api.routes import router as api_router
from ingestion_service.config import settings
from ingestion_service.db.session import get_engine, init_db


async def check_postgres() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 1. Observability setup
    configure_logging(service_name=settings.service_name, log_level=os.getenv("LOG_LEVEL", "INFO"))
    init_tracing(service_name=settings.service_name)

    # 2. Database bootstrap
    await init_db()

    # 3. Auth JWT validator
    jwks_cache = JWKSCache(jwks_url=settings.keycloak_jwks_url, min_refetch_interval_s=1.0)
    validator = JWTValidator(
        jwks_cache=jwks_cache,
        expected_issuer=settings.keycloak_issuer,
        expected_audience=settings.api_audience,
    )
    set_global_jwt_validator(validator)

    yield


app = FastAPI(
    title="SelenePlan Ingestion Service",
    description="Egress-controlled dataset registration and COG ingestion",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware and Observability
app.add_middleware(PrometheusMetricsMiddleware)
health_router = create_health_router(ready_checks={"postgres": check_postgres})
app.include_router(health_router)

# Service Endpoints
app.include_router(api_router)
