# Phase 5 Demo Runbook: Planning, Orchestration, Approvals, Signing, Replay, and Reports

This runbook demonstrates the complete end-to-end mission workflow per `docs/01-requirements.md` section 7 and Phase 5 specifications:
- Pure-function orchestrator state machine with parallel analysis steps and join barrier.
- Deterministic candidate landing site ranking with soft scores and rejection reasons.
- Time-expanded A* traverse search with physical energy transitions and comms checkpoints.
- Structured what-if explanations identifying dominant constraint violations.
- Two-person approval workflow with MFA enforcement (four-eyes principle).
- RFC 8785 canonical JSON digest and Ed25519 signing via Vault Transit with key rotation support.
- Mission reporting with DRAFT watermark for unsigned plans, GeoJSON, and CSV exports.
- Offline verification (`tools/verify_bundle.py`) and lineage replay (`tools/replay.py`).

---

## 1. Services & Architecture Overview

| Service | Port | Responsibilities |
|---|---|---|
| `project-service` | 8101 | System of record, pipeline orchestrator state machine, four-eyes plan workflow |
| `planner-service` | 8107 | Candidate site ranking, time-expanded A* traverse search, what-if comparison |
| `signing-service` | 8110 | RFC 8785 JSON canonicalization, Vault Transit Ed25519 signing & verification |
| `report-service` | 8108 | HTML/PDF mission report with DRAFT watermark, GeoJSON & CSV waypoint exports |
| `provenance-service` | 8111 | Artifact SHA-256 registry, lineage DAGs, replay recipes |
| `web` | 5173 | Mission Control UI with planner panel, what-if form, approvals queue, bundle verifier |

---

## 2. Automated Test Verification

Run all test suites across the monorepo:
```bash
# Run backend service and library tests (319 tests)
pytest libs/ services/ -v

# Run web frontend tests (11 Vitest & axe-core accessibility tests)
cd services/web && npm test
```

**Expected Results:**
- `services/planner-service`: 15 passed (golden wall with gap, wait-for-light case, comms-constraint checkpoint, property search invariance over random seeds, energy conservation).
- `services/project-service`: 16 passed (orchestrator join barrier, retry on step failure, restart idempotency, author self-approval denial, MFA enforcement, two distinct approvers).
- `services/signing-service`: 7 passed (RFC 8785 canonicalization, permuted-key equality, single-byte tamper detection, approval evidence verification, historical key verification after rotation).
- `services/report-service`: 6 passed (signed report metadata, unsigned plan DRAFT watermark, HTML/template injection autoescaping, non-redistributable dataset safeguarding).
- `services/provenance-service`: replay test passed (exact waypoint match within tolerance, loud failure on altered input hash).
- `services/web`: 11 Vitest & accessibility tests passed with zero axe-core violations.

---

## 3. Step-by-Step Mission Workflow Walkthrough

### Step 1: Run Orchestrator State Machine
Start a mission run for the Shackleton South Pole AOI:
```bash
curl -X POST http://localhost:8101/v1/projects/proj-shackleton/runs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: idemp-run-001" \
  -d '{"scenario_id": "scen-south-pole", "aoi_id": "aoi-shackleton"}'
```
- Orchestrator kicks off 4 parallel analysis steps: `terrain`, `hazard`, `illumination`, `comms`.
- As completed events arrive, intermediate product references are recorded.
- When all 4 analysis steps complete, the join barrier is satisfied and `plan.requested` is automatically emitted with all 4 product IDs.

### Step 2: Site Ranking & Traverse Planning
Generate optimal landing site rankings and compute the baseline traverse path:
```bash
curl -X POST http://localhost:8107/v1/planner/routes \
  -H "Content-Type: application/json" \
  -d '{
    "start_point": [8, 2],
    "goal_point": [8, 18],
    "max_slope_deg": 15.0,
    "battery_capacity_wh": 500.0,
    "require_comms_checkpoints": true
  }'
```
- Planner executes time-expanded A* search across the 20 m grid.
- Evaluates slope hazards, illumination timestack, solar energy generation, battery charge, and Earth LOS visibility.
- Emits waypoints with coordinates, timestamp, battery state, sun elevation, and Earth visibility.

