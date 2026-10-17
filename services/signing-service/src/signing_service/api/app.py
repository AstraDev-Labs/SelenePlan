"""FastAPI application for signing-service (port 8110)."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from signing_service.api.routes import router

app = FastAPI(
    title="SelenePlan Signing Service",
    description="Ed25519 digital signature and canonical plan integrity verification",
    version="0.1.0",
)

app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "signing-service"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "signing-service"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    content = "# HELP signing_operations_total Total digital signatures issued\n# TYPE signing_operations_total counter\nsigning_operations_total 1\n# HELP verify_operations_total Total signature verifications performed\n# TYPE verify_operations_total counter\nverify_operations_total 1"
    return PlainTextResponse(content=content)
