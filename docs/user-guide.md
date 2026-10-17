# SelenePlan User Guide: Analyst, Approver, and Auditor Workflows

## 1. Overview
SelenePlan is a lunar south pole mission planning platform designed for mission safety, mathematical rigor, and forensic auditability. This guide describes the end-to-end workflows for the three primary operator roles:
- **Analyst:** Explores the lunar terrain, triggers parallel analysis pipelines, ranks candidate sites, solves time-expanded rover traverses, runs what-if analyses, and submits plans.
- **Approver:** Evaluates submitted plans, checks safety thresholds, verifies contrastive rejection reasons, and signs off using multi-factor authentication (MFA).
- **Auditor:** Verifies cryptographic bundle integrity offline, audits the continuous hash-chained event log, and reproduces traverses deterministically.

---

## 2. Analyst Workflow: Exploration, Site Ranking & Traverse Planning

### Step 2.1: Authentication & Project Creation
1. Navigate to the web application at `http://localhost:5173`.
2. Log in using your assigned credentials (e.g. `analyst1@mission.org`).
3. Click **"New Project"**, specify a project identifier (e.g. `artemis-shackleton-alpha`), and define the Area of Interest (AOI):
   - **Center Coordinate:** $89.9^\circ\text{ S}, 0.0^\circ\text{ E}$ (Shackleton Crater rim).
   - **Bounding Box:** $20\text{ km} \times 20\text{ km}$ Lunar Polar Stereographic extent.
   - **Mission Window:** 2026-10-18T00:00:00Z to 2026-11-18T00:00:00Z.

### Step 2.2: Triggering Analysis Pipelines
1. Select the base elevation layer (`LOLA Polar DEM 20m/px`).
2. Click **"Execute Multi-Layer Analysis"**.
3. SelenePlan's orchestrator starts 4 concurrent analysis pipelines via Kafka:
   - **Terrain Analysis:** Computes elevation slope in radians ($0^\circ \text{ to } 90^\circ$) and roughness metrics.
   - **Illumination Engine:** Generates horizon elevation masks and simulates 720 time steps of solar elevation and azimuth using SPICE kernels.
   - **Comms Engine:** Raytraces direct-to-Earth line-of-sight (LOS) visibility and libration windows.
   - **Hazard ML Service:** Detects craters and boulders using verified ONNX models and fuses them into a conservative binary obstacle mask.
4. Watch the pipeline status cards until the join barrier completes and status transitions to `COMPLETED`.

### Step 2.3: Landing Site Candidate Ranking
1. Open the **"Candidate Sites"** drawer.
2. Select your mission objective profile:
   - *Science-Heavy:* Prioritizes proximity to permanently shadowed regions (PSRs).
   - *Safety-Heavy:* Maximizes continuous solar illumination ($> 70\%$) and direct Earth comms ($> 80\%$).
3. Click **"Rank Candidates"**. The ranking engine computes soft scores across candidate grid cells:
   $$\text{Score} = w_{illum} \cdot \bar{I} + w_{comms} \cdot \bar{C} - w_{slope} \cdot \bar{\alpha} - w_{hazard} \cdot \bar{H}$$
4. Click on top candidate `SITE-01` to lock it as the traverse starting waypoint.

### Step 2.4: Time-Expanded Traverse Planning
1. Set the destination scientific target (e.g. Ridge Peak $1.8\text{ km}$ away).
2. Configure rover energy parameters:
   - Solar panel area: $1.2\text{ m}^2$, solar efficiency: $28\%$.
   - Drive speed: $0.05\text{ m/s}$, rover mass: $150\text{ kg}$.
   - Max battery capacity: $1200\text{ Wh}$, min state-of-charge reserve: $20\%$.
3. Click **"Solve Traverse"**. The planner solves the space-time path $(x, y, t)$ via time-expanded A* search, ensuring the rover never runs out of power or enters impassable slopes ($> 15^\circ$).
4. Inspect the interactive **Energy State-of-Charge Profile** and **Comms Window Overlays** along the route.

