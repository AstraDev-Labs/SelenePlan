"""Approval gate and two-person rule enforcement for ML model registry."""


class ApprovalGateError(Exception):
    """Raised when a model fails metric thresholds or two-person approval rules."""

    pass


def evaluate_metric_gate(
    measured_metrics: dict[str, float],
    thresholds: dict[str, float],
) -> tuple[bool, list[str]]:
    """Verify that all measured metrics meet or exceed required thresholds."""
    violations: list[str] = []

    # Check precision
    if "min_precision" in thresholds:
        val = measured_metrics.get("precision", 0.0)
        req = thresholds["min_precision"]
        if val < req:
            violations.append(f"Precision {val:.3f} is below required threshold {req:.3f}")

    # Check recall
    if "min_recall" in thresholds:
        val = measured_metrics.get("recall", 0.0)
        req = thresholds["min_recall"]
        if val < req:
            violations.append(f"Recall {val:.3f} is below required threshold {req:.3f}")

    # Check F1
    if "min_f1" in thresholds:
        val = measured_metrics.get("f1", 0.0)
        req = thresholds["min_f1"]
        if val < req:
            violations.append(f"F1 {val:.3f} is below required threshold {req:.3f}")

    # Check small crater recall
    if "min_small_crater_recall" in thresholds:
        val = measured_metrics.get("recall_small", 0.0)
        req = thresholds["min_small_crater_recall"]
        if val < req:
            violations.append(
                f"Small crater recall {val:.3f} is below required threshold {req:.3f}"
            )

    return len(violations) == 0, violations


def check_two_person_rule(creator_id: str, approver_id: str) -> bool:
    """Enforce two-person separation of duty: approver must be distinct from creator."""
    if not creator_id or not approver_id:
        return False
    return creator_id.strip() != approver_id.strip()
