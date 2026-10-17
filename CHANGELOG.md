# Changelog

All notable changes to the SelenePlan platform are documented in this file.
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and [Conventional Commits](https://www.conventionalcommits.org/).

---

## [1.0.0] - 2026-10-18

### Initial Production Release (v1.0.0)

#### Highlights
- **Phase 0 (Foundation & Governance):**
  - Core security libraries (`selene-auth`, `selene-events`, `selene-observability`).
  - Keycloak OIDC integration, OPA Rego policy agent, Kong API Gateway.
  - Cryptographic append-only audit service with SHA-256 hash chaining.
- **Phase 1 (Lunar Data & Terrain):**
  - Planetary geodesy engine (`selene-geo`) enforcing IAU 2000 Moon reference sphere ($R = 1,737.4\text{ km}$).
  - Ingestion service with strict SSRF protection and host allowlisting.
  - DAG provenance service with cycle detection and SHA-256 artifact verification.
  - Terrain service computing slopes in radians, Horn's gradient, and Cloud-Optimized GeoTIFF sampling.
  - Real lunar south-pole data execution over Shackleton Crater ($20\text{ km} \times 20\text{ km}$, 20m/px LOLA DEM).
  - Modern web shell with MapLibre GL, Deck.gl, TailwindCSS, and WCAG AA accessibility compliance.
- **Phase 2 (Illumination Engine):**
  - Azimuthal horizon-profile elevation raytracing (`selene-horizon`).
  - NAIF SPICE planetary Sun ephemerides integration.
  - 720-step Zarr timestack solar availability computation, permanently shadowed regions (PSR) identification, and longest dark/lit duration stats.
- **Phase 3 (Earth Communications):**
  - Direct-to-Earth line-of-sight (LOS) visibility raytracing with lunar libration modeling.
  - Contact window extraction and blackout duration metrics.
  - Interactive dual-timeline synchronization in web UI.
- **Phase 4 (Hazard ML & Fusion):**
  - ONNX crater detection model with two-person gated signature verification.
  - Tiled CPU inference engine with circular non-maximum suppression (NMS) boundary deduplication.
  - Conservative hazard fusion joining slope, roughness, and ML detections.
- **Phase 5 (Planning, Integrity & Reporting):**
  - Pure-function rover energy state-of-charge model.
  - Landing site candidate ranking with multi-objective soft scoring.
  - Time-expanded space-time A* traverse solver avoiding slopes $> 15^\circ$ and battery depletion.
  - Contrastive what-if explainability engine.
  - Four-eyes approval state machine with MFA token enforcement.
  - RFC 8785 canonical plan JSON serialization with HashiCorp Vault Transit Ed25519 signing.
  - Offline cryptographic bundle verification tool (`tools/verify_bundle.py`).
  - Lineage-driven deterministic plan replay CLI (`tools/replay.py`).
  - Auto-escaping HTML/PDF mission briefing generator with DRAFT watermarking for unsigned plans.
- **Phase 6 (Enterprise Hardening & Resilience):**
  - Multi-stage minimal non-root Dockerfiles across all microservices.
  - Umbrella Helm chart with Pod Security Standards (Restricted) and PodDisruptionBudgets.
  - Default-deny Kubernetes NetworkPolicies with strict egress allowlists.
  - KEDA autoscalers on Kafka consumer lag.
  - Prometheus alerting rules (`AuditChainTamperDetected`, `AuthAnomalySpike`, `DLQMessageGrowth`, etc.) and Grafana Mission Control dashboard.
  - Disaster recovery restore drill achieving RTO $< 12\text{ minutes}$ and RPO $= 0\text{ s}$.
  - Full OWASP ASVS v4.0 penetration test with zero open High/Critical vulnerabilities.
- **Phase 7 (Documentation & Release):**
  - Complete C4 architecture models (Context, Container, Components).
  - Interactive Redoc OpenAPI documentation.
  - Analyst, Approver, and Auditor user guide and operations guide.
  - End-to-end scripted demo walkthrough and shot list with seed automation.
  - Scientific references bibliography, novelty statement, academic paper outline, and patent disclosure.
  - Third-party licenses audit and final review register.
