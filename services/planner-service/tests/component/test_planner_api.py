"""Component integration tests for planner-service REST endpoints."""

import pytest
from fastapi.testclient import TestClient
from planner_service.api.app import app


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
    assert "planner_http_requests_total" in res.text


def test_rankings_api_flow(client: TestClient) -> None:
    res = client.post(
        "/v1/planner/rankings",
        json={
            "aoi_id": "shackleton-polar-01",
            "max_slope_deg": 12.0,
            "min_lit_fraction": 0.40,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "ranking_id" in data
    assert data["ranked_count"] > 0

    ranking_id = data["ranking_id"]
    res = client.get(f"/v1/planner/rankings/{ranking_id}")
    assert res.status_code == 200
    details = res.json()
    assert len(details["ranked_sites"]) > 0


def test_route_and_whatif_api_flow(client: TestClient) -> None:
    # 1. Plan baseline route
    res = client.post(
        "/v1/planner/routes",
        json={
            "start_point": [10, 10],
            "goal_point": [25, 25],
            "max_slope_deg": 15.0,
        },
    )
    assert res.status_code == 201
    route_data = res.json()
    assert route_data["success"] is True
    route_id = route_data["route_id"]

    # 2. Get route details
    res = client.get(f"/v1/planner/routes/{route_id}")
    assert res.status_code == 200
    details = res.json()
    assert len(details["waypoints"]) > 0

    # 3. What-if analysis
    res = client.post(
        "/v1/planner/whatif",
        json={
            "base_route_id": route_id,
            "max_slope_deg": 12.0,
            "battery_capacity_wh": 600.0,
        },
    )
    assert res.status_code == 200
    whatif = res.json()
    assert "delta_distance_m" in whatif
    alt_id = whatif["alternative_route_id"]

    # 4. Compare routes
    res = client.get(f"/v1/planner/compare?a={route_id}&b={alt_id}")
    assert res.status_code == 200
    comp = res.json()
    assert "route_a" in comp
    assert "route_b" in comp
    assert "delta" in comp
