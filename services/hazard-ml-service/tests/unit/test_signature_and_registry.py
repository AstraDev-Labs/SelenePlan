"""Unit tests for model registry, signature calculation, and gate enforcement."""

import pytest
from hazard_ml_service.registry.gate import (
    ApprovalGateError,
    check_two_person_rule,
    evaluate_metric_gate,
)
from hazard_ml_service.registry.models import (
    ModelCard,
    ModelRegistry,
)
from hazard_ml_service.registry.signature import (
    compute_sha256,
    sign_model_manifest,
    verify_model_signature,
)


def test_sha256_and_signature_verification() -> None:
    data = b"synthetic-test-onnx-bytes-payload"
    hash_val = compute_sha256(data)
    assert len(hash_val) == 64

    sig = sign_model_manifest("model-1", "1.0.0", hash_val)
    assert sig.startswith("sig:v1:")
    assert verify_model_signature("model-1", "1.0.0", hash_val, sig) is True

    # Tampered hash
    tampered_hash = compute_sha256(b"tampered-bytes")
    assert verify_model_signature("model-1", "1.0.0", tampered_hash, sig) is False

    # Tampered version
    assert verify_model_signature("model-1", "1.0.1", hash_val, sig) is False


def test_metric_gate_evaluation() -> None:
    thresholds = {
        "min_precision": 0.70,
        "min_recall": 0.70,
        "min_small_crater_recall": 0.65,
    }

    # Passing metrics
    good_metrics = {"precision": 0.75, "recall": 0.72, "recall_small": 0.80}
    passed, violations = evaluate_metric_gate(good_metrics, thresholds)
    assert passed is True
    assert len(violations) == 0

    # Failing precision
    bad_metrics = {"precision": 0.65, "recall": 0.80, "recall_small": 0.80}
    passed, violations = evaluate_metric_gate(bad_metrics, thresholds)
    assert passed is False
    assert any("Precision" in v for v in violations)


def test_two_person_rule() -> None:
    assert check_two_person_rule("steward-1", "steward-2") is True
    assert check_two_person_rule("steward-1", "steward-1") is False


def test_registry_registration_and_two_person_approval() -> None:
    registry = ModelRegistry()
    card = ModelCard(
        model_id="test_model_v1",
        version="1.0.0",
        name="Test Model",
        architecture="CNN",
        description="Testing card",
        intended_use="Unit tests",
        thresholds={"min_precision": 0.70, "min_recall": 0.70},
        measured_metrics={"precision": 0.75, "recall": 0.75},
    )
    onnx_bytes = b"valid-onnx-test-binary"
    reg = registry.register_model(card, onnx_bytes, created_by="alice")
    assert reg.approved is False

    # Same person tries to approve -> must fail
    with pytest.raises(ApprovalGateError, match="two-person rule"):
        registry.approve_model("test_model_v1", approver_id="alice")

    # Second person approves -> succeeds
    approved = registry.approve_model("test_model_v1", approver_id="bob")
    assert approved.approved is True
    assert approved.approved_by == "bob"
