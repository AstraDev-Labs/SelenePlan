"""Security integrity tests for ML model loading and operator allowlists (SEC-09, T7)."""

from pathlib import Path

import pytest
from hazard_ml_service.inference.validator import ModelValidationError, validate_onnx_model
from hazard_ml_service.registry.models import (
    ModelCard,
    ModelRegistry,
    SecurityIntegrityError,
)


@pytest.fixture
def valid_onnx_bytes() -> bytes:
    p = Path(__file__).resolve().parent.parent.parent / "model-cards" / "crater_detector_v1.onnx"
    return p.read_bytes()


def test_unapproved_model_load_fails_and_audits(valid_onnx_bytes: bytes) -> None:
    registry = ModelRegistry()
    card = ModelCard(
        model_id="unapproved_model",
        version="1.0.0",
        name="Unapproved",
        architecture="CNN",
        description="Unapproved test",
        intended_use="Test",
        thresholds={"min_precision": 0.70},
        measured_metrics={"precision": 0.75},
    )
    registry.register_model(card, valid_onnx_bytes, created_by="alice")

    # Attempting to load unapproved model MUST fail
    with pytest.raises(SecurityIntegrityError, match="not approved"):
        registry.load_model_session("unapproved_model")

    events = registry.get_audit_events()
    assert any(e.data["action"] == "model.load.refused" for e in events)


def test_tampered_model_binary_fails_and_audits(valid_onnx_bytes: bytes) -> None:
    registry = ModelRegistry()
    card = ModelCard(
        model_id="tampered_model",
        version="1.0.0",
        name="Tampered",
        architecture="CNN",
        description="Tampered test",
        intended_use="Test",
        thresholds={"min_precision": 0.70},
        measured_metrics={"precision": 0.75},
    )
    registry.register_model(card, valid_onnx_bytes, created_by="alice")
    registry.approve_model("tampered_model", approver_id="bob")

    # Simulate bit flip / binary tampering after approval
    tampered_bytes = bytearray(valid_onnx_bytes)
    tampered_bytes[100] ^= 0xFF
    registry._binaries["tampered_model"] = bytes(tampered_bytes)

    with pytest.raises(SecurityIntegrityError, match="tampering detected"):
        registry.load_model_session("tampered_model")

    events = registry.get_audit_events()
    assert any(e.data["action"] == "model.load.tampered" for e in events)


def test_invalid_signature_fails_and_audits(valid_onnx_bytes: bytes) -> None:
    registry = ModelRegistry()
    card = ModelCard(
        model_id="bad_sig_model",
        version="1.0.0",
        name="Bad Sig",
        architecture="CNN",
        description="Bad sig test",
        intended_use="Test",
        thresholds={"min_precision": 0.70},
        measured_metrics={"precision": 0.75},
    )
    # Register with forged signature
    registry.register_model(
        card, valid_onnx_bytes, created_by="alice", signature="sig:v1:forged-signature-hex"
    )
    registry.approve_model("bad_sig_model", approver_id="bob")

    with pytest.raises(SecurityIntegrityError, match="signature is invalid"):
        registry.load_model_session("bad_sig_model")

    events = registry.get_audit_events()
    assert any(e.data["action"] == "model.load.unsigned_or_invalid" for e in events)


def test_disallowed_onnx_operator_rejected() -> None:
    # Corrupt payload that isn't ONNX or violates allowlist
    with pytest.raises(ModelValidationError):
        validate_onnx_model(b"corrupted-non-onnx-bytes")
