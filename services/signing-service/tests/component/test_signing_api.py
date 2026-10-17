"""Component tests for signing-service system and metadata endpoints."""

import pytest
from fastapi.testclient import TestClient
from signing_service.api.app import app


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
    assert "signing_operations_total" in res.text


def test_keys_metadata_and_public_key_export(client: TestClient) -> None:
    # 1. Get keys metadata
    res = client.get("/v1/keys")
    assert res.status_code == 200
    data = res.json()
    assert data["key_id"] == "selene-plan-signing"
    assert "versions" in data

    # 2. Get active public key
    res = client.get("/v1/keys/selene-plan-signing/public")
    assert res.status_code == 200
    pub = res.json()
    assert "public_key_b64" in pub
    assert len(pub["public_key_b64"]) > 30

    # Non-existent key
    res = client.get("/v1/keys/non-existent-key/public")
    assert res.status_code == 404
