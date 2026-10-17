"""Live Keycloak integration tests for SelenePlan realm.

Validates:
- Live JWKS token verification using selene-auth (no mocks).
- Token claims for all seed users (roles, org_id, aud=selene-api).
- Admin-only role isolation (asserts admin token has no other roles and receives 403 on approver-only checks).
- Step-up MFA enforcement (approver/admin fail without OTP, succeed with OTP; acr/mfa_verified signals).
- Refresh token rotation and reuse detection (reuse invalidates the session).
- Service-to-service client credentials token (aud, client_id, no user roles).

Marked as integration test and skipped unless SELENE_LIVE=1.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
import time
import urllib.parse
import urllib.request
from typing import Any

import pytest
from selene_auth import JWKSCache, JWTValidator, Principal, require_roles

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8081")
REALM = "selene"
EXPECTED_ISSUER = f"{KEYCLOAK_BASE_URL}/realms/{REALM}"
JWKS_URL = f"{EXPECTED_ISSUER}/protocol/openid-connect/certs"
TOKEN_ENDPOINT = f"{EXPECTED_ISSUER}/protocol/openid-connect/token"
AUDIENCE = "selene-api"
DEV_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEV_PASSWORD = "DevPassword123!"
DEV_TOTP_SECRET = "JBSWY3DPEHPK3PXP"
DEV_SERVICE_SECRET = "dev-service-secret-fake-12345"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SELENE_LIVE") != "1",
        reason="Requires live Keycloak container with SELENE_LIVE=1",
    ),
]


def generate_totp_utf8(secret: str) -> str:
    """Generate TOTP matching Keycloak's UTF-8 secret interpretation."""
    key = secret.encode("utf-8")
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


@pytest.fixture(scope="session", autouse=True)
def ensure_test_client_present() -> None:
    """Ensure the direct-grant test client exists in the live realm for integration tests."""
    admin_data = urllib.parse.urlencode(
        {
            "client_id": "admin-cli",
            "username": "admin",
            "password": "dev-only-change-me",
            "grant_type": "password",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{KEYCLOAK_BASE_URL}/realms/master/protocol/openid-connect/token",
        data=admin_data,
    )
    with urllib.request.urlopen(req) as resp:
        admin_token = json.loads(resp.read().decode("utf-8"))["access_token"]

    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    req_check = urllib.request.Request(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM}/clients?clientId=selene-test-client",
        headers=headers,
    )
    with urllib.request.urlopen(req_check) as resp:
        clients = json.loads(resp.read().decode("utf-8"))
        if clients:
            return

    client_payload = {
        "clientId": "selene-test-client",
        "name": "Selene Direct-Grant Test Client (Test Profile Only)",
        "enabled": True,
        "publicClient": True,
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": False,
        "defaultClientScopes": ["selene-default"],
    }
    req_create = urllib.request.Request(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM}/clients",
        data=json.dumps(client_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req_create):
        pass


@pytest.fixture(scope="session")
def jwt_validator() -> JWTValidator:
    """Instantiate a JWTValidator wired to live Keycloak JWKS endpoint without mocks."""
    cache = JWKSCache(jwks_url=JWKS_URL, min_refetch_interval_s=0.5)
    return JWTValidator(
        jwks_cache=cache,
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=AUDIENCE,
    )


def fetch_direct_grant_tokens(
    username: str,
    password: str = DEV_PASSWORD,
    totp: str | None = None,
) -> dict[str, Any]:
    """Execute direct grant password request against Keycloak."""
    params: dict[str, str] = {
        "grant_type": "password",
        "client_id": "selene-test-client",
        "username": username,
        "password": password,
    }
    if totp is not None:
        params["totp"] = totp

    req = urllib.request.Request(
        TOKEN_ENDPOINT, data=urllib.parse.urlencode(params).encode("utf-8")
    )
    with urllib.request.urlopen(req) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return data


USER_TOTP_SECRETS = {
    "approver": "JBSWY3DPEHPK3PXP",
    "second_approver": "JBSWY3DPEHPK3PXQ",
    "admin": "JBSWY3DPEHPK3PXR",
}


@pytest.fixture(scope="session")
def seed_user_tokens() -> dict[str, dict[str, Any]]:
    """Fetch live direct grant tokens for all seed users once per test session."""
    users = [
        ("analyst", False),
        ("operator", False),
        ("approver", True),
        ("second_approver", True),
        ("steward", False),
        ("admin", True),
        ("auditor", False),
    ]
    tokens: dict[str, dict[str, Any]] = {}
    for username, requires_mfa in users:
        totp = generate_totp_utf8(USER_TOTP_SECRETS[username]) if requires_mfa else None
        tokens[username] = fetch_direct_grant_tokens(username=username, totp=totp)
    return tokens


