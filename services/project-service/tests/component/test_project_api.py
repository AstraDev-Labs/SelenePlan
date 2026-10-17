"""Component tests for project-service HTTP API endpoints.

Per services/project-service/SPEC.md:
- Acceptance Criterion 1: Cross-project access denied (403).
- Acceptance Criterion 6: Idempotency-Key replays return original response.
"""

import pytest
from fastapi.testclient import TestClient
from project_service.api.app import app


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
    assert "project_runs_total" in res.text


def test_project_crud_and_cross_project_isolation(client: TestClient) -> None:
    # 1. Create new project
    res = client.post(
        "/v1/projects",
        json={
            "name": "Amundsen Rim Base",
            "description": "Amundsen crater exploration",
            "org_id": "org-artemis",
            "members": ["user-lead-amundsen"],
        },
    )
    assert res.status_code == 201
    proj_data = res.json()
    proj_id = proj_data["project_id"]

    # 2. Get project details
    res = client.get(f"/v1/projects/{proj_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Amundsen Rim Base"

    # 3. Create plan in proj-shackleton
    res = client.post(
        "/v1/projects/proj-shackleton/plans",
        json={
            "name": "Shackleton Traverse Plan",
            "author_id": "user-analyst",
            "payload": {"waypoints": [[10, 10], [10, 20]]},
        },
    )
    assert res.status_code == 201
    plan_id = res.json()["plan_id"]

    # 4. Attempt to access this plan using a different project_id -> 403 Forbidden
    res = client.get(f"/v1/projects/{proj_id}/plans/{plan_id}")
    assert res.status_code == 403


def test_run_start_with_idempotency_key(client: TestClient) -> None:
    idemp_key = "idemp-key-run-999"
    payload = {
        "scenario_id": "scen-polar-winter",
        "aoi_id": "aoi-shackleton",
    }

    # First attempt
    res1 = client.post(
        "/v1/projects/proj-shackleton/runs",
        json=payload,
        headers={"Idempotency-Key": idemp_key},
    )
    assert res1.status_code == 202
    data1 = res1.json()
    run_id1 = data1["run_id"]

    # Replay with same Idempotency-Key
    res2 = client.post(
        "/v1/projects/proj-shackleton/runs",
        json=payload,
        headers={"Idempotency-Key": idemp_key},
    )
    assert res2.status_code == 202
    data2 = res2.json()
    assert data2["run_id"] == run_id1


def test_plan_submission_and_two_person_approval_api(client: TestClient) -> None:
    # 1. Create plan
    res = client.post(
        "/v1/projects/proj-shackleton/plans",
        json={
            "name": "Golden Traverse Path",
            "author_id": "user-author",
            "payload": {"waypoints": [[5, 2], [5, 8]], "energy_wh": 480.0},
        },
    )
    assert res.status_code == 201
    plan_id = res.json()["plan_id"]
    version_id = res.json()["version_id"]

    # 2. Submit plan
    res = client.post(
        f"/v1/plans/{plan_id}/versions/{version_id}/submit",
        json={"user_id": "user-analyst", "user_role": "analyst"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_review"

    # 3. First approval (user-approver-1)
    res = client.post(
        f"/v1/plans/{plan_id}/versions/{version_id}/decision",
        json={
            "user_id": "user-approver-1",
            "user_role": "approver",
            "decision": "approve",
            "mfa_verified": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_review"

    # 4. Second approval (user-approver-2)
    res = client.post(
        f"/v1/plans/{plan_id}/versions/{version_id}/decision",
        json={
            "user_id": "user-approver-2",
            "user_role": "approver",
            "decision": "approve",
            "mfa_verified": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
