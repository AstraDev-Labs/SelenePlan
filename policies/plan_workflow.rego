package selene.plan_workflow

import rego.v1

default allow_submit := false
default allow_decision := false
default can_transition_to_approved := false
default can_transition_to_draft := false

# Submit rule
# Only Analyst/Admin who is a project member; plan must be in "draft"
allow_submit if {
	input.user.role in ["analyst", "admin"]
	input.user.id in input.project.members
	input.plan.status == "draft"
}

# Decision rule
# Approver/Admin role, MFA present, not author, not previously decided, plan in "in_review"
allow_decision if {
	input.user.role in ["approver", "admin"]
	input.user.mfa == true
	input.user.id != input.plan.author_id
	not input.user.id in input.plan.decided_user_ids
	input.plan.status == "in_review"
}

# Approval completion rule: two distinct approvers, zero rejections
can_transition_to_approved if {
	count(input.approvals) >= 2
	count(input.rejections) == 0
}

# Rejection reset rule: any rejection resets to draft
can_transition_to_draft if {
	count(input.rejections) > 0
}
