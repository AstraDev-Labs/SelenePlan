# project-service

**Port:** 8101 | **Tech:** FastAPI, SQLAlchemy 2, Pydantic v2 | **Phase:** 5

## Purpose
System of record for organizations, projects, AOIs, rover profiles, scenarios, runs, plans, and approvals. Hosts the pipeline orchestrator state machine and four-eyes plan workflow (FR-10, FR-20, FR-30 to FR-33).

## Implemented Features
1. **Pipeline Orchestrator State Machine:** Pure-function run state machine handling parallel steps (`terrain`, `hazard`, `illumination`, `comms`), join barrier, then `plan` step, retry logic (up to 3 attempts), timeouts, cancel handling, and restart idempotency.
2. **Plan Approval Lifecycle:** Versioned plan state transitions (`draft → in_review → approved → signed`).
3. **Four-Eyes Policy:** Enforces approver role, required MFA claims, author self-approval denial, two distinct approvers required for `approved`, and rejection reset to `draft`.
4. **Idempotency & Isolation:** Idempotency-Key header support on run start and approval decisions, cross-project access isolation (403 Forbidden).

## Local Development & Testing
```bash
pytest services/project-service/tests/ -v
```
