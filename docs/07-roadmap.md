# 07. Roadmap

Timeline assumes one developer working with Antigravity agents, roughly 15 to 20 focused hours per week. Adjust dates, but **keep the order** and the exit criteria. Always complete a thin vertical slice (one small AOI, end to end) before widening.

## Phase overview
| Phase | Weeks | Theme | Exit criteria (all must be true) |
|---|---|---|---|
| P-0 | 0 (before coding) | Prior art and scope | Prior-art search done; one-line novelty claim written; datasets and licenses listed; AOI chosen (small, about 10 to 20 km) |
| 0 | 1-2 | Foundation and security base | Monorepo, CI with scans, Compose stack up, Keycloak realm, Vault dev, `selene-auth` lib, gateway routes a hello service with JWT, audit service skeleton receives events, threat model reviewed |
| 1 | 3-4 | Data and terrain | Dataset ingestion with SSRF protections; DEM to COG with manifest; terrain service outputs slope, aspect, roughness; map shows slope layer; golden tests pass |
| 2 | 5-7 | Illumination | Time-stacked illumination for the small AOI; timeline slider in UI; known-answer tests pass; comparison with published data documented; performance baseline recorded |
| 3 | 8-9 | Earth visibility | Comms service with SPICE; visibility windows and blackout stats; tests pass; UI layer and timeline |
| 4 | 10-12 | ML hazards | Model registry with signing; training and evaluation pipeline; hazard-ml service serving ONNX; hazard map merged with terrain; evaluation report published |
| 5 | 13-16 | Planning, workflow, integrity | Site ranking and traverse planner with explanations; project-service orchestrator runs full pipeline; plan versions and two-person approval; signing and verification; audit chain verified; replay works; report PDF |
| 6 | 17-20 | Enterprise hardening | Kubernetes deploy with Helm; mTLS and NetworkPolicies; OTel, Prometheus, Grafana, Loki dashboards; KEDA autoscaling; load and soak tests meet NFRs or documented gaps; pen test and fixes; backup and restore tested |
| 7 | 21-22 | Release and publication | Docs complete; demo video; paper or patent disclosure draft; v1.0 tag; SBOM and signed images published |

## Task breakdown (selected; expand into issues)

### P-0 Prior art and scope
- P-0.1 Search Google Scholar, arXiv, Google Patents, GitHub for: lunar south pole traverse planning, illumination and Earth visibility mapping, explainable site selection, time-dependent rover path planning.
- P-0.2 Write `docs/novelty.md` with a table: existing tools, what they cover, and the gap this project fills.
- P-0.3 Decide the AOI and period. Record in `docs/validation/aoi.md`.
- P-0.4 List datasets, their licenses, and access method.

### Phase 0
- Initialize repo, branch protection, CODEOWNERS for `docs/03-*`, `services/signing-service`, `services/audit-service`, `infra/`.
- `selene-common` libraries: `selene-auth` (JWT validation, RBAC decorators), `selene-events` (envelope, producer, idempotent consumer), `selene-observability` (OTel setup, JSON logging).
- Compose stack and Makefile targets (`make up`, `make test`, `make lint`).
- Keycloak realm export with roles and a test user per role.
- Gateway: JWT validation plugin or OIDC, rate limit, request size limit, routes.
- Audit-service MVP: consume `audit.event`, hash chain, verify endpoint.
- CI: lint, tests, Semgrep, gitleaks, Trivy, SBOM.

### Phase 1
- Ingestion API and worker, allowlist, size limits, COG conversion (GDAL), checksum, registration, events.
- Terrain service algorithms (Horn or Zevenbergen-Thorne slope; document choice), roughness measure, tests.
- Web app shell: login, project list, map with COG layer from TiTiler.
- Provenance service MVP: record artifacts and lineage edges.

### Phase 2
- Illumination algorithm design ADR (horizon-profile vs ray marching, resolution strategy, storage format).
- Sun position via SPICE; moon-fixed frame handling; time axis.
- Optimized kernel (Numba), tiling, parallel workers.
- Storage format ADR (banded COG vs Zarr).
- API for slices and stats; UI timeline.
- Validation notes and performance baseline.

### Phase 3
- Earth direction in the local topocentric frame; horizon test against terrain.
- Window extraction and blackout statistics; API and UI.
- Cross-check against illumination results for sanity (same horizon routines where valid).

### Phase 4
- Training data assembly with licenses, tiling, labels from a published crater catalog, boulder labeling strategy.
- Training and evaluation scripts (reproducible, seeded), ONNX export, model card.
- Model registry with signature verification; inference worker with batching and tiling; confidence rasters.
- Hazard fusion: terrain hazard, ML hazard, configurable thresholds; unit tests.

### Phase 5
- Rover profile model (power, speed, slope limits).
- Site ranking: hard constraints, weighted soft criteria, score breakdown, rejection reasons.
- Traverse planner: time-expanded graph search with energy model; explanation generator; what-if API.
- Project-service orchestrator saga with retries, timeouts, DLQ handling.
- Approval workflow with OPA policies; signing service; verification endpoint; canonical JSON.
- Replay tool (CLI and API) that recomputes from lineage and compares.
- Report service (PDF with plan, maps, lineage, signature).

### Phase 6
- Helm charts and Kubernetes manifests; NetworkPolicies; mesh mTLS; Pod security standards.
- KEDA scaling on Kafka lag; resource requests and limits from measured profiles.
- Dashboards and alerts; SLO definitions; runbooks in `docs/runbooks/`.
- k6 load tests; soak; chaos experiments (kill workers mid-run).
- Pen-test per plan; fix findings; write report.
- Backup and restore drill.

### Phase 7
- Finish docs and diagrams (C4), onboarding guide, API docs site.
- Demo script and video; paper or patent disclosure outline; release notes.

## Definition of Done per phase
1. Exit criteria met and demonstrated (demo script in `docs/demos/phase-N.md`).
2. CI green on main; no open critical or high findings.
3. Docs and ADRs updated; contracts match code.
4. Retrospective note: what slipped, what was learned, risks changed.

## Risk burn-down (check at each phase end)
| Risk | Check |
|---|---|
| Compute too slow | Compare measured NFR-03 against target; decide on algorithm, tiling, or resolution changes |
| Scientific error | Review validation notes and known-answer tests with an advisor if possible |
| Scope creep | Anything not in the exit criteria goes to `docs/backlog.md` |
| Dataset license | Re-check any new dataset before ingestion |

## Backlog (post v1 ideas)
Multi-rover fleet planning, dynamic re-planning from telemetry, thermal modeling, higher-fidelity soil mechanics, collaborative editing, other bodies (Mars), public read-only dashboard.
