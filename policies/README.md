# OPA policies

Rego policies for authorization decisions beyond simple roles. Each policy has a `*_test.rego` file and must pass `opa test policies -v` in CI.

Planned policies:
- `plan_workflow.rego`: Approver role, MFA claim present, author is not an approver, two distinct approvers, rejection resets to draft, signed versions immutable (Phase 5).
- `project_access.rego`: project membership and role checks shared by services (Phase 0 to 1).
- `ingestion.rego`: who may register datasets and upload (Phase 1).

Phase 0 Task 0.1 provides `example.rego` plus `example_test.rego` proving policy execution and test coverage.

## Running Policy Tests

With local OPA installed:
```bash
opa test policies -v
```

Using Docker:
```bash
docker run --rm -v "${PWD}/policies:/policies" openpolicyagent/opa test /policies -v
```
