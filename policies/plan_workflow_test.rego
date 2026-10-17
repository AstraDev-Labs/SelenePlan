package selene.plan_workflow_test

import rego.v1
import data.selene.plan_workflow

test_allow_submit_valid if {
	plan_workflow.allow_submit with input as {
		"user": {"id": "user-analyst", "role": "analyst"},
		"project": {"members": ["user-analyst", "user-lead"]},
		"plan": {"status": "draft"},
	}
}

test_deny_submit_not_member if {
	not plan_workflow.allow_submit with input as {
		"user": {"id": "user-outsider", "role": "analyst"},
		"project": {"members": ["user-lead"]},
		"plan": {"status": "draft"},
	}
}

test_deny_submit_wrong_role if {
	not plan_workflow.allow_submit with input as {
		"user": {"id": "user-viewer", "role": "viewer"},
		"project": {"members": ["user-viewer"]},
		"plan": {"status": "draft"},
	}
}

test_deny_submit_not_draft if {
	not plan_workflow.allow_submit with input as {
		"user": {"id": "user-analyst", "role": "analyst"},
		"project": {"members": ["user-analyst"]},
		"plan": {"status": "in_review"},
	}
}

test_allow_decision_valid if {
	plan_workflow.allow_decision with input as {
		"user": {"id": "user-approver-1", "role": "approver", "mfa": true},
		"plan": {
			"status": "in_review",
			"author_id": "user-author",
			"decided_user_ids": [],
		},
	}
}

test_deny_decision_author_cannot_approve if {
	not plan_workflow.allow_decision with input as {
		"user": {"id": "user-author", "role": "approver", "mfa": true},
		"plan": {
			"status": "in_review",
			"author_id": "user-author",
			"decided_user_ids": [],
		},
	}
}

test_deny_decision_mfa_required if {
	not plan_workflow.allow_decision with input as {
		"user": {"id": "user-approver-1", "role": "approver", "mfa": false},
		"plan": {
			"status": "in_review",
			"author_id": "user-author",
			"decided_user_ids": [],
		},
	}
}

test_deny_decision_cannot_decide_twice if {
	not plan_workflow.allow_decision with input as {
		"user": {"id": "user-approver-1", "role": "approver", "mfa": true},
		"plan": {
			"status": "in_review",
			"author_id": "user-author",
			"decided_user_ids": ["user-approver-1"],
		},
	}
}

test_two_approvers_can_approve if {
	plan_workflow.can_transition_to_approved with input as {
		"approvals": ["user-approver-1", "user-approver-2"],
		"rejections": [],
	}
}

test_single_rejection_resets_to_draft if {
	plan_workflow.can_transition_to_draft with input as {
		"approvals": ["user-approver-1"],
		"rejections": [{"user_id": "user-approver-2", "comment": "Hazard margin insufficient"}],
	}
	not plan_workflow.can_transition_to_approved with input as {
		"approvals": ["user-approver-1"],
		"rejections": [{"user_id": "user-approver-2", "comment": "Hazard margin insufficient"}],
	}
}