### Step 2.5: What-If Contrastive Explanations
1. Want to know why the rover didn't take the direct straight-line path?
2. Open **"What-If Comparison"** and click **"Explain Rejection"** for the direct route.
3. The explainer generates contrastive natural-language rationales:
   > *"Direct path rejected: traverses a 22.4° slope exceeding the 15° rover stability limit at km 0.8, and encounters total shadow from 14:00 to 19:00 causing battery depletion."*

### Step 2.6: Submit for Multi-Person Review
1. Once satisfied with the traverse, click **"Submit Plan for Review"**.
2. The orchestrator locks the plan version, marks status as `SUBMITTED`, and emits an immutable `audit.event`.

---

## 3. Approver Workflow: Four-Eyes Review & Cryptographic Sign-Off

SelenePlan enforces a strict **Four-Eyes Policy** (`policies/plan_workflow.rego`):
- A plan requires **two distinct approver signatures** before it can be signed and exported.
- The analyst who created the plan **cannot approve their own plan**.
- Approvers must possess the `role: approver` and complete MFA token verification.

### Step 3.1: Plan Inspection
1. Log in as Approver 1 (`approver1@mission.org`).
2. Open the **"Pending Approvals"** inbox and select the submitted plan.
3. Review the safety checklist:
   - [x] Maximum slope along route: $11.8^\circ$ (within limit $< 15^\circ$).
   - [x] Minimum battery state-of-charge: $34.2\%$ (above reserve $> 20\%$).
   - [x] Continuous Earth comms coverage: $88.5\%$.
   - [x] Hazardous crater clearance: $> 15\text{ metres}$.

### Step 3.2: Record Approval Vote
1. Enter your approval comments and sign with your MFA token:
   ```json
   {
     "action": "APPROVE",
     "comments": "Traverse verified against LOLA DEM. Slope clearances and solar margins acceptable.",
     "mfa_token": "totp-829104"
   }
   ```
2. The plan status updates to `PENDING_SECOND_APPROVAL` (1 of 2 approved).

### Step 3.3: Second Approval & Automated Signing
1. Approver 2 (`approver2@mission.org`) reviews and records their approval vote.
2. The orchestrator verifies that Approver 1 $\neq$ Approver 2 $\neq$ Creator.
3. Once the second approval is recorded:
   - The state transitions to `APPROVED`.
   - The orchestrator dispatches the canonical JSON representation of the plan (RFC 8785) to `signing-service`.
   - HashiCorp Vault Transit produces an Ed25519 digital signature.
   - `report-service` compiles the official mission PDF/HTML briefing dossier.

---

## 4. Auditor & Mission Assurance Workflow

### Step 4.1: Offline Bundle Verification
Mission Assurance or international partners can verify any exported plan packet completely offline:
1. Download the exported bundle (e.g. `mission_plan_bundle.json`).
2. Run the offline verification CLI:
   ```bash
   python tools/verify_bundle.py path/to/mission_plan_bundle.json
   ```
3. Verification checks:
   - Recovers Ed25519 public key from the embedded key ID.
   - Canonicalizes payload according to RFC 8785.
   - Confirms signature validity.
   - Verifies input raster SHA-256 digests against provenance records.
   - Checks that 2 distinct approvers signed off.

### Step 4.2: Audit Hash Chain Verification
To ensure no database rows were tampered with, altered, or deleted:
1. Run the continuous audit chain verification tool:
   ```bash
   python -m services.audit_service.verify_chain \
     --db-url "$AUDIT_DB_URL" \
     --anchor-bucket "selene-audit-anchors"
   ```
2. The tool recalculates SHA-256 digests from genesis to tip and compares the daily digests with immutable WORM S3 Object Lock archives.

### Step 4.3: Deterministic Plan Replay
To prove that the plan's outputs were produced genuinely from the registered algorithms and inputs:
1. Execute the replay tool using the plan's provenance identifier:
   ```bash
   python tools/replay.py --plan-id "plan_8f912c" --tolerance-m 1.0
   ```
2. The CLI pulls historical inputs from MinIO, re-executes the time-expanded A* search, and asserts that the reproduced waypoint sequence and energy profile match within scientific tolerance.