def test_live_keycloak_seed_users_tokens(
    jwt_validator: JWTValidator,
    seed_user_tokens: dict[str, dict[str, Any]],
) -> None:
    """Verify live tokens for every seed user against Keycloak JWKS with selene-auth."""
    expected_roles = {
        "analyst": "analyst",
        "operator": "operator",
        "approver": "approver",
        "second_approver": "approver",
        "steward": "steward",
        "admin": "admin",
        "auditor": "auditor",
    }
    mfa_users = {"approver", "second_approver", "admin"}

    for username, expected_role in expected_roles.items():
        token_resp = seed_user_tokens[username]
        access_token = token_resp["access_token"]

        # Validate with live JWKS (no mocks)
        principal = jwt_validator.verify_token(access_token)
        assert isinstance(principal, Principal)

        # Audience and org_id
        assert principal.claims["aud"] == AUDIENCE
        assert principal.org_id == DEV_ORG_ID

        # Role membership
        assert expected_role in principal.roles

        # MFA signal
        if username in mfa_users:
            assert principal.mfa_verified is True
            assert principal.claims.get("acr") == "2"
        else:
            assert principal.mfa_verified is False
            assert principal.claims.get("acr") == "1"


def test_live_keycloak_admin_only_privilege_isolation(
    jwt_validator: JWTValidator,
    seed_user_tokens: dict[str, dict[str, Any]],
) -> None:
    """Admin token must have ONLY the admin role and be rejected on approver-only checks."""
    admin_token = seed_user_tokens["admin"]["access_token"]
    principal = jwt_validator.verify_token(admin_token)

    # 1. Assert admin has NO other domain roles (ignoring Keycloak built-in defaults)
    ignored_builtins = {"default-roles-selene", "offline_access", "uma_authorization"}
    domain_roles = [r for r in principal.roles if r not in ignored_builtins]
    assert domain_roles == ["admin"]

    # 2. Test approver-only endpoint rejects admin token with 403 Forbidden
    dep = require_roles("approver")
    with pytest.raises(Exception) as exc_info:
        dep(principal)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_live_keycloak_mfa_step_up_enforcement(
    seed_user_tokens: dict[str, dict[str, Any]],
    jwt_validator: JWTValidator,
) -> None:
    """Approver without OTP must be rejected; approver with OTP succeeds with acr=2."""
    # 1. Approver without OTP => must fail (401 Unauthorized, no token issued)
    params_no_otp = {
        "grant_type": "password",
        "client_id": "selene-test-client",
        "username": "approver",
        "password": DEV_PASSWORD,
    }
    req_fail = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(params_no_otp).encode("utf-8"),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_fail:
        urllib.request.urlopen(req_fail)
    assert exc_fail.value.code == 401

    # 2. Approver token fetched with valid OTP has mfa_verified True and acr="2"
    approver_token = seed_user_tokens["approver"]["access_token"]
    approver_principal = jwt_validator.verify_token(approver_token)
    assert approver_principal.mfa_verified is True
    assert approver_principal.claims.get("acr") == "2"

    # 3. Analyst (password-only) token has mfa_verified False and acr="1"
    analyst_token = seed_user_tokens["analyst"]["access_token"]
    analyst_principal = jwt_validator.verify_token(analyst_token)
    assert analyst_principal.mfa_verified is False
    assert analyst_principal.claims.get("acr") == "1"


def test_live_keycloak_refresh_token_rotation_and_reuse_invalidation() -> None:
    """Reusing an old refresh token must trigger reuse detection and invalidate session."""
    # 1. Initial login
    tokens1 = fetch_direct_grant_tokens(username="analyst")
    refresh_token_1 = tokens1["refresh_token"]

    # 2. Legitimate refresh: exchange refresh_token_1 for new tokens
    refresh_params = {
        "grant_type": "refresh_token",
        "client_id": "selene-test-client",
        "refresh_token": refresh_token_1,
    }
    req_refresh = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(refresh_params).encode("utf-8"),
    )
    with urllib.request.urlopen(req_refresh) as resp:
        tokens2 = json.loads(resp.read().decode("utf-8"))
        refresh_token_2 = tokens2["refresh_token"]
        assert refresh_token_2 != refresh_token_1

    # 3. REUSE: Re-submit the already used refresh_token_1
    req_reuse = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(refresh_params).encode("utf-8"),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_reuse:
        urllib.request.urlopen(req_reuse)
    # Keycloak returns 400 Bad Request on refresh token reuse
    assert exc_reuse.value.code == 400
    error_body = exc_reuse.value.read().decode("utf-8")
    assert "invalid_grant" in error_body

    # 4. Session Invalidation: Even the legitimate refresh_token_2 must now be dead
    req_revoked = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "client_id": "selene-test-client",
                "refresh_token": refresh_token_2,
            }
        ).encode("utf-8"),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_revoked:
        urllib.request.urlopen(req_revoked)
    assert exc_revoked.value.code == 400


def test_live_keycloak_service_token(jwt_validator: JWTValidator) -> None:
    """Verify selene-service client credentials token (aud=selene-api, client_id, no user roles)."""
    params = {
        "grant_type": "client_credentials",
        "client_id": "selene-service",
        "client_secret": DEV_SERVICE_SECRET,
    }
    req = urllib.request.Request(
        TOKEN_ENDPOINT, data=urllib.parse.urlencode(params).encode("utf-8")
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        service_token = data["access_token"]

    principal = jwt_validator.verify_token(service_token)
    assert principal.claims["aud"] == AUDIENCE
    assert (
        principal.claims.get("azp") == "selene-service"
        or principal.claims.get("client_id") == "selene-service"
    )

    # User domain roles must not be granted to service credentials
    domain_roles = {"analyst", "operator", "approver", "steward", "admin", "auditor"}
    assert not any(r in domain_roles for r in principal.roles)
