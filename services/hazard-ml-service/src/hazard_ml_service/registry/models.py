"""Model registry and secure session loading for hazard-ml-service."""

from datetime import UTC, datetime
from typing import Any

import onnxruntime as ort
from hazard_ml_service.events.publisher import create_audit_event
from hazard_ml_service.registry.gate import (
    ApprovalGateError,
    check_two_person_rule,
    evaluate_metric_gate,
)
from hazard_ml_service.registry.signature import (
    compute_sha256,
    sign_model_manifest,
    verify_model_signature,
)
from pydantic import BaseModel, Field


class SecurityIntegrityError(Exception):
    """Raised when an ONNX model fails integrity, signature, or approval checks."""


class ModelCard(BaseModel):
    model_id: str
    version: str
    name: str
    architecture: str
    description: str
    intended_use: str
    thresholds: dict[str, float] = Field(default_factory=dict)
    measured_metrics: dict[str, float] = Field(default_factory=dict)
    training_manifest: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class RegisteredModelRecord(BaseModel):
    model_id: str
    version: str
    sha256: str
    signature: str
    approved: bool = False
    created_by: str
    approved_by: str | None = None
    created_at: str
    approved_at: str | None = None
    model_card: dict[str, Any]


class ModelRegistry:
    """Manages models, cryptographic signatures, approval gates, and secure runtime loading."""

    def __init__(self) -> None:
        self._models: dict[str, RegisteredModelRecord] = {}
        self._binaries: dict[str, bytes] = {}
        self._audit_events: list[Any] = []

    def register_model(
        self,
        model_card: ModelCard,
        onnx_bytes: bytes,
        created_by: str,
        signature: str | None = None,
    ) -> RegisteredModelRecord:
        """Register a new candidate model. Computes SHA-256 and signs manifest if key available."""
        model_id = model_card.model_id
        sha256_hash = compute_sha256(onnx_bytes)

        # If no external signature is provided, sign using registry Vault Transit key
        if not signature:
            signature = sign_model_manifest(model_id, model_card.version, sha256_hash)

        record = RegisteredModelRecord(
            model_id=model_id,
            version=model_card.version,
            sha256=sha256_hash,
            signature=signature,
            approved=False,
            created_by=created_by,
            created_at=datetime.now(UTC).isoformat(),
            model_card=model_card.model_dump(),
        )

        self._models[model_id] = record
        self._binaries[model_id] = onnx_bytes

        audit = create_audit_event(
            action="model.registered",
            actor_id=created_by,
            target_id=model_id,
            target_type="ml_model",
            status="SUCCESS",
            details={"sha256": sha256_hash, "version": model_card.version},
        )
        self._audit_events.append(audit)
        return record

    def approve_model(self, model_id: str, approver_id: str) -> RegisteredModelRecord:
        """Approve a model after verifying metric thresholds and two-person rule."""
        if model_id not in self._models:
            raise KeyError(f"Model {model_id} not found in registry")

        record = self._models[model_id]

        # 1. Enforce two-person separation of duty
        if not check_two_person_rule(record.created_by, approver_id):
            audit = create_audit_event(
                action="model.approval.denied",
                actor_id=approver_id,
                target_id=model_id,
                target_type="ml_model",
                status="DENIED_SAME_APPROVER",
                details={"reason": "Approver cannot be the same as creator"},
            )
            self._audit_events.append(audit)
            raise ApprovalGateError(
                "Violation of two-person rule: Approver must be distinct from creator"
            )

        # 2. Enforce metrics gate
        card = record.model_card
        thresholds = card.get("thresholds", {})
        metrics = card.get("measured_metrics", {})
        passed, violations = evaluate_metric_gate(metrics, thresholds)

        if not passed:
            audit = create_audit_event(
                action="model.approval.denied",
                actor_id=approver_id,
                target_id=model_id,
                target_type="ml_model",
                status="DENIED_METRICS_GATE",
                details={"violations": violations},
            )
            self._audit_events.append(audit)
            raise ApprovalGateError(f"Model failed metric gate: {', '.join(violations)}")

        # Mark approved
        record.approved = True
        record.approved_by = approver_id
        record.approved_at = datetime.now(UTC).isoformat()

        audit = create_audit_event(
            action="model.approved",
            actor_id=approver_id,
            target_id=model_id,
            target_type="ml_model",
            status="SUCCESS",
            details={"approved_by": approver_id},
        )
        self._audit_events.append(audit)
        return record

    def get_model(self, model_id: str) -> RegisteredModelRecord:
        """Retrieve model metadata."""
        if model_id not in self._models:
            raise KeyError(f"Model {model_id} not found in registry")
        return self._models[model_id]

    def list_models(self) -> list[RegisteredModelRecord]:
        """List all models in registry."""
        return list(self._models.values())

    def get_audit_events(self) -> list[Any]:
        """Get emitted audit events."""
        return list(self._audit_events)

    def load_model_session(self, model_id: str) -> ort.InferenceSession:
        """Securely verify integrity, signature, and approval status, returning an ONNX Runtime session."""
        if model_id not in self._models or model_id not in self._binaries:
            raise KeyError(f"Model {model_id} not found")

        record = self._models[model_id]
        binary = self._binaries[model_id]

        # 1. Operational Approval Check
        if not record.approved:
            audit = create_audit_event(
                action="model.load.refused",
                actor_id="system",
                target_id=model_id,
                target_type="ml_model",
                status="REFUSED_NOT_APPROVED",
                details={"reason": "Model is not marked approved for operational inference"},
            )
            self._audit_events.append(audit)
            raise SecurityIntegrityError(
                f"Model {model_id} is not approved for operational use (SEC-09, T7)"
            )

        # 2. Cryptographic Checksum Check (Tamper Detection)
        computed_hash = compute_sha256(binary)
        if computed_hash != record.sha256:
            audit = create_audit_event(
                action="model.load.tampered",
                actor_id="system",
                target_id=model_id,
                target_type="ml_model",
                status="INTEGRITY_TAMPER_ALERT",
                details={"expected_hash": record.sha256, "actual_hash": computed_hash},
            )
            self._audit_events.append(audit)
            raise SecurityIntegrityError(
                f"Model {model_id} binary checksum mismatch! Potential tampering detected (T7)"
            )

        # 3. Signature Verification
        if not verify_model_signature(model_id, record.version, record.sha256, record.signature):
            audit = create_audit_event(
                action="model.load.unsigned_or_invalid",
                actor_id="system",
                target_id=model_id,
                target_type="ml_model",
                status="SIGNATURE_VERIFICATION_FAILED",
                details={"signature": record.signature},
            )
            self._audit_events.append(audit)
            raise SecurityIntegrityError(
                f"Model {model_id} cryptographic signature is invalid or unsigned (T7)"
            )

        # 4. Safe Load via ONNX Runtime CPU Provider
        session = ort.InferenceSession(binary, providers=["CPUExecutionProvider"])
        return session


# Global default registry instance
GLOBAL_MODEL_REGISTRY = ModelRegistry()
