#!/usr/bin/env python3
"""CLI utility for local development to obtain access tokens from Keycloak.

Security rules:
- Strictly dev-only.
- Refuses non-localhost issuers.
- Uses fake dev credentials only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import struct
import sys
import time
import urllib.parse
import urllib.request

# Default dev seed credentials
DEV_PASSWORD = "DevPassword123!"
DEV_SERVICE_SECRET = "dev-service-secret-fake-12345"

MFA_USER_SECRETS: dict[str, str] = {
    "approver": "JBSWY3DPEHPK3PXP",
    "second_approver": "JBSWY3DPEHPK3PXQ",
    "admin": "JBSWY3DPEHPK3PXR",
}


def generate_totp_utf8(secret: str) -> str:
    """Generate 6-digit TOTP code matching Keycloak's UTF-8 secret interpretation."""
    key = secret.encode("utf-8")
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


def ensure_test_client(keycloak_url: str) -> None:
    """Ensure the direct-grant test client exists in Keycloak (dev only)."""
    # Obtain admin access token
    admin_auth = urllib.parse.urlencode(
        {
            "client_id": "admin-cli",
            "username": "admin",
            "password": "dev-only-change-me",
            "grant_type": "password",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{keycloak_url}/realms/master/protocol/openid-connect/token",
        data=admin_auth,
    )
    with urllib.request.urlopen(req) as resp:
        admin_token = json.loads(resp.read().decode("utf-8"))["access_token"]

    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    # Check if selene-test-client already exists
    req_check = urllib.request.Request(
        f"{keycloak_url}/admin/realms/selene/clients?clientId=selene-test-client",
        headers=headers,
    )
    with urllib.request.urlopen(req_check) as resp:
        clients = json.loads(resp.read().decode("utf-8"))
        if clients:
            return

    # Create direct-grant test client
    client_payload = {
        "clientId": "selene-test-client",
        "name": "Selene Direct-Grant Test Client (Dev Only)",
        "enabled": True,
        "publicClient": True,
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": False,
        "defaultClientScopes": ["selene-default"],
    }
    req_create = urllib.request.Request(
        f"{keycloak_url}/admin/realms/selene/clients",
        data=json.dumps(client_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req_create):
        pass


def get_token(
    keycloak_url: str,
    user: str | None = None,
    service: str | None = None,
    otp: str | None = None,
) -> dict[str, str]:
    # Enforce localhost-only security rule
    parsed = urllib.parse.urlparse(keycloak_url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(
            f"Security violation: Refusing non-localhost Keycloak issuer: {keycloak_url}. "
            "get_token.py is strictly for local dev/testing."
        )

    token_endpoint = f"{keycloak_url}/realms/selene/protocol/openid-connect/token"

    if service:
        # Service-to-service client credentials grant
        params = {
            "grant_type": "client_credentials",
            "client_id": service,
            "client_secret": DEV_SERVICE_SECRET,
        }
    else:
        username = user or "analyst"
        ensure_test_client(keycloak_url)
        params = {
            "grant_type": "password",
            "client_id": "selene-test-client",
            "username": username,
            "password": DEV_PASSWORD,
        }
        if username in MFA_USER_SECRETS:
            params["totp"] = otp or generate_totp_utf8(MFA_USER_SECRETS[username])

    req = urllib.request.Request(
        token_endpoint, data=urllib.parse.urlencode(params).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data: dict[str, str] = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as err:
        error_body = err.read().decode("utf-8")
        raise RuntimeError(f"Keycloak HTTP {err.code}: {error_body}") from err


def decode_jwt_payload(token: str) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    rem = len(parts[1]) % 4
    padded = parts[1] + ("=" * (4 - rem) if rem else "")
    decoded: dict[str, object] = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    return decoded


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Keycloak JWT access token for dev/testing.")
    parser.add_argument(
        "--url",
        default="http://localhost:8081",
        help="Keycloak base URL (must be localhost).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--user",
        default="analyst",
        help="Seed username (analyst, operator, approver, second_approver, steward, admin, auditor).",
    )
    group.add_argument(
        "--service",
        help="Service client ID (e.g., selene-service) for client_credentials grant.",
    )
    parser.add_argument("--otp", help="Specific 6-digit TOTP code (auto-generated if omitted).")
    parser.add_argument("--json", action="store_true", help="Output full JSON response.")

    args = parser.parse_args()

    try:
        token_data = get_token(
            keycloak_url=args.url,
            user=args.user if not args.service else None,
            service=args.service,
            otp=args.otp,
        )
    except (RuntimeError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(token_data, indent=2))
    else:
        access_token = token_data.get("access_token", "")
        payload = decode_jwt_payload(access_token)
        print("=== Access Token Payload ===")
        print(json.dumps(payload, indent=2))
        print("\n=== Raw Access Token ===")
        print(access_token)


if __name__ == "__main__":
    main()