### Step 3: What-If Comparison & Constraint Violation Explanations
Evaluate an alternative constraint scenario:
```bash
curl -X POST http://localhost:8107/v1/planner/whatif \
  -H "Content-Type: application/json" \
  -d '{
    "base_route_id": "route-123",
    "max_slope_deg": 8.0,
    "battery_capacity_wh": 300.0
  }'
```
- When an alternative is infeasible, the planner produces a structured explanation naming the first and dominant violated constraint with location and timestamp:
  ```json
  {
    "dominant_violation": "MAX_SLOPE_EXCEEDED",
    "location": [8, 10],
    "slope_deg": 14.8,
    "reason": "Slope 14.8° exceeds maximum traversable limit 8.0°"
  }
  ```

### Step 4: Two-Person Approval Workflow
1. Analyst submits the draft plan for review:
   ```bash
   curl -X POST http://localhost:8101/v1/plans/plan-001/versions/pv-001/submit \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user-analyst", "user_role": "analyst"}'
   ```
2. Author attempts to self-approve: **Rejected (400 Bad Request)** with `"Author cannot approve or reject their own plan (four-eyes principle)"`.
3. First independent Approver (with MFA claim) approves: Plan status moves to `in_review`.
4. Second independent Approver approves: Plan status moves to `approved`.

### Step 5: Cryptographic Signing via Vault Transit
Signing service verifies the two approvals and canonicalizes the plan:
```bash
curl -X POST http://localhost:8110/internal/v1/sign \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "plan-001",
    "plan_version_id": "pv-001",
    "payload": { ... },
    "submitted_hash": "...",
    "approval_evidence": { ... }
  }'
```
- Produces Ed25519 signature record: `vault:v1:<base64-signature>`.
- Re-signing the same version returns the original signature (idempotent).
- Key rotation retains past keys in retired status so historical signatures remain verifiable.

### Step 6: Mission PDF/HTML Report & Data Exports
1. Download full mission report:
   ```bash
   curl http://localhost:8108/v1/reports/rep-001/download > mission_report.html
   ```
   - Signed plans feature the cryptographic signature block and verification instructions.
   - Unsigned plans prominently display the `DRAFT / NOT SIGNED` watermark.
2. Download GeoJSON and CSV exports:
   ```bash
   curl http://localhost:8108/v1/reports/rep-001/export/geojson > route.geojson
   curl http://localhost:8108/v1/reports/rep-001/export/csv > waypoints.csv
   ```

### Step 7: Offline Verification & Lineage Replay
Verify the signed bundle completely offline without network access:
```bash
python tools/verify_bundle.py path/to/signed_bundle.json
```
- Output: `SUCCESS: Valid Ed25519 signature! Payload hash: <sha256>`.
- If a single character or number is altered in the payload: `FAILURE: Cryptographic signature verification FAILED`.

Recompute and replay the plan from recorded lineage:
```bash
python tools/replay.py path/to/replay-spec.json
```
- Verifies input hashes against recorded provenance before search.
- If an input raster was tampered with: exits with `InputHashMismatchError`.
- Re-executes search and validates that all waypoints match within 0.01 m and 0.001 h tolerance.

---

## 4. UI Demonstration: Mission Control Web Interface

1. Launch `http://localhost:5173`.
2. In the **Map View**, interact with the new **Mission Traverse Planner** card:
   - Adjust **Max Traversable Slope** and **Battery Capacity**.
   - Click **Plan Traverse**: baseline time-expanded A* route is generated.
   - Click **What-If**: view delta distance and detour explanations.
   - Click **Submit Plan for Review**: advances plan to approval queue.
3. Switch persona to **Approver**:
   - Navigate to the **Approvals** tab: notice the author cannot approve their own plan.
   - Enter justification comments and record two distinct approvals.
4. Navigate to the **Cryptographic Verification** tab:
   - Paste a signed mission bundle and click **Verify Bundle Cryptography**.
   - Observe real-time validation of SHA-256 digests and Ed25519 signature authenticity.
