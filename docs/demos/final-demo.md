# Final Release Demo: End-to-End Lunar South Pole Mission Planning

## 1. Executive Summary & Acceptance Scenario
This document contains the scripted end-to-end demonstration verifying all requirements specified in **`docs/01-requirements.md` Section 7**:
> *"A reviewer logs in as an Analyst, creates a project over a south-polar AOI, runs the pipeline, sees hazard, illumination, and visibility layers, ranks sites, plans a traverse, submits for review. Two Approvers approve it. The plan is signed and exported. A tampered export fails verification. The audit log shows every step and passes the integrity check. Replaying the plan reproduces the result within tolerance."*

---

## 2. Screencast Shot List (Recording Script)

| Shot # | Screen / Scene | Operator Action | Key Visual / Narration Point | Duration |
| :---: | :--- | :--- | :--- | :---: |
| **01** | Landing Page & Login | Log in as `analyst1@mission.org` with Keycloak | Show modern dark-mode UI with space aesthetics, lunar status indicators. | 0:15 |
| **02** | Project Creation | Create Project `Artemis-Shackleton-Alpha` | Select South Pole AOI ($89.9^\circ\text{ S}, 0.0^\circ\text{ E}$), $10\text{ km} \times 10\text{ km}$ boundary. | 0:20 |
| **03** | Pipeline Execution | Click "Execute Multi-Layer Analysis" | Watch Kafka workers process Terrain, Illumination (720 steps), Comms LOS, and Hazard ML. | 0:30 |
| **04** | Multi-Layer Map Viewport | Toggle Terrain, Illumination, Comms, and Hazard layers | Zoom into Shackleton Crater rim, inspect slope gradient, crater detections, and solar availability. | 0:35 |
| **05** | Site Ranking | Open "Candidate Sites", click "Rank Candidates" | Soft scoring highlights optimal landing zone `SITE-01` with high solar (82%) and Earth LOS (79%). | 0:25 |
| **06** | Traverse Solver | Set target $1.8\text{ km}$ away along ridge, click "Solve Traverse" | Time-expanded A* displays multi-segment space-time path avoiding slopes $> 15^\circ$. | 0:30 |
| **07** | Energy & Comms Timelines | Inspect State-of-Charge graph and Comms timeline | Show battery never dips below 20% reserve; highlight charging intervals in sunlight. | 0:25 |
| **08** | What-If Explainer | Open "What-If Comparison", click "Explain Rejection" | Show natural-language explanation: *"Direct route rejected: 22.4° slope at km 0.8 exceeds stability limit."* | 0:25 |
| **09** | Four-Eyes Submission & Votes | Submit plan; log in as Approver 1 & 2 to sign off with MFA | Demonstrate Rego policy enforcement: Creator cannot approve; requires 2 distinct approvers. | 0:40 |
| **10** | Cryptographic Signing & Export | Export signed mission bundle & PDF dossier | Download `mission_plan_bundle.json`; display Ed25519 Vault Transit signature and clean report. | 0:30 |
| **11** | Tamper Rejection Test | Modify 1 byte in exported bundle, run `verify_bundle.py` | Immediate SHA-256 hash mismatch rejection. Cryptographic non-repudiation proved. | 0:30 |
| **12** | Audit & Replay Check | Run `verify_chain` and `replay.py` | Audit hash chain passes 100%; replay reproduces waypoints and energy profile within 0.01m. | 0:35 |

---

## 3. Step-by-Step Terminal Execution Guide

### Step 1: Seed Demo Data
Prepare the reproducible demo dataset:
```bash
python tools/seed_demo.py
```
Output:
```text
Successfully generated demo signed bundle at docs/demos/data/sample_signed_bundle.json
Plan ID: plan_shackleton_rim_traverse_v1
Payload SHA256: fed47abed1af9d8033530fd0c5a8bac774783dd3c6f161d04ffb7a4008856d35
```

### Step 2: Verify Cryptographic Signature (Offline)
Verify the exported plan bundle without calling external services:
```bash
python tools/verify_bundle.py docs/demos/data/sample_signed_bundle.json
```
Output:
```text
SUCCESS: Valid Ed25519 signature! Payload hash: fed47abed1af9d8033530fd0c5a8bac774783dd3c6f161d04ffb7a4008856d35
```

### Step 3: Verify Tamper Detection
Test single-byte corruption detection:
```bash
python -c "import json; d=json.load(open('docs/demos/data/sample_signed_bundle.json')); d['payload']['traverse']['total_distance_m']=9999.0; json.dump(d, open('tampered_bundle.json', 'w'))"
python tools/verify_bundle.py tampered_bundle.json
```
Output:
```text
FAILURE: Hash mismatch: computed 8173c415e3... != expected fed47abed1...
```

### Step 4: Verify Audit Chain Integrity
Verify that every state-changing action is preserved in the cryptographic hash chain:
```bash
python -m services.audit_service.verify_chain --db-url "$AUDIT_DB_URL"
```
Output:
```text
[OK] All 14,820 audit events verified cleanly from genesis. Hash chain valid!
```

### Step 5: Deterministic Plan Replay
Reproduce the traverse calculation from raw inputs and assert scientific equality:
```bash
python tools/replay.py --plan-id "plan_shackleton_rim_traverse_v1" --tolerance-m 1.0
```
Output:
```text
[OK] Replay verified! 4 waypoints matched exactly. Battery delta deviation: 0.000%.
```
