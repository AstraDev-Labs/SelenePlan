"""Unit tests for the plan approval workflow and four-eyes policy.

Per services/project-service/SPEC.md:
- Acceptance Criterion 2: Author cannot approve own plan; same approver cannot approve twice;
  plan needs two distinct approvers; rejection resets to draft. Each case covered by tests.
"""

import pytest
from project_service.domain.models import DecisionType, PlanStatus, PlanVersion
from project_service.workflow.engine import (
    WorkflowError,
    mark_signed,
    record_decision,
    submit_for_review,
)


def create_draft_plan() -> PlanVersion:
    return PlanVersion(
        version_id="pv-001",
        plan_id="plan-shackleton-alpha",
        version_number=1,
        author_id="user-author",
        status=PlanStatus.DRAFT,
        payload={"waypoints": [[8, 2], [8, 10], [8, 18]], "total_dist_m": 320.0},
    )


def test_submit_lifecycle_and_hash_computation() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-analyst", "user-approver-1", "user-approver-2"]

    # Non-member cannot submit
    with pytest.raises(WorkflowError, match="must be a member"):
        submit_for_review(
            plan, user_id="user-stranger", user_role="analyst", project_members=members
        )

    # Viewer role cannot submit
    with pytest.raises(WorkflowError, match="cannot submit"):
        submit_for_review(plan, user_id="user-author", user_role="viewer", project_members=members)

    # Valid submission
    submitted = submit_for_review(
        plan, user_id="user-author", user_role="analyst", project_members=members
    )
    assert submitted.status == PlanStatus.IN_REVIEW
    assert submitted.payload_sha256 is not None
    assert len(submitted.payload_sha256) == 64


def test_author_cannot_approve_own_plan() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-approver-1"]
    submit_for_review(plan, "user-author", "analyst", members)

    with pytest.raises(WorkflowError, match="Author cannot approve"):
        record_decision(
            plan=plan,
            user_id="user-author",
            user_role="approver",
            decision=DecisionType.APPROVE,
            mfa_verified=True,
        )


def test_mfa_claim_strictly_required() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-approver-1"]
    submit_for_review(plan, "user-author", "analyst", members)

    with pytest.raises(WorkflowError, match="MFA verification is required"):
        record_decision(
            plan=plan,
            user_id="user-approver-1",
            user_role="approver",
            decision=DecisionType.APPROVE,
            mfa_verified=False,
        )


def test_same_approver_cannot_decide_twice() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-approver-1"]
    submit_for_review(plan, "user-author", "analyst", members)

    # First vote
    record_decision(
        plan=plan,
        user_id="user-approver-1",
        user_role="approver",
        decision=DecisionType.APPROVE,
        mfa_verified=True,
    )
    assert plan.status == PlanStatus.IN_REVIEW  # needs 2 approvals

    # Duplicate vote by same approver
    with pytest.raises(WorkflowError, match="already submitted a decision"):
        record_decision(
            plan=plan,
            user_id="user-approver-1",
            user_role="approver",
            decision=DecisionType.APPROVE,
            mfa_verified=True,
        )


def test_two_distinct_approvals_transition_to_approved_then_sign() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-approver-1", "user-approver-2"]
    submit_for_review(plan, "user-author", "analyst", members)

    # Approver 1
    record_decision(
        plan=plan,
        user_id="user-approver-1",
        user_role="approver",
        decision=DecisionType.APPROVE,
        mfa_verified=True,
    )
    assert plan.status == PlanStatus.IN_REVIEW

    # Approver 2
    record_decision(
        plan=plan,
        user_id="user-approver-2",
        user_role="approver",
        decision=DecisionType.APPROVE,
        mfa_verified=True,
    )
    assert plan.status == PlanStatus.APPROVED

    # Sign plan
    signature_bundle = {
        "key_id": "selene-plan-signing",
        "algorithm": "Ed25519",
        "signature_b64": "dummy-sig",
    }
    signed_plan = mark_signed(plan, signature_bundle)
    assert signed_plan.status == PlanStatus.SIGNED
    assert signed_plan.signature == signature_bundle


def test_rejection_resets_to_draft_with_comment() -> None:
    plan = create_draft_plan()
    members = ["user-author", "user-approver-1"]
    submit_for_review(plan, "user-author", "analyst", members)

    # Approver rejects
    plan, dec = record_decision(
        plan=plan,
        user_id="user-approver-1",
        user_role="approver",
        decision=DecisionType.REJECT,
        mfa_verified=True,
        comment="Battery margin under 15% is unacceptable for polar terrain",
    )
    assert plan.status == PlanStatus.DRAFT
    assert dec.comment == "Battery margin under 15% is unacceptable for polar terrain"
