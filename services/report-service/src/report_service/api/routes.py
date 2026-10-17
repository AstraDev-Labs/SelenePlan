"""FastAPI routes for report-service: report generation, HTML/PDF rendering, GeoJSON, and CSV export."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from report_service.exports.export import export_csv, export_geojson
from report_service.templates.builder import render_report_html

router = APIRouter(prefix="/v1")

REPORT_STORE: dict[str, dict[str, Any]] = {}


class CreateReportRequest(BaseModel):
    project_id: str
    plan_id: str
    plan_data: dict[str, Any]


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(req: CreateReportRequest) -> dict[str, Any]:
    report_id = f"rep-{uuid.uuid4().hex[:8]}"

    # Render report HTML
    html_content = render_report_html(req.plan_data)
    content_sha256 = hashlib.sha256(html_content.encode("utf-8")).hexdigest()

    record = {
        "report_id": report_id,
        "project_id": req.project_id,
        "plan_id": req.plan_id,
        "plan_name": req.plan_data.get("name", "Untitled Plan"),
        "is_signed": bool(req.plan_data.get("signature")),
        "content_sha256": content_sha256,
        "html_content": html_content,
        "plan_data": req.plan_data,
        "status": "completed",
    }

    REPORT_STORE[report_id] = record

    return {
        "report_id": report_id,
        "status": "completed",
        "content_sha256": content_sha256,
        "project_id": req.project_id,
    }


@router.get("/reports/{report_id}")
async def get_report_metadata(report_id: str, project_id: str | None = None) -> dict[str, Any]:
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    rep = REPORT_STORE[report_id]
    if project_id and rep["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Cross-project access forbidden")

    return {
        "report_id": rep["report_id"],
        "project_id": rep["project_id"],
        "plan_id": rep["plan_id"],
        "plan_name": rep["plan_name"],
        "is_signed": rep["is_signed"],
        "content_sha256": rep["content_sha256"],
        "status": rep["status"],
    }


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str, project_id: str | None = None) -> HTMLResponse:
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    rep = REPORT_STORE[report_id]
    if project_id and rep["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Cross-project access forbidden")

    return HTMLResponse(content=rep["html_content"])


@router.get("/reports/{report_id}/export/{format_type}")
async def export_report_format(
    report_id: str, format_type: str, project_id: str | None = None
) -> Response:
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    rep = REPORT_STORE[report_id]
    if project_id and rep["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Cross-project access forbidden")

    if format_type.lower() == "geojson":
        geojson_data = export_geojson(rep["plan_data"])
        import json

        return Response(
            content=json.dumps(geojson_data, indent=2),
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename={rep['plan_id']}.geojson"},
        )
    elif format_type.lower() == "csv":
        csv_text = export_csv(rep["plan_data"])
        return PlainTextResponse(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={rep['plan_id']}.csv"},
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format '{format_type}': choose geojson or csv",
        )
