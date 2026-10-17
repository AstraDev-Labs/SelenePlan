# 01. Requirements

## 1. Vision and scope
SelenePlan helps mission analysts choose **where to land** and **how to drive** near the lunar south pole, where low sun angles create long shadows, permanently shadowed regions, and Earth visibility that varies with terrain and libration.

**In scope:** data ingestion, terrain hazard analysis, ML hazard detection, illumination and shadow modeling, Earth line-of-sight windows, site ranking, traverse planning, explanation, approval workflow, signed exports, audit, reporting, and a 2D/3D web UI.

**Out of scope (v1):** real spacecraft command and control, landing guidance and navigation, high-fidelity rover dynamics, thermal modeling beyond a simple survival heuristic, other celestial bodies (design for extension, do not build).

## 2. Personas and roles
| Role | Can do |
|---|---|
| Mission Analyst | Create projects and scenarios, run analyses, create plans |
| Rover Operator | View plans, run what-if traverses, comment |
| Reviewer / Approver | Approve or reject plans (two distinct approvers required for "flight-ready") |
| Data Steward | Register datasets and models, manage provenance |
| Admin | Manage users, roles, organizations, platform settings |
| Auditor (read-only) | View audit log and signatures, verify exports |

## 3. Functional requirements
IDs are referenced by service specs and tests.

### Data and provenance
- **FR-01** Register a dataset (DEM, orthoimage, ephemeris kernel set) with source, license, CRS, resolution, and checksum.
- **FR-02** Ingest datasets from allowlisted sources or user upload. Convert rasters to Cloud-Optimized GeoTIFF with an overview pyramid and a recorded manifest.
- **FR-03** Every derived product records the exact input dataset versions, parameters, code version, and model version (full lineage).

### Analysis
- **FR-10** Define an Area of Interest (AOI) by polygon or bounding box in lunar polar coordinates.
- **FR-11** Compute slope, aspect, and roughness rasters from a DEM at a chosen resolution.
- **FR-12** Detect craters and boulders in orthoimagery with an ML model and produce a hazard layer with confidence.
- **FR-13** Combine terrain and ML hazards into a **hazard map** with configurable thresholds (per rover profile).
- **FR-14** Compute **illumination** over time: sun elevation and visibility per cell, lit fraction, and longest continuous dark period, for a user-set period (default 1 lunar day to 1 year).
- **FR-15** Compute **Earth visibility** per cell over time: Earth above the local horizon, windows, and longest blackout.
- **FR-16** Provide a time slider API that returns illumination and visibility rasters (or tiles) for a requested timestamp.

### Planning
- **FR-20** Define **rover profiles** (max slope, wheel/ground constraints, speed, battery capacity, power draw by mode, solar panel area and efficiency, minimum survival power).
- **FR-21** Rank **landing sites** within an AOI using hard constraints (hazard) and weighted soft criteria (illumination, comms, proximity to targets), with a score breakdown.
- **FR-22** Compute a **traverse plan** from a start to one or more targets, honoring slope, hazard, energy, and optional comms checkpoints, minimizing a configurable objective (time, energy, risk).
- **FR-23** Produce an **explanation** for each ranking and each rejected alternative (which constraint failed, where, and when).
- **FR-24** Support **what-if** re-planning (change start time, rover profile, or targets) and **scenario comparison**.

### Workflow and integrity
- **FR-30** Plans have versions and states: `draft` → `in_review` → `approved` (two distinct approvers) → `signed`. Edits after approval create a new version.
- **FR-31** Signing: approved plans are digitally signed. Verification of an exported plan must fail if any byte changes.
- **FR-32** Replay: any signed plan can be **recomputed from its recorded lineage** and compared to the stored result.
- **FR-33** Export plans as GeoJSON, CSV waypoints, and a PDF mission report that embeds the signature and lineage.
- **FR-34** Immutable, hash-chained **audit log** for all state changes, approvals, signing, logins, and permission changes, with an integrity verification endpoint.

### UI
- **FR-40** 3D globe/terrain view (CesiumJS, lunar ellipsoid) and a 2D polar map; layers for hazard, illumination at time T, Earth visibility at time T, candidate sites, and routes.
- **FR-41** Timeline scrubber that animates illumination and visibility.
- **FR-42** Plan viewer with energy profile, timeline of sun and comms, and the explanation panel.
- **FR-43** Role-aware UI (only show actions the user may perform).

## 4. Non-functional requirements
| ID | Requirement | Target (initial) |
|---|---|---|
| NFR-01 | API latency (read endpoints), p95 | under 300 ms at 50 rps |
| NFR-02 | Tile/time-slice request, p95 | under 500 ms (cached) |
| NFR-03 | Illumination run, 20 m/px, 100 km x 100 km AOI, 1 lunar day at 6 h steps | completes within 15 min on 8 vCPU (measure, then tune) |
| NFR-04 | Availability of API and UI (single-region) | 99.5% (demo target) |
| NFR-05 | Horizontal scalability | analysis services scale independently via consumer groups |
| NFR-06 | Reproducibility | identical inputs plus versions yield bit-identical or tolerance-bounded results (document the tolerance) |
| NFR-07 | Observability | traces, metrics, and logs for every request and job; SLO dashboards |
| NFR-08 | Data durability | daily DB backups; restore tested; object storage versioning on |
| NFR-09 | Accessibility | WCAG 2.1 AA for UI core flows |
| NFR-10 | Portability | runs fully on a single laptop (Docker Compose) and on Kubernetes |

Targets are starting points. Measure first, then adjust and record changes in the roadmap.

## 5. Security requirements (summary; details in `03-security-threat-model.md`)
- **SEC-01** OIDC authentication via Keycloak with MFA for Approver and Admin roles.
- **SEC-02** RBAC plus per-project membership on every request; deny by default.
- **SEC-03** mTLS between services in Kubernetes; default-deny NetworkPolicies.
- **SEC-04** Secrets only from Vault; no secrets in images, git, or env files in production.
- **SEC-05** Encryption in transit everywhere; at rest for DB and object storage.
- **SEC-06** Tamper-evident audit log; signed plans; signed datasets, models, and containers.
- **SEC-07** Supply chain: SBOM, vulnerability and secret scanning, signed images, protected branches.
- **SEC-08** Ingestion hardening: host allowlist, size limits, safe raster parsing, sandboxed workers.
- **SEC-09** Model integrity: signed model artifacts, version recorded in every result.
- **SEC-10** Rate limiting and request-size limits at the gateway.

## 6. Constraints and assumptions
- Public data only (NASA PDS products, ISRO releases where license permits). No export-controlled data.
- Single region, single cluster for v1. Multi-region is a non-goal.
- All thresholds are assumptions pending mission-specific input. See `08-science-notes.md`.

## 7. Acceptance of the whole system (demo scenario)
A reviewer logs in as an Analyst, creates a project over a south-polar AOI, runs the pipeline, sees hazard, illumination, and visibility layers, ranks sites, plans a traverse, submits for review. Two Approvers approve it. The plan is signed and exported. A tampered export fails verification. The audit log shows every step and passes the integrity check. Replaying the plan reproduces the result within tolerance.
