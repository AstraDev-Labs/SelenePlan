"""Workflow engine for Plan lifecycle and approvals.

Enforces rules defined in SPEC.md and policies/plan_workflow.rego:
- submit: Analyst/Admin in project members, plan in draft.
- decision: Approver/Admin, MFA verified, author != approver, not already decided.
- approved: Requires two distinct approvals, zero rejections.
- reject: Resets status to draft.
- signed: Immutable.
"""

from __future__ import annotations

import uuid
from typing import Any

from project_service.domain.models import (
    ApprovalDecision,
    DecisionType,
    PlanStatus,
    PlanVersion,
)


class WorkflowError(Exception):
    def __init__(self, message: str, code: str = "WORKFLOW_POLICY_VIOLATION") -> None:
        super().__init__(message)
        self.code = code


def submit_for_review(
    plan: PlanVersion,
    user_id: str,
    user_role: str,
    project_members: list[str],
) -> PlanVersion:
    """Submit a draft plan version for two-person review."""
    if plan.status != PlanStatus.DRAFT:
        raise WorkflowError(f"Cannot submit plan in state '{plan.status}': must be 'draft'")
    if user_role not in ("analyst", "admin"):
        raise WorkflowError(f"User role '{user_role}' cannot submit plan: must be analyst or admin")
    if user_id not in project_members:
        raise WorkflowError("User must be a member of the project to submit a plan")

    plan.payload_sha256 = plan.compute_hash()
    plan.status = PlanStatus.IN_REVIEW
    return plan


def record_decision(
    plan: PlanVersion,
    user_id: str,
    user_role: str,
    decision: DecisionType,
    mfa_verified: bool,
    comment: str | None = None,
) -> tuple[PlanVersion, ApprovalDecision]:
    """Record an approval decision from an authorized approver.

    Enforces:
    1. Plan must be in 'in_review'.
    2. Role must be 'approver' or 'admin'.
    3. MFA claim must be present.
    4. Author cannot approve own plan (four-eyes principle).
    5. Approver cannot decide twice on the same version.
    """
    if plan.status != PlanStatus.IN_REVIEW:
        raise WorkflowError(
            f"Cannot record decision on plan in state '{plan.status}': must be 'in_review'"
        )
    if user_role not in ("approver", "admin"):
        raise WorkflowError(
            f"Role '{user_role}' not authorized to approve plans: must be approver or admin"
        )
    if not mfa_verified:
        raise WorkflowError("MFA verification is required to approve or reject plans")
    if user_id == plan.author_id:
        raise WorkflowError("Author cannot approve or reject their own plan (four-eyes principle)")

    decided_users = {d.user_id for d in plan.decisions}
    if user_id in decided_users:
        raise WorkflowError(
            f"User '{user_id}' has already submitted a decision on this plan version"
        )

    record = ApprovalDecision(
        decision_id=f"dec-{uuid.uuid4().hex[:8]}",
        plan_version_id=plan.version_id,
        user_id=user_id,
        decision=decision,
        mfa_verified=mfa_verified,
        comment=comment,
    )
    plan.decisions.append(record)

    # Evaluate transition
    if decision == DecisionType.REJECT:
        # Any rejection resets to draft
        plan.status = PlanStatus.DRAFT
    else:
        # Check if we reached 2 distinct approvals with no rejections
        approvals = [d for d in plan.decisions if d.decision == DecisionType.APPROVE]
        rejections = [d for d in plan.decisions if d.decision == DecisionType.REJECT]
        distinct_approvers = {d.user_id for d in approvals}

        if len(distinct_approvers) >= 2 and len(rejections) == 0:
            plan.status = PlanStatus.APPROVED

    return plan, record


def mark_signed(plan: PlanVersion, signature_bundle: dict[str, Any]) -> PlanVersion:
    """Transition approved plan to signed upon successful signing-service response."""
    if plan.status != PlanStatus.APPROVED:
        raise WorkflowError(f"Cannot sign plan in state '{plan.status}': must be 'approved'")
    plan.signature = signature_bundle
    plan.status = PlanStatus.SIGNED
    return plan
