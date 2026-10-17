package example_test

import rego.v1

import data.example

test_allow_for_analyst if {
	example.allow with input as {
		"user": {"id": "user-1", "role": "analyst"},
		"project": {"members": []},
		"action": "create",
	}
}

test_allow_for_admin if {
	example.allow with input as {
		"user": {"id": "user-2", "role": "admin"},
		"project": {"members": []},
		"action": "delete",
	}
}

test_allow_for_member_read if {
	example.allow with input as {
		"user": {"id": "user-3", "role": "operator"},
		"project": {"members": ["user-3"]},
		"action": "read",
	}
}

test_deny_for_anonymous_or_unauthorized if {
	not example.allow with input as {
		"user": {"id": "user-4", "role": "unauthorized"},
		"project": {"members": ["user-1"]},
		"action": "delete",
	}
}
