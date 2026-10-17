"""Gateway acceptance tests verifying AC 1 through AC 6."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from typing import Any

import httpx
import pytest

from scripts.get_token import get_token

GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "http://localhost:8080")
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8081")


def is_gateway_reachable() -> bool:
    try:
        # If rate limit is active from a prior run, allow up to 10s for token refill
        for _ in range(6):
            r = httpx.get(f"{GATEWAY_BASE_URL}/healthz", timeout=2.0)
            if r.status_code == 404:
                return True
            if r.status_code == 429:
                time.sleep(2)
            else:
                return False
        return False
    except httpx.RequestError:
        return False


live_gateway_only = pytest.mark.skipif(
    not is_gateway_reachable(),
    reason="Gateway not reachable on localhost:8080. Start infra/docker-compose.yml to run.",
)


def make_unverified_token(header: dict[str, Any], payload: dict[str, Any]) -> str:
    """Helper to produce unsigned base64url tokens (e.g. alg=none)."""
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{h_b64}.{p_b64}."


# AC 6: Gateway configuration validation in CI
def test_gateway_config_validation() -> None:
    """AC 6: Validate Envoy YAML configuration via envoy validate mode or docker."""
    envoy_bin = shutil.which("envoy")
    if envoy_bin:
        cmd = [envoy_bin, "-c", "infra/envoy.yaml", "--mode", "validate"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"Envoy validate failed: {res.stderr}"
    else:
        # Fall back to docker container validation
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{os.path.abspath('infra')}:/infra:ro",
            "envoyproxy/envoy:v1.30-latest",
            "-c",
            "/infra/envoy.yaml",
            "--mode",
            "validate",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"Docker envoy validate failed: {res.stderr}\n{res.stdout}"


# AC 1: Request authentication & token validation
@live_gateway_only
def test_ac1_no_token_returns_401() -> None:
    """Request without a token receives 401."""
    resp = httpx.get(f"{GATEWAY_BASE_URL}/v1/hello")
    assert resp.status_code == 401
    assert "jwt" in resp.text.lower() or "unauthorized" in resp.text.lower()


@live_gateway_only
def test_ac1_alg_none_returns_401() -> None:
    """Token with alg=none receives 401."""
    token = make_unverified_token(
        {"alg": "none", "typ": "JWT"},
        {"sub": "attacker", "iss": f"{KEYCLOAK_BASE_URL}/realms/selene", "aud": "selene-api"},
    )
    resp = httpx.get(f"{GATEWAY_BASE_URL}/v1/hello", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@live_gateway_only
def test_ac1_tampered_signature_returns_401() -> None:
    """Tampered token receives 401."""
    valid_token_data = get_token(keycloak_url=KEYCLOAK_BASE_URL, user="analyst")
    real_token = valid_token_data["access_token"]
    # Tamper with the last 5 characters of the signature
    tampered = real_token[:-5] + ("AAAAA" if not real_token.endswith("AAAAA") else "ZZZZZ")
    resp = httpx.get(
        f"{GATEWAY_BASE_URL}/v1/hello", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert resp.status_code == 401


@live_gateway_only
def test_ac1_wrong_audience_returns_401() -> None:
    """Token with wrong audience receives 401."""
    token = make_unverified_token(
        {"alg": "RS256", "typ": "JWT", "kid": "fake"},
        {
            "sub": "user",
            "iss": f"{KEYCLOAK_BASE_URL}/realms/selene",
            "aud": "wrong-audience",
            "exp": int(time.time()) + 300,
        },
    )
    resp = httpx.get(f"{GATEWAY_BASE_URL}/v1/hello", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@live_gateway_only
def test_ac1_expired_token_returns_401() -> None:
    """Expired token receives 401."""
    token = make_unverified_token(
        {"alg": "RS256", "typ": "JWT", "kid": "fake"},
        {
            "sub": "user",
            "iss": f"{KEYCLOAK_BASE_URL}/realms/selene",
            "aud": "selene-api",
            "exp": int(time.time()) - 3600,
        },
    )
    resp = httpx.get(f"{GATEWAY_BASE_URL}/v1/hello", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# AC 3: Body above size limit yields 413
@live_gateway_only
def test_ac3_payload_too_large_yields_413() -> None:
    """Body above the 10 MB limit yields 413 Payload Too Large."""
    valid_token_data = get_token(keycloak_url=KEYCLOAK_BASE_URL, user="analyst")
    headers = {
        "Authorization": f"Bearer {valid_token_data['access_token']}",
        "Content-Type": "application/octet-stream",
    }

    # Generate 11 MB payload (> 10485760 bytes)
    oversized_data = b"x" * (11 * 1024 * 1024)

    # Note: Envoy buffer filter immediately rejects with 413 when buffer threshold exceeded
    resp = httpx.post(
        f"{GATEWAY_BASE_URL}/v1/hello", headers=headers, content=oversized_data, timeout=30.0
    )
    assert resp.status_code == 413


# AC 4: /metrics and /healthz of upstreams are not reachable through the gateway
@live_gateway_only
@pytest.mark.parametrize(
    "blocked_path", ["/healthz", "/readyz", "/metrics", "/internal/secret", "/admin"]
)
def test_ac4_upstream_internals_unreachable_through_gateway(blocked_path: str) -> None:
    """Internal endpoints are blocked at gateway level and return 404."""
    resp = httpx.get(f"{GATEWAY_BASE_URL}{blocked_path}")
    assert resp.status_code in {401, 404}


# AC 5: Routes in the table work end to end with hello service in Phase 0
@live_gateway_only
def test_ac5_hello_service_end_to_end_analyst() -> None:
    """End-to-end hello route works for analyst user."""
    token_data = get_token(keycloak_url=KEYCLOAK_BASE_URL, user="analyst")
    resp = httpx.get(
        f"{GATEWAY_BASE_URL}/v1/hello",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "hello-service"
    assert "analyst" in payload["roles"]
    assert payload["org_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["mfa_verified"] is False
    assert payload["sub"] != ""


@live_gateway_only
def test_ac5_hello_service_end_to_end_approver_mfa() -> None:
    """End-to-end hello route works for approver with MFA verified."""
    token_data = get_token(keycloak_url=KEYCLOAK_BASE_URL, user="approver")
    resp = httpx.get(
        f"{GATEWAY_BASE_URL}/v1/hello",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert "approver" in payload["roles"]
    assert payload["mfa_verified"] is True


# AC 2: Exceeding rate limit yields 429 with Retry-After (runs last to prevent blocking other tests)
@live_gateway_only
def test_ac_last_rate_limit_exceeded_yields_429() -> None:
    """Exceeding the rate limit yields 429 with Retry-After header."""
    valid_token_data = get_token(keycloak_url=KEYCLOAK_BASE_URL, user="analyst")
    headers = {"Authorization": f"Bearer {valid_token_data['access_token']}"}

    client = httpx.Client(base_url=GATEWAY_BASE_URL, headers=headers)
    hit_429 = False
    retry_after_val: str | None = None

    # Envoy local rate limit token bucket is configured to 120 tokens max.
    # We blast up to 150 fast requests; once tokens exhaust, it must return 429.
    for _ in range(150):
        r = client.get("/v1/hello")
        if r.status_code == 429:
            hit_429 = True
            retry_after_val = r.headers.get("retry-after")
            break

    assert hit_429, "Expected to trigger 429 Too Many Requests after exceeding 120 burst"
    assert retry_after_val is not None, "Expected Retry-After header on 429 response"
