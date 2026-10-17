package example

import rego.v1

default allow := false

# Allow access if the user has the "analyst" or "admin" role
allow if {
	input.user.role in ["analyst", "admin"]
}

# Allow access if the user is a project member with appropriate permission
allow if {
	input.user.id in input.project.members
	input.action in ["read", "whatif"]
}
