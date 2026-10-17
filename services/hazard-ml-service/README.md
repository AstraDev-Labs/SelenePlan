# hazard-ml-service

**Port:** 8104
**Tech:** FastAPI + worker, ONNX Runtime (CPU serving), Rasterio, SciPy
**Phase:** 4

## Purpose
Advisory machine learning crater and obstacle detection on lunar orthoimagery tiles (256x256), signed model registry with cryptographic verification and two-person approval gate, and conservative terrain hazard fusion (FR-12, FR-13, SEC-09, T7, T8).

## Architectural Design
- **Architecture ADR:** [ADR-0009: Hazard Detection Architecture: Dual-Head Circle-Aware CNN with ONNX Runtime CPU Serving](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/adr/0009-hazard-detection-architecture.md)
- **Data & Labels Plan:** [docs/ml/data-plan.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/ml/data-plan.md) (disjoint geographic splits, lighting-condition bins, boulder plan)
- **Evaluation Report:** [docs/ml/evaluation-report.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/ml/evaluation-report.md)
- **Phase 4 Demo Runbook:** [docs/demos/phase-4.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/demos/phase-4.md)

## Core Capabilities
1. **Model Registry & Two-Person Approval Gate:**
   - Cryptographic manifest signing (`sig:v1:...`) and SHA-256 binary checksums via Provenance/Vault Transit.
   - Enforces two-person separation of duty: model approver must be distinct from model creator (`check_two_person_rule`).
   - CI-style metrics gate: candidate models cannot be approved unless precision $\ge 0.70$ and recall $\ge 0.70$.
   - Tamper-evident loading: unsigned, tampered, or unapproved models are rejected and emit `selene.audit.event.v1`.
2. **CPU Inference Worker:**
   - 256x256 overlapping tiles with 32 px margins.
   - Spatial Circular Non-Maximum Suppression (NMS) merging detections across tile boundaries.
   - Zero GPU requirement: sub-100 ms per-tile CPU execution.
   - ONNX graph operator allowlist validation (no custom C++ plugins, no Python `pickle`).
3. **Hazard Fusion (FR-13):**
   - Combines deterministic physical terrain hazards (slope and TRI) with advisory ML crater detections.
   - Conservative max-pooling resampling when grid dimensions differ.
   - Full lineage tracking recorded in `params` (`terrain_product_id`, `ml_product_id`, `model_id`, `model_sha256`).

## API Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| `POST` | `/v1/models` | Register candidate model and manifest | Steward |
| `GET` | `/v1/models` | List registered models | Members |
| `GET` | `/v1/models/{id}` | Retrieve model card and metrics | Members |
| `POST` | `/v1/models/{id}/approve` | Approve model (enforcing metric gate & two-person rule) | Steward (2nd Approver) |
| `POST` | `/v1/inference` | Run tiled inference over AOI image | Members |
| `GET` | `/v1/products/{id}` | Retrieve product metadata and throughput | Members |
| `GET` | `/v1/products/{id}/detections` | Paginated GeoJSON FeatureCollection of crater circles | Members |
| `POST` | `/v1/fusion` | Fuse physical terrain hazards and ML hazard detections | Members |
| `GET` | `/healthz`, `/readyz` | Liveness and readiness health probes | Public |
| `GET` | `/metrics` | Prometheus metrics (`hazard_ml_` prefixed) | Public |

## Events
- **Consumes:** `selene.hazard.detection.requested.v1`
- **Produces:** `selene.hazard.detection.completed.v1`, `selene.audit.event.v1`

## Local Development & Testing
```bash
# Export and evaluate candidate ONNX model
python training/export_onnx.py
python training/evaluate.py

# Run test suite
pytest tests/ -v
```
