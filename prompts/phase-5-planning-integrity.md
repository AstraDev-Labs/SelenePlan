# Phase 5: Planning, orchestration, approvals, signing, replay, reports

**Goal:** the complete mission workflow: run the pipeline, rank sites, plan traverses with explanations, approve with two people, sign, export, verify, and replay.

**Read first:** `services/planner-service/SPEC.md`, `services/project-service/SPEC.md`, `services/signing-service/SPEC.md`, `services/report-service/SPEC.md`, `services/provenance-service/SPEC.md`, `docs/08-science-notes.md` (section 7), `docs/04-data-model.md` (section 5), `docs/adr/0002`, `0005`, `0006`, `docs/03-security-threat-model.md` (T3, T9, T10, T21).

## Tasks

### Task 5.1: Rover profiles and energy model
In project-service: rover profile CRUD with validation and versioning. In planner-service: pure-function energy model (solar input, consumption by mode, battery limits, survival minimum). Document assumptions in `services/planner-service/DECISIONS.md`.
**Done when:** energy golden tests pass (constant lit and drive power equals power times time; long dark segment violates the minimum).

### Task 5.2: Site ranking
Implement candidate generation, hard constraints, soft scoring with breakdown, rejection reasons.
**Done when:** SPEC criterion 6 passes; rankings are deterministic.

### Task 5.3: Traverse search
Implement time-expanded search (cell, time bucket, battery bucket) with admissible heuristic, constraints for hazard, slope, energy, comms checkpoints, and max blackout. Fixed tie-breaking.
**Done when:** golden tests (wall with a gap, wait-for-light case, comms-constraint case) and the property test (never enters hazard cells or exceeds max slope) pass; a performance baseline is recorded and a bounded-search fallback is documented.

### Task 5.4: Explanations and what-if
Implement structured explanations plus readable text, and the what-if and compare endpoints.
**Done when:** infeasible alternatives produce explanations naming the dominant violated constraint with location and time; tests assert the content.

### Task 5.5: Orchestrator
Implement the run state machine in project-service per SPEC: parallel analysis steps, join, plan step, retries, timeouts, DLQ handling, cancel, outbox, SSE progress. State machine as a pure function with exhaustive unit tests.
**Done when:** killing the service mid-run and restarting completes the run exactly once per step; duplicate events do not create duplicate steps.

### Task 5.6: Approval workflow and OPA policy
Implement plan versions, `submit`, `decision`, and the Rego policy: Approver role, MFA claim, author not approver, two distinct approvers, rejection resets to draft, signed immutable. OPA unit tests for every rule.
**Done when:** SPEC acceptance criteria 1 and 2 for project-service pass.

### Task 5.7: Signing service
Implement canonicalization (RFC 8785), Vault Transit signing, signature records, verify endpoint, public key endpoint, internal sign endpoint with approval-evidence re-verification, and the offline `tools/verify_bundle.py`.
**Done when:** all signing acceptance criteria pass, including permuted-key equality, single-byte tamper detection, signing refused without evidence, and old-key verification after rotation.

### Task 5.8: Replay
Implement `GET /v1/lineage/{id}/replay-spec` and a `tools/replay` CLI that recomputes a plan from its recorded lineage and compares waypoints and metrics against the stored plan within documented tolerance.
**Done when:** replay of a small signed plan matches; a deliberately altered input hash causes replay to fail loudly.

### Task 5.9: Reports and exports
Implement report-service per SPEC: PDF with signature and lineage, GeoJSON and CSV exports, DRAFT watermark for unsigned plans, template injection safety.
**Done when:** the PDF-text-versus-DB test passes; injection tests pass.

### Task 5.10: UI for planning and approvals
Planner panel, explanation panel, what-if form, compare view, approvals queue (author's approve button disabled; server also enforces), signature badge, verify-bundle upload, lineage viewer, audit viewer with chain status.
**Done when:** Playwright end-to-end (with real backend in Compose) covers: run pipeline, rank, plan, submit, two approvals by two users, signed, export, verify valid, tamper then verify invalid, audit chain OK.

## Phase 5 exit criteria
The full demo scenario in `docs/01-requirements.md` section 7 works end to end. All acceptance criteria for planner, project, signing, report, audit, provenance are demonstrated. `docs/demos/phase-5.md` written.
