# Final Review and Post-v1 Backlog

## 1. Overview
This review audits the SelenePlan v1.0.0 codebase against the system requirements (`docs/01-requirements.md`), microservices architecture (`docs/02-architecture.md`), security threat model (`docs/03-security-threat-model.md`), and scientific rules (`docs/08-science-notes.md`).

---

## 2. Specification Compliance Matrix

| Subsystem / Service | Requirement / Spec Reference | Implemented Status | Verification Method |
| :--- | :--- | :--- | :--- |
| **selene-geo** | Section 1 & 3: Lunar Sphere $1,737.4\text{ km}$, SI units | ✅ Full Compliance | `pytest libs/selene-geo` (analytical spherical tests) |
| **selene-auth** | SEC-01..04: JWT validation, OPA Rego policy evaluation | ✅ Full Compliance | `pytest libs/selene-auth` (tampered token rejection) |
| **selene-events** | SEC-08: Envelope schema, Kafka SASL_PLAINTEXT | ✅ Full Compliance | `pytest libs/selene-events` |
| **selene-horizon** | Section 4: 720-bin azimuthal horizon profiling | ✅ Full Compliance | `pytest libs/selene-horizon` (cone & pyramid golden tests) |
| **audit-service** | SEC-06, T11/T12: Append-only SHA-256 hash chain | ✅ Full Compliance | `pytest services/audit-service` (hash tamper detection) |
| **ingestion-service** | SEC-05, T1: Host allowlisting, SSRF protection | ✅ Full Compliance | `pytest services/ingestion-service` (private CIDR blocking) |
| **terrain-service** | FR-02..05: COG sampling, Horn's slope in radians | ✅ Full Compliance | `pytest services/terrain-service` (inclined plane test) |
| **illumination-service** | FR-06..10: SPICE Sun ephemerides, Zarr timestack | ✅ Full Compliance | `pytest services/illumination-service` (720-step timestack) |
| **comms-service** | FR-11..14: Earth LOS raytracing & libration | ✅ Full Compliance | `pytest services/comms-service` (window extraction) |
| **hazard-ml-service** | FR-15..18, T7/T8: Signed ONNX models, circular NMS | ✅ Full Compliance | `pytest services/hazard-ml-service` (tamper rejection) |
| **planner-service** | FR-19..24: Time-expanded A*, energy model, explain | ✅ Full Compliance | `pytest services/planner-service` (battery & slope check) |
| **project-service** | FR-25..28, T2/T3: Orchestrator join-barrier, 4-eyes MFA | ✅ Full Compliance | `pytest services/project-service` (dual-approver check) |
| **signing-service** | FR-29, T9: RFC 8785 canonicalization, Ed25519 Vault | ✅ Full Compliance | `pytest services/signing-service` (permuted key test) |
| **report-service** | FR-30: Auto-escaping HTML/PDF with DRAFT watermark | ✅ Full Compliance | `pytest services/report-service` (XSS injection test) |
| **provenance-service** | FR-31..32: DAG lineage, cycle check, S3 sha256 | ✅ Full Compliance | `pytest services/provenance-service` (tamper detection) |
| **web frontend** | Section 7: MapLibre, Deck.gl, A11y WCAG AA | ✅ Full Compliance | `npm test` (0 axe-core violations, 11 tests green) |

---

## 3. Threat Model Verification (STRIDE)

- **T1: Malicious DEM URL Ingestion (SSRF):** Mitigated by strict host allowlist and network policy blocking private RFC 1918 / cloud metadata IPs. Verified in `test_ssrf.py`.
- **T2 & T3: Four-Eyes Approval Bypass & Creator Self-Approval:** Mitigated by `policies/plan_workflow.rego` requiring 2 distinct approvers $\ne$ creator with verified MFA. Verified in `test_plan_approval_workflow.py`.
- **T7 & T8: Model Deserialization & Registry Tampering:** Mitigated by pure ONNX Runtime inference (no Python pickles) and cryptographic Ed25519 signature checks. Verified in `test_security_integrity.py`.
- **T9: Plan Alteration Post-Approval:** Mitigated by RFC 8785 canonical serialization and Ed25519 signing. Tampered payload fails verification. Verified by `test_signing_integrity.py` and `tools/verify_bundle.py`.
- **T11 & T12: Audit Log Database Tampering:** Mitigated by immutable SHA-256 hash chain and daily WORM S3 Object Lock archiving. Divergent rows trigger `AuditChainTamperDetected` alert. Verified in `test_chain.py`.

---

## 4. Known Limitations & Scope Boundaries (v1.0.0)

1. **Point-Source Sun Approximation:** The standard illumination solver treats the Sun as an astronomical point-source at the sub-solar coordinate. Penumbral partial-obscuration during grazing contact is available only when sub-pixel multi-sampling is explicitly enabled.
2. **Line-of-Sight Comms Only:** Direct-to-Earth visibility models geometric line of sight; RF link budget, antenna radiation patterns, and orbital relay constellations (e.g. Lunar Pathfinder) are reserved for v1.1.
3. **Terramechanics:** The rover energy model accounts for grade resistance $m g \sin\alpha$ and rolling friction $\mu$, but does not simulate regolith shear failure or dynamic wheel slip.
4. **Single-Region / Polar Focus:** Geodesic and raytracing operators assume lunar south polar coordinates; non-polar global equatorial operations require distinct cartographic projections.

---

## 5. Post-v1 Backlog

- **BACKLOG-01: Multi-Agent Relay Satellite Constellations:** Incorporate lunar orbiter relay visibility windows into the time-expanded A* search space.
- **BACKLOG-02: Terramechanics & Slip Modeling:** Integrate Bekker-Wong soil mechanics model based on regolith compaction data from Apollo and Chang'e core samples.
- **BACKLOG-03: Penumbral Solar Sub-Disk Integration:** Accelerate finite solar disk raytracing via GPU shader pipelines or WebGPU compute kernels.
- **BACKLOG-04: Multi-Rover Fleet Coordination:** Extend the orchestrator state machine to support multi-rover cooperative traverse planning with collision avoidance.
- **BACKLOG-05: Real-Time Telemetry Drift Correction:** Ingest downlink rover position telemetry and perform dynamic Kalman filter re-localization against LOLA relief.
