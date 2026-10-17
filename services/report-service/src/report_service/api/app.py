"""FastAPI application for report-service (port 8108)."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from report_service.api.routes import router

app = FastAPI(
    title="SelenePlan Report Service",
    description="Mission reporting, document rendering, and GeoJSON/CSV exports",
    version="0.1.0",
)

app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "report-service"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "report-service"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    content = "# HELP reports_generated_total Total mission reports compiled\n# TYPE reports_generated_total counter\nreports_generated_total 1\n# HELP exports_generated_total Total GeoJSON and CSV exports served\n# TYPE exports_generated_total counter\nexports_generated_total 1"
    return PlainTextResponse(content=content)
