# AGENTS.md: Rules for AI agents working on SelenePlan

Read this file fully before every task. Then read the SPEC.md of the service you are touching and `docs/02-architecture.md`.

## 1. Source of truth
- `docs/` and `services/<name>/SPEC.md` define what to build. Do not invent features, endpoints, or events that are not specified.
- If a spec is ambiguous or wrong, **stop and list the question** instead of guessing. If you must proceed, record the assumption in the service's `DECISIONS.md` and flag it in your summary.
- Any change to an API, event, or schema must update `contracts/` and the relevant doc in the same change.

## 2. Repository conventions
- Monorepo. Each service lives in `services/<name>/` with its own `Dockerfile`, `pyproject.toml` (or `package.json`), `src/`, `tests/`, and `README.md`.
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 plus Alembic, `ruff` for lint and format, `mypy --strict` on new code, `pytest`. Frontend: TypeScript strict, React, Vite, Vitest.
- Service ports and names are fixed in `docs/02-architecture.md`. Do not change them.
- Conventional Commits. One logical change per commit. Never commit secrets, datasets, model weights, or build output (use `.gitignore`).

## 3. Definition of Done (every task)
1. Code, plus unit tests, plus at least one integration test where a dependency (DB, Kafka, MinIO) is involved.
2. `ruff`, `mypy`, and tests pass locally and in CI.
3. OpenAPI and event contracts updated. Health endpoints (`/healthz`, `/readyz`) and `/metrics` present.
4. Structured JSON logs with `trace_id`. No PII or secrets in logs.
5. Docs updated. `README.md` of the service explains how to run and test it.
6. A short summary: what changed, what was tested, what is left, and which assumptions were made.

## 4. Security rules (non-negotiable)
- No hard-coded secrets. Read secrets from environment variables that Vault populates. Provide only fake values in `.env.example`.
- Every endpoint requires authentication and an authorization check (role and project membership) unless the spec marks it public. Deny by default.
- Validate all input against schemas. Never build SQL by string concatenation. Parameterized queries only.
- Outbound fetches (ingestion) must use the **host allowlist** from config. Never fetch arbitrary user-supplied URLs.
- Never deserialize untrusted pickles. Do not load model files without verifying their signature or checksum via the provenance service.
- Every state-changing operation emits an `audit.event`.
- Pin dependency versions. Do not add a dependency without a one-line justification in the PR summary.

## 5. Scientific rules
- Units: SI. Metres, seconds, radians internally. Convert only at the API or UI boundary. Name units in field names (`slope_deg`, `elevation_m`).
- Time: UTC, ISO 8601, timezone-aware always. Use SPICE for ephemerides, never hand-rolled astronomy.
- The Moon is **not** an Earth ellipsoid. Use the lunar reference sphere of 1737.4 km (see `docs/08-science-notes.md`). Never reuse Earth CRS assumptions.
- Never fabricate data or "plausible" test fixtures that look real. Use clearly synthetic fixtures (analytic cones, planes, a single crater) and label them.
- Every analytic algorithm needs a **golden test** with a known-answer case (see `docs/06-testing-strategy.md`). If you cannot validate an output, say so explicitly.
- Thresholds are config, never constants buried in code.

## 6. Working style
- Plan first: write a short plan (files to create or change, tests to add), then implement.
- Work on one service or one phase task at a time. Do not refactor unrelated services.
- Prefer small, reviewable diffs. If a task would exceed about 600 changed lines, split it and say so.
- Run the tests you wrote. Report real results, never claim a test passed that you did not run.
- When something fails and you cannot fix it in a few attempts, stop and report the error, what you tried, and your hypothesis.
