"""Unit tests for Hello Service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from selene_auth import Principal, set_global_jwt_validator
from selene_auth.jwt import AuthError

from hello_service.main import app


class DummyValidator:
    def verify_token(self, token: str) -> Principal:
        if token == "valid-analyst-token":
            return Principal(
                sub="user-123",
                roles=["analyst"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=False,
            )
        if token == "valid-approver-token":
            return Principal(
                sub="user-456",
                roles=["approver"],
                org_id="00000000-0000-0000-0000-000000000001",
                mfa_verified=True,
            )
        raise AuthError(code="invalid_token", message="Invalid token in test")


@pytest.fixture(autouse=True)
def setup_validator() -> None:
    set_global_jwt_validator(DummyValidator())  # type: ignore[arg-type]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz(client: TestClient) -> None:
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_metrics(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


def test_hello_unauthorized(client: TestClient) -> None:
    resp = client.get("/v1/hello")
    assert resp.status_code == 401


def test_hello_invalid_token(client: TestClient) -> None:
    resp = client.get("/v1/hello", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "invalid_token"


def test_hello_authorized_analyst(client: TestClient) -> None:
    resp = client.get("/v1/hello", headers={"Authorization": "Bearer valid-analyst-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "hello-service"
    assert data["sub"] == "user-123"
    assert data["roles"] == ["analyst"]
    assert data["org_id"] == "00000000-0000-0000-0000-000000000001"
    assert data["mfa_verified"] is False


def test_hello_authorized_approver(client: TestClient) -> None:
    resp = client.get("/v1/hello", headers={"Authorization": "Bearer valid-approver-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["roles"] == ["approver"]
    assert data["mfa_verified"] is True


def test_hello_post_echo(client: TestClient) -> None:
    resp = client.post(
        "/v1/hello",
        json={"greeting": "lunar greetings"},
        headers={"Authorization": "Bearer valid-analyst-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "received",
        "keys": ["greeting"],
        "sub": "user-123",
    }
