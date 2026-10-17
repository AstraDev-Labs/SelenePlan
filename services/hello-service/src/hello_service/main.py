"""Hello Service for Phase 0 Gateway and Authentication Verification."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from selene_auth import (
    JWKSCache,
    JWTValidator,
    Principal,
    get_current_principal,
    set_global_jwt_validator,
)
from selene_observability import (
    PrometheusMetricsMiddleware,
    configure_logging,
    create_health_router,
    init_tracing,
)

# Service configuration
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8081/realms/selene")
KEYCLOAK_JWKS_URL = os.getenv(
    "KEYCLOAK_JWKS_URL",
    "http://keycloak:8080/realms/selene/protocol/openid-connect/certs",
)
API_AUDIENCE = os.getenv("API_AUDIENCE", "selene-api")


class HelloResponse(BaseModel):
    status: str
    service: str
    sub: str
    roles: list[str]
    org_id: str | None
    mfa_verified: bool


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    """Initialize observability, logging, and auth validator on startup."""
    configure_logging(service_name="hello-service", log_level=os.getenv("LOG_LEVEL", "INFO"))
    init_tracing(service_name="hello-service")

    # Initialize JWKS cache and validator for defense-in-depth token validation
    jwks_cache = JWKSCache(jwks_url=KEYCLOAK_JWKS_URL, min_refetch_interval_s=1.0)
    validator = JWTValidator(
        jwks_cache=jwks_cache,
        expected_issuer=KEYCLOAK_ISSUER,
        expected_audience=API_AUDIENCE,
    )
    set_global_jwt_validator(validator)

    yield


app = FastAPI(
    title="SelenePlan Hello Service",
    version="0.1.0",
    lifespan=lifespan,
)

# 1. Observability middleware and endpoints
app.add_middleware(PrometheusMetricsMiddleware)
health_router = create_health_router()
app.include_router(health_router)


# 2. Protected Gateway Test Endpoints
@app.get("/v1/hello", response_model=HelloResponse)
async def get_hello(principal: Principal = Depends(get_current_principal)) -> HelloResponse:
    """Authenticated endpoint returning caller principal details."""
    return HelloResponse(
        status="ok",
        service="hello-service",
        sub=principal.sub,
        roles=principal.roles,
        org_id=principal.org_id,
        mfa_verified=principal.mfa_verified,
    )


@app.post("/v1/hello")
async def post_hello(
    payload: dict[str, Any],
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Authenticated POST endpoint used to verify request size limits."""
    return {
        "status": "received",
        "sub": principal.sub,
        "keys": list(payload.keys()),
    }
