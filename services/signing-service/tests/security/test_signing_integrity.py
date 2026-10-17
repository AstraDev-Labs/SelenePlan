"""Security and integrity tests for signing-service.

Per services/signing-service/SPEC.md:
- AC 2: Single byte tamper fails verification.
- AC 3: Signing refused without valid approval evidence.
- AC 4: Old key signature verifies after rotation.
- AC 5: Offline verification matches.
- AC 6: Re-sign of same version is idempotent.
- AC 7: Audit logs exist.
"""

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from signing_service.api.app import app
from signing_service.api.routes import AUDIT_LOGS
from signing_service.canonical.jcs import canonical_sha256

from tools.verify_bundle import verify_bundle_data


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_complete_signing_verification_and_tamper_detection(client: TestClient) -> None:
    payload = {
        "plan_id": "plan-shackleton-001",
        "waypoints": [[8, 2], [8, 10], [8, 18]],
        "safe_speed_mps": 0.1,
    }
    sub_hash = canonical_sha256(payload)

    # 1. Sign plan with valid 2-person approval evidence
    sign_res = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-shackleton-001",
            "plan_version_id": "pv-alpha",
            "payload": payload,
            "submitted_hash": sub_hash,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-app-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-app-2", "decision": "approve", "mfa_verified": True},
                ],
                "rejections": [],
            },
        },
    )
    assert sign_res.status_code == 200
    bundle = sign_res.json()
    assert bundle["signature"].startswith("vault:v1:")

    # AC 6: Re-sign returns exact original signature
    re_res = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-shackleton-001",
            "plan_version_id": "pv-alpha",
            "payload": payload,
            "submitted_hash": sub_hash,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-app-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-app-2", "decision": "approve", "mfa_verified": True},
                ],
            },
        },
    )
    assert re_res.status_code == 200
    assert re_res.json() == bundle

    # 2. Verify with valid payload -> True
    verify_res = client.post(
        "/v1/verify",
        json={"payload": payload, "signature_bundle": bundle},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True

    # 3. AC 5: Offline verification tool
    valid, _msg = verify_bundle_data({"payload": payload, "signature_bundle": bundle})
    assert valid is True

    # 4. AC 2: Single-byte tamper in payload -> verification MUST fail!
    tampered_payload = copy.deepcopy(payload)
    tampered_payload["safe_speed_mps"] = 0.2  # subtle change

    tamper_res = client.post(
        "/v1/verify",
        json={"payload": tampered_payload, "signature_bundle": bundle},
    )
    assert tamper_res.status_code == 200
    assert tamper_res.json()["valid"] is False

    valid_offline, _msg_offline = verify_bundle_data(
        {"payload": tampered_payload, "signature_bundle": bundle}
    )
    assert valid_offline is False


def test_signing_refusal_cases(client: TestClient) -> None:
    payload = {"mission": "Polar exploration"}
    sub_hash = canonical_sha256(payload)

    # Refused: only 1 approval
    res1 = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-refuse-1",
            "plan_version_id": "pv-refuse-1",
            "payload": payload,
            "submitted_hash": sub_hash,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-app-1", "decision": "approve", "mfa_verified": True}
                ],
                "rejections": [],
            },
        },
    )
    assert res1.status_code == 400
    assert "insufficient approvals" in res1.json()["detail"]

    # Refused: active rejection
    res2 = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-refuse-2",
            "plan_version_id": "pv-refuse-2",
            "payload": payload,
            "submitted_hash": sub_hash,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-app-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-app-2", "decision": "approve", "mfa_verified": True},
                ],
                "rejections": [{"user_id": "user-app-3", "decision": "reject"}],
            },
        },
    )
    assert res2.status_code == 400
    assert "contains active rejections" in res2.json()["detail"]

    # Refused: submitted hash mismatch
    res3 = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-refuse-3",
            "plan_version_id": "pv-refuse-3",
            "payload": payload,
            "submitted_hash": "ffff" * 16,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-app-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-app-2", "decision": "approve", "mfa_verified": True},
                ],
            },
        },
    )
    assert res3.status_code == 400
    assert "hash mismatch" in res3.json()["detail"]


def test_key_rotation_and_historical_verification(client: TestClient) -> None:
    # 1. Sign under Key Version 1
    payload = {"data": "historical_plan"}
    sub_hash = canonical_sha256(payload)
    res_v1 = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-v1",
            "plan_version_id": "pv-v1",
            "payload": payload,
            "submitted_hash": sub_hash,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-2", "decision": "approve", "mfa_verified": True},
                ],
            },
        },
    )
    bundle_v1 = res_v1.json()
    assert bundle_v1["key_version"] == 1

    # 2. Rotate Key -> Version 2 becomes active
    rotate_res = client.post("/internal/v1/keys/rotate")
    assert rotate_res.status_code == 200
    assert rotate_res.json()["new_active_version"] >= 2

    # 3. Sign a new plan -> signed with new version
    payload2 = {"data": "future_plan"}
    sub_hash2 = canonical_sha256(payload2)
    res_v2 = client.post(
        "/internal/v1/sign",
        json={
            "plan_id": "plan-v2",
            "plan_version_id": "pv-v2",
            "payload": payload2,
            "submitted_hash": sub_hash2,
            "approval_evidence": {
                "approvals": [
                    {"user_id": "user-1", "decision": "approve", "mfa_verified": True},
                    {"user_id": "user-2", "decision": "approve", "mfa_verified": True},
                ],
            },
        },
    )
    bundle_v2 = res_v2.json()
    assert bundle_v2["key_version"] >= 2

    # 4. AC 4: Verify the older version 1 signature STILL verifies after rotation!
    ver_v1 = client.post("/v1/verify", json={"payload": payload, "signature_bundle": bundle_v1})
    assert ver_v1.json()["valid"] is True

    # Verify version 2 signature also verifies
    ver_v2 = client.post("/v1/verify", json={"payload": payload2, "signature_bundle": bundle_v2})
    assert ver_v2.json()["valid"] is True

    # 5. AC 7: Audit events check
    assert len(AUDIT_LOGS) > 0
    actions = [log["action"] for log in AUDIT_LOGS]
    assert "plan.signed" in actions
    assert "verify.result" in actions
