"""SelenePlan Audit Service Main Application."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from selene_auth import (
    JWKSCache,
    JWTValidator,
    set_global_jwt_validator,
)
from selene_observability import (
    PrometheusMetricsMiddleware,
    configure_logging,
    create_health_router,
    init_tracing,
)
from sqlalchemy import text

from audit_service.api.integrity import router as integrity_router
from audit_service.api.internal import router as internal_router
from audit_service.api.query import router as query_router
from audit_service.consumer.audit_consumer import AuditEventConsumer
from audit_service.db.session import (
    get_engine,
    get_session_factory,
    init_db,
)

KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8081/realms/selene")
KEYCLOAK_JWKS_URL = os.getenv(
    "KEYCLOAK_JWKS_URL",
    "http://keycloak:8080/realms/selene/protocol/openid-connect/certs",
)
API_AUDIENCE = os.getenv("API_AUDIENCE", "selene-api")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

consumer_task: asyncio.Task[None] | None = None
consumer_instance: AuditEventConsumer | None = None


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
    global consumer_instance

    # 1. Observability setup
    configure_logging(service_name="audit-service", log_level=os.getenv("LOG_LEVEL", "INFO"))
    init_tracing(service_name="audit-service")

    # 2. Database bootstrap
    await init_db()

    # 3. Auth JWT validator
    jwks_cache = JWKSCache(jwks_url=KEYCLOAK_JWKS_URL, min_refetch_interval_s=1.0)
    validator = JWTValidator(
        jwks_cache=jwks_cache,
        expected_issuer=KEYCLOAK_ISSUER,
        expected_audience=API_AUDIENCE,
    )
    set_global_jwt_validator(validator)

    # 4. Background Kafka consumer if Kafka configured
    if KAFKA_BOOTSTRAP_SERVERS:
        try:
            import redis.asyncio as aioredis
            from selene_events.consumer import RedisDedupeStore

            redis_client = aioredis.from_url(REDIS_URL)
            dedupe_store = RedisDedupeStore(redis_client)

            consumer_instance = AuditEventConsumer(
                session_factory=get_session_factory(),
                dedupe_store=dedupe_store,
            )
        except Exception as e:  # noqa: BLE001
            # Non-blocking in dev if Kafka/Redis unavailable
            print(f"Warning: Kafka consumer setup failed: {e}")

    yield

    # Cleanup
    if consumer_instance:
        await consumer_instance.stop()
    if consumer_task:
        consumer_task.cancel()


app = FastAPI(
    title="SelenePlan Audit Service",
    description="Tamper-evident append-only audit trail with hash chain and anchoring",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware and Observability
app.add_middleware(PrometheusMetricsMiddleware)
health_router = create_health_router(ready_checks={"postgres": check_postgres})
app.include_router(health_router)

# Service Endpoints
app.include_router(internal_router)
app.include_router(query_router)
app.include_router(integrity_router)
