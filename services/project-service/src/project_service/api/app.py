"""FastAPI application for project-service (port 8101)."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from project_service.api.routes import router

app = FastAPI(
    title="SelenePlan Project Service",
    description="Pipeline orchestrator and plan workflow management",
    version="0.1.0",
)

app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "project-service"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "project-service"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    content = "# HELP project_runs_total Total mission runs initiated\n# TYPE project_runs_total counter\nproject_runs_total 1\n# HELP project_plans_total Total plan versions managed\n# TYPE project_plans_total counter\nproject_plans_total 1"
    return PlainTextResponse(content=content)
