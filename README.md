# SelenePlan: Lunar South Pole Mission Planner

SelenePlan is an enterprise-grade, microservice-based platform that selects landing sites and plans rover traverses near the lunar south pole. It treats **terrain hazard, time-varying sunlight, and Earth communication visibility together**, and it explains every decision it makes. Every approved plan is signed and fully reproducible.

> Working name. Rename freely, but keep the `selene-` prefix consistent in topics, images, and namespaces or do a global rename early.

## What is novel (the claim to defend)
A **time-aware joint optimizer** over sunlight, terrain hazard, energy, and Earth visibility, with an **explainability layer** ("route rejected: shadow from 14:00 to 19:00 plus no Earth visibility"), wrapped in **mission-integrity controls** (two-person approval, signed plans, hash-chained audit, signed datasets and models). Confirm novelty with a prior-art search before publishing. See `docs/07-roadmap.md`, task P-0.

## Repository map
```
selene-plan/
  README.md                  you are here
  AGENTS.md                  rules every AI agent (Antigravity) must follow
  docs/
    01-requirements.md       functional, non-functional, and security requirements
    02-architecture.md       system architecture, diagrams, service catalog
    03-security-threat-model.md   threat model (STRIDE), controls, pen-test plan
    04-data-model.md         database schema, object storage layout, CRS
    05-events-and-apis.md    event envelope, topics, API conventions
    06-testing-strategy.md   test pyramid, golden datasets, performance targets
    07-roadmap.md            phases, exit criteria, risks
    08-science-notes.md      data sources, algorithms, validation, assumptions
    adr/                     architecture decision records
  contracts/
    openapi/selene-v1.yaml   API contract skeleton
    events/envelope.schema.json
  services/<name>/SPEC.md    one implementation spec per service (14)
  infra/                     docker-compose, Prometheus, Kong config, env template
  .github/workflows/ci.yml   CI skeleton with security scans
  prompts/                   Antigravity prompt pack (master context + phases 0 to 7)
```

## How to start (in Antigravity)
1. Open this folder as the workspace.
2. Read `AGENTS.md` and make sure Antigravity uses it as project rules (paste it into the project rules or instructions if your version does not pick it up automatically).
3. Paste `prompts/00-master-context.md` as the first message of the first agent session.
4. Run phases in order with `prompts/phase-0-foundation.md`, then `phase-1-terrain.md`, and so on. **Do one phase at a time and review the result before moving on.**
5. Keep `docs/` and `services/*/SPEC.md` as the source of truth. When the design changes, update the doc in the same commit and add an ADR for significant decisions.

## Services & Platform Status

| Service / Library | Directory | Port / Type | Status | Phase |
| :--- | :--- | :--- | :--- | :--- |
| **selene-auth** | `libs/selene-auth` | Py Library | ✅ Verified & Tested | Phase 0 |
| **selene-events** | `libs/selene-events` | Py Library | ✅ Verified & Tested | Phase 0 |
| **selene-observability** | `libs/selene-observability` | Py Library | ✅ Verified & Tested | Phase 0 |
| **selene-geo** | `libs/selene-geo` | Py Library | ✅ Verified & Tested | Phase 1 |
| **selene-horizon** | `libs/selene-horizon` | Py Library | ✅ Verified & Tested | Phase 2 |
| **selene-testing** | `libs/selene-testing` | Py Library | ✅ Verified & Tested | Phase 1 |
| **audit-service** | `services/audit-service` | Port 8101 | ✅ Verified & Tested | Phase 0 |
| **hazard-ml-service** | `services/hazard-ml-service` | Port 8104 | ✅ Verified & Tested | Phase 4 |
| **hello-service** | `services/hello-service` | Port 8100 | ✅ Verified & Tested | Phase 0 |
| **comms-service** | `services/comms-service` | Port 8106 | ✅ Verified & Tested | Phase 3 |
| **gateway** | `services/gateway` | Port 8000 | ✅ Verified & Tested | Phase 0 |
| **identity** | `services/identity` | Port 8080 | ✅ Verified & Tested | Phase 0 |
| **illumination-service** | `services/illumination-service` | Port 8105 | ✅ Verified & Tested | Phase 2 |
| **ingestion-service** | `services/ingestion-service` | Port 8102 | ✅ Verified & Tested | Phase 1 |
| **planner-service** | `services/planner-service` | Port 8107 | ✅ Verified & Tested | Phase 5 |
| **project-service** | `services/project-service` | Port 8101 | ✅ Verified & Tested | Phase 5 |
| **provenance-service** | `services/provenance-service` | Port 8111 | ✅ Verified & Tested | Phase 1/5 |
| **report-service** | `services/report-service` | Port 8108 | ✅ Verified & Tested | Phase 5 |
| **signing-service** | `services/signing-service` | Port 8110 | ✅ Verified & Tested | Phase 5 |
| **terrain-service** | `services/terrain-service` | Port 8103 | ✅ Verified & Tested | Phase 1 |
| **web** | `services/web` | Port 5173 / 3000 | ✅ Verified & Tested | Phase 1-5 |

## Local quick start
```bash
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d
python -m pytest libs services
```

## Important caveats
- Scientific outputs (illumination, visibility, slope) must be **validated against published reference data** before being trusted. See `docs/08-science-notes.md`.
- Dataset terms of use (including ISRO PRADAN) must be checked before ingestion or redistribution.
- All thresholds (maximum slope, battery model, sun panel model) are **configurable assumptions**, not mission-certified values.
