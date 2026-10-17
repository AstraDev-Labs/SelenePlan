# SPEC: project-service

**Port:** 8101 | **Tech:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/PostGIS, aiokafka | **Phases:** 0 (skeleton), 1-2 (CRUD), 5 (orchestrator, workflow)

## Purpose
System of record for organizations, projects, AOIs, rover profiles, scenarios, runs, plans, and approvals. Hosts the **pipeline orchestrator** and the **plan workflow** (states and approvals).

## Responsibilities
1. CRUD for projects, memberships, AOIs, rover profiles, scenarios (FR-10, FR-20).
2. Start and track **runs**: orchestrator state machine (below).
3. Plan lifecycle: versions, `submit`, `decision` (approve/reject), signing request, export (FR-30 to FR-33).
4. Outbox publisher for events.
5. Emit `audit.event` for every state change.
6. Authorization: project membership and roles via `selene-auth` and OPA policies.

## Non-goals
Running analyses, storing rasters, computing plans.

## API (see `contracts/openapi/selene-v1.yaml` and `docs/05-events-and-apis.md`)
Projects, AOIs, rover profiles, scenarios, runs (`POST` returns 202 + Location, `GET`, `GET /events` SSE), plans and versions (`submit`, `decision`, `export`). Idempotency-Key on run start and decisions.

## Orchestrator state machine
Run states: `queued → running → succeeded | failed | canceled`.
Steps: `terrain`, `hazard`, `illumination`, `comms` (parallel), then `plan`.
- On run start: validate scenario inputs exist and are registered datasets; write run and step rows; write outbox events for the four analyses.
- On each `*.completed`: mark step `succeeded`, store `product_id`. When all four are done, emit `plan.requested` with product refs.
- On `*.failed` or timeout: retry according to policy (max 3 attempts, backoff), else mark run `failed` with a reason; keep partial results visible.
- On `plan.completed`: create the plan version in `draft` and mark the run `succeeded`.
- Cancel: emit cancel events (workers must honor), mark `canceled`.
- All handlers are **idempotent** (dedupe by `event_id`) and **resumable** after restart (state lives in DB).
- Unit-test the state machine as a pure function (inputs: state plus event; outputs: new state plus commands).

## Plan workflow and policy
States: `draft → in_review → approved → signed` and `superseded`.
- `submit`: only Analyst/Admin who is a project member; computes and stores `payload_sha256`.
- `decision`: Approver role, **MFA claim present**, not the author, and not previously decided on this version. `approved` requires **two distinct approvers** with no rejection; any `reject` returns the plan to `draft` with a comment.
- When approved: call signing-service (`/internal/v1/sign`); on success set `signed` and emit `plan.signed`.
- Signed versions are immutable. Editing creates a new version; the old becomes `superseded`.
- Policy is expressed in Rego (`policies/plan_workflow.rego`) with unit tests; the service enforces via OPA or an equivalent embedded evaluation.

## Data owned
See `docs/04-data-model.md` (schema `project`). Row-level security by `org_id`/`project_id`.

## Events
Produces: `*.requested`, `plan.requested`, `plan.state.changed`, `report.requested`, `audit.event`.
Consumes: `*.completed`, `*.failed`, `plan.completed`, `plan.failed`, `plan.signed`, `report.completed`, `dataset.registered`.

## Config
`DATABASE_URL`, `KAFKA_BOOTSTRAP`, `OPA_URL` (or policy path), `KEYCLOAK_JWKS_URL`, `STEP_TIMEOUT_S`, `MAX_RETRIES`, `RUN_QUOTA_PER_USER`.

## Security
C-AUTH-2, C-AUTHZ-1, C-AUTHZ-2, C-INT-1, T2, T3, T9, T16, T21. Quotas on concurrent runs, AOI area, and period length by role.

## NFRs
Read p95 under 300 ms at 50 rps. Orchestrator survives restart mid-run without losing or duplicating steps.

## Acceptance criteria
1. User from another project cannot read or act on any resource (403/404) across all endpoints.
2. Author cannot approve own plan; same approver cannot approve twice; plan needs two distinct approvers; rejection resets to `draft`. Each case covered by tests.
3. Orchestrator: killing the service mid-run and restarting completes the run exactly once per step.
4. Duplicate events do not create duplicate steps or plans.
5. Every state change appears in the audit log.
6. Idempotency-Key replays return the original response.
7. OpenAPI matches the contract; Schemathesis passes.

## Folder layout
```
services/project-service/
  pyproject.toml  Dockerfile  alembic/
  src/project_service/{api,domain,orchestrator,workflow,events,db,policies}/
  tests/{unit,component,contract}/
  policies/plan_workflow.rego  policies/plan_workflow_test.rego
```
