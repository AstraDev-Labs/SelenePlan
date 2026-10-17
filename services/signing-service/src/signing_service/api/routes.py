"""FastAPI routes for signing-service: canonical signing, verification, and key metadata."""

from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from signing_service.canonical.jcs import canonical_digest, canonical_sha256
from signing_service.vault_client.transit import VaultTransitEngine

router = APIRouter()
ENGINE = VaultTransitEngine(key_id="selene-plan-signing")
SIGNATURE_REGISTRY: dict[str, dict[str, Any]] = {}
AUDIT_LOGS: list[dict[str, Any]] = []


# --- Request / Response Models ---


class ApprovalRecord(BaseModel):
    user_id: str
    decision: str
    mfa_verified: bool = True
    timestamp: str | None = None


class ApprovalEvidence(BaseModel):
    approvals: list[ApprovalRecord]
    rejections: list[ApprovalRecord] = Field(default_factory=list)
    policy_version: str = "v1.0"


class SignRequest(BaseModel):
    plan_id: str
    plan_version_id: str
    payload: dict[str, Any]
    submitted_hash: str
    approval_evidence: ApprovalEvidence


class VerifyRequest(BaseModel):
    payload: dict[str, Any]
    signature_bundle: dict[str, Any]


# --- Internal Sign Endpoint ---


@router.post("/internal/v1/sign", status_code=status.HTTP_200_OK)
async def sign_plan(req: SignRequest) -> dict[str, Any]:
    """Internal endpoint for signing approved plan payloads."""
    # 1. Idempotency: return existing signature if already signed
    if req.plan_version_id in SIGNATURE_REGISTRY:
        return SIGNATURE_REGISTRY[req.plan_version_id]

    # 2. Re-verify approval evidence: must have >= 2 distinct approvers and 0 rejections
    approver_ids = {
        a.user_id
        for a in req.approval_evidence.approvals
        if a.decision == "approve" and a.mfa_verified
    }
    if len(approver_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Signing refused: insufficient approvals ({len(approver_ids)} valid approvers, requires 2)",
        )
    if len(req.approval_evidence.rejections) > 0:
        raise HTTPException(
            status_code=400,
            detail="Signing refused: plan contains active rejections",
        )

    # 3. Canonicalize payload and check against submitted hash
    computed_hash = canonical_sha256(req.payload)
    if computed_hash != req.submitted_hash:
        raise HTTPException(
            status_code=400,
            detail=f"Signing refused: payload canonical hash mismatch. Computed: {computed_hash}, Submitted: {req.submitted_hash}",
        )

    # 4. Sign pre-hashed digest using Vault Transit
    digest = canonical_digest(req.payload)
    sig_str, key_ver = ENGINE.sign(digest)
    nonce = secrets.token_hex(16)
    timestamp = int(time.time())

    record = {
        "plan_id": req.plan_id,
        "plan_version_id": req.plan_version_id,
        "payload_sha256": computed_hash,
        "key_id": ENGINE.key_id,
        "key_version": key_ver,
        "algorithm": "Ed25519",
        "signature": sig_str,
        "nonce": nonce,
        "timestamp": timestamp,
        "public_key_b64": ENGINE.get_public_key_raw_b64(key_ver),
    }

    SIGNATURE_REGISTRY[req.plan_version_id] = record

    AUDIT_LOGS.append(
        {
            "action": "plan.signed",
            "plan_id": req.plan_id,
            "plan_version_id": req.plan_version_id,
            "payload_sha256": computed_hash,
            "key_id": ENGINE.key_id,
            "key_version": key_ver,
            "timestamp": timestamp,
        }
    )

    return record


# --- Public Verification Endpoint ---


@router.post("/v1/verify")
async def verify_signature(req: VerifyRequest) -> dict[str, Any]:
    """Verify digital signature on a canonical plan payload."""
    bundle = req.signature_bundle
    key_id = bundle.get("key_id", ENGINE.key_id)
    key_version = int(bundle.get("key_version", 1))
    sig_str = bundle.get("signature", "")
    expected_hash = bundle.get("payload_sha256", "")

    # 1. Canonicalize provided payload
    computed_hash = canonical_sha256(req.payload)
    if computed_hash != expected_hash:
        AUDIT_LOGS.append(
            {
                "action": "verify.failed",
                "reason": "HASH_MISMATCH",
                "computed_hash": computed_hash,
                "expected_hash": expected_hash,
            }
        )
        return {
            "valid": False,
            "reason": f"Payload hash mismatch (computed {computed_hash} != expected {expected_hash})",
            "payload_sha256": computed_hash,
            "key_id": key_id,
            "key_version": key_version,
        }

    # 2. Verify signature with key
    digest = canonical_digest(req.payload)
    valid = ENGINE.verify(digest, sig_str, key_version)

    AUDIT_LOGS.append(
        {
            "action": "verify.result",
            "valid": valid,
            "payload_sha256": computed_hash,
            "key_id": key_id,
            "key_version": key_version,
        }
    )

    return {
        "valid": valid,
        "reason": "Signature verified successfully" if valid else "Cryptographic signature invalid",
        "payload_sha256": computed_hash,
        "key_id": key_id,
        "key_version": key_version,
    }


# --- Key Management Endpoints ---


@router.get("/v1/keys/{key_id}/public")
async def get_public_key(key_id: str, version: int | None = None) -> dict[str, Any]:
    if key_id != ENGINE.key_id:
        raise HTTPException(status_code=404, detail=f"Key {key_id} not found")

    v = version or ENGINE.active_version
    try:
        pub_b64 = ENGINE.get_public_key_raw_b64(v)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "key_id": key_id,
        "key_version": v,
        "algorithm": "Ed25519",
        "public_key_b64": pub_b64,
    }


@router.get("/v1/keys")
async def get_keys() -> dict[str, Any]:
    return ENGINE.get_key_metadata()


@router.post("/internal/v1/keys/rotate")
async def rotate_signing_key() -> dict[str, Any]:
    new_version = ENGINE.rotate_key()
    return {
        "status": "rotated",
        "key_id": ENGINE.key_id,
        "new_active_version": new_version,
    }
