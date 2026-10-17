# Phase 0: Foundation and security base

**Goal:** a running local platform skeleton with authentication, an audit trail, shared libraries, and CI with security scans. No domain logic yet.

**Read first:** `docs/02-architecture.md` (sections 1 to 8), `docs/03-security-threat-model.md`, `docs/05-events-and-apis.md`, `services/gateway/SPEC.md`, `services/identity/SPEC.md`, `services/audit-service/SPEC.md`, `libs/README.md`, `docs/adr/`.

**Rule:** do the tasks in order, one at a time. After each task, wait for my review. Start each by writing a short plan.

## Tasks

### Task 0.1: Repository base
- Verify the folder structure matches the README. Add per-service `README.md` stubs where missing.
- Add pre-commit config: ruff, gitleaks, end-of-file fixer, check-yaml.
- Add `policies/` (OPA) with a README and an `example.rego` plus test that proves `opa test` runs.
- Create `services/identity/realm/` placeholder so Compose starts.
**Done when:** `make lint` runs (even if there is little code), pre-commit works, `docker compose config` validates.

### Task 0.2: Shared libraries
Create `libs/selene-events`, `libs/selene-observability`, `libs/selene-auth` as installable Python packages (each with `pyproject.toml`, tests, README).
- `selene-events`: Pydantic models for the envelope (matching `contracts/events/envelope.schema.json`), JSON Schema validation, Kafka producer (aiokafka) with outbox helper interface, idempotent consumer base class (dedupe by `event_id` using a pluggable store), DLQ publishing.
- `selene-observability`: OpenTelemetry setup, JSON logging with `trace_id`, Prometheus metrics middleware, `/healthz` `/readyz` `/metrics` router factory, log scrubbing helper.
- `selene-auth`: JWT verification with JWKS cache, **pinned algorithms (RS256/ES256 only)**, issuer/audience/expiry checks, role extraction, FastAPI dependencies (`require_roles(...)`), project-membership helper interface, OPA client wrapper.
**Done when:** unit tests cover: tampered JWT, `alg=none`, wrong audience, expired token, missing role, envelope validation failures, duplicate event handling. Coverage on these libs at least 85%.

### Task 0.3: Compose stack and realm
- Bring up the stack from `infra/docker-compose.yml`. Fix any issue you find (image tags, healthchecks, networking). Document changes.
- Write `services/identity/realm/selene-realm.json` per `services/identity/SPEC.md` (roles, clients, mappers, MFA requirement for approver and admin, token lifetimes). Add seed users with fake dev passwords documented in the identity README.
- Add `scripts/get_token.py` (dev only) to fetch tokens for seed users.
**Done when:** `make up` works from a clean clone; tokens for each seed user contain correct `roles`, `org_id`, `aud`.

### Task 0.4: Gateway
- Decide the gateway option (Kong with JWT plugin vs Envoy `jwt_authn` with JWKS). Write the decision in `services/gateway/DECISIONS.md` with reasons. Implement it.
- Create a tiny `hello-service` (FastAPI) that uses `selene-auth` and `selene-observability` and is routed through the gateway at `/v1/hello`.
**Done when:** the gateway acceptance criteria 1 to 5 in `services/gateway/SPEC.md` are demonstrated by automated tests (missing, expired, wrong-audience, `alg=none`, tampered token; rate limit; size limit).

### Task 0.5: Audit service MVP
Implement `services/audit-service` per its SPEC: schema and migrations, hash chain, consumer, internal endpoint, integrity verification, query API with role-aware access. Wire Keycloak events (or a forwarder) into audit.
**Done when:** acceptance criteria 1 to 7 pass, including gap/fork-free chain under concurrency, tamper detection, and DB grants preventing UPDATE/DELETE (tests execute them).

### Task 0.6: CI and security baseline
- Make `.github/workflows/ci.yml` work for what exists. Add the lint, type, test, gitleaks, Semgrep, Trivy, SBOM jobs.
- Add a threat-model review checklist to `docs/security/phase-0-review.md` and fill in what is implemented vs pending per STRIDE row.
**Done when:** CI is green on a PR; a deliberately committed fake secret is caught by gitleaks in a test branch.

## Phase 0 exit criteria
- Clean clone, `make up`, all infra healthy; token flow works; gateway enforces auth; audit chain verifies; CI green with scans; threat model reviewed; ADRs updated.
- Provide `docs/demos/phase-0.md` with the exact commands to demonstrate the above.

## Report format
For each task: files changed, tests and real results, assumptions, spec deviations, remaining work.
