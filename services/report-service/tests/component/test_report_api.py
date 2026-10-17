"""Component tests for report-service API routes.

Per services/report-service/SPEC.md:
- AC 6: Another project's member cannot download the report (403 Forbidden).
- GeoJSON and CSV export endpoint verification.
"""

import pytest
from fastapi.testclient import TestClient
from report_service.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_system_endpoints(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"

    res = client.get("/metrics")
    assert res.status_code == 200
    assert "reports_generated_total" in res.text


def test_report_generation_download_and_project_isolation(client: TestClient) -> None:
    plan_data = {
        "plan_id": "plan-shackleton-exp",
        "name": "Expedition One",
        "version_number": 1,
        "project_id": "proj-shackleton",
        "waypoints": [
            {
                "step_idx": 0,
                "row": 8,
                "col": 2,
                "x_m": -160.0,
                "y_m": 0.0,
                "t_hours": 0.0,
                "battery_wh": 500.0,
            },
            {
                "step_idx": 1,
                "row": 8,
                "col": 10,
                "x_m": 0.0,
                "y_m": 0.0,
                "t_hours": 0.5,
                "battery_wh": 485.0,
            },
            {
                "step_idx": 2,
                "row": 8,
                "col": 18,
                "x_m": 160.0,
                "y_m": 0.0,
                "t_hours": 1.0,
                "battery_wh": 470.0,
            },
        ],
        "total_distance_m": 320.0,
        "total_duration_hours": 1.0,
        "signature": {
            "key_id": "selene-plan-signing",
            "key_version": 1,
            "payload_sha256": "abcdef998877",
            "signature": "vault:v1:sig-test",
        },
    }

    # 1. Create Report
    create_res = client.post(
        "/v1/reports",
        json={
            "project_id": "proj-shackleton",
            "plan_id": "plan-shackleton-exp",
            "plan_data": plan_data,
        },
    )
    assert create_res.status_code == 202
    data = create_res.json()
    report_id = data["report_id"]

    # 2. Download report with matching project
    down_res = client.get(f"/v1/reports/{report_id}/download?project_id=proj-shackleton")
    assert down_res.status_code == 200
    assert "Expedition One" in down_res.text

    # 3. AC 6: Member from another project denied -> 403 Forbidden
    cross_res = client.get(f"/v1/reports/{report_id}/download?project_id=proj-amundsen")
    assert cross_res.status_code == 403

    # 4. GeoJSON export
    geo_res = client.get(f"/v1/reports/{report_id}/export/geojson?project_id=proj-shackleton")
    assert geo_res.status_code == 200
    assert geo_res.headers["content-type"].startswith("application/geo+json")
    geojson = geo_res.json()
    assert geojson["type"] == "FeatureCollection"
    assert geojson["properties"]["payload_sha256"] == "abcdef998877"
    assert len(geojson["features"]) == 4  # 1 LineString + 3 Points

    # 5. CSV export
    csv_res = client.get(f"/v1/reports/{report_id}/export/csv?project_id=proj-shackleton")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "# Payload Canonical SHA-256: abcdef998877" in csv_res.text
    assert (
        "step_idx,row,col,x_m,y_m,t_hours,battery_wh,sun_elev_deg,is_lit,earth_visible,action"
        in csv_res.text
    )
