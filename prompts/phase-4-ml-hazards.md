# Phase 4: ML hazard detection and hazard fusion

**Goal:** a signed, versioned crater (and later boulder) detector served on CPU, producing confidence-aware hazards that are fused with terrain hazards.

**Read first:** `services/hazard-ml-service/SPEC.md`, `services/provenance-service/SPEC.md`, `docs/08-science-notes.md` (section 6), `docs/03-security-threat-model.md` (T7, T8), `docs/06-testing-strategy.md` (section 7).

**Honesty rules for this phase:** do not claim accuracy you did not measure. Report metrics by lighting condition. Label synthetic data as synthetic. Check licenses for every dataset and catalog before use.

## Tasks

### Task 4.1: Data and labels plan
Write `docs/ml/data-plan.md`: imagery sources and licenses, crater catalog source and license, tiling strategy, train/validation/test split (**split by geographic area, not by random tile**, to avoid leakage), lighting-condition bins, and a boulder labeling plan. Wait for my approval.

### Task 4.2: Training and evaluation pipeline
In `services/hazard-ml-service/training/`: reproducible scripts (seeded, config files), a baseline detection or segmentation model (choose and justify in an ADR), evaluation producing precision, recall, and size-binned recall, split by lighting bin, plus a robustness table (noise, blur, no-data stripes).
**Done when:** running the pipeline on a small subset produces a metrics report and an ONNX export; results are reproducible with the same seed.

### Task 4.3: Model registry with signing
Implement registry API and storage, model cards, SHA-256, manifest signature via provenance (Vault Transit, separate key from plan signing), `approved` flag with the CI-style metrics gate, second-approver rule.
**Done when:** loading an unsigned or tampered model fails and raises an audit event (test); an under-threshold model cannot be approved (test).

### Task 4.4: Inference worker
Tiled inference with overlap, batching, NMS merge, detections to storage, hazard raster with confidence band, ONNX graph validation (input/output shapes, operator allowlist), no pickle. CPU only.
**Done when:** synthetic-image test with drawn craters meets the documented recall threshold; tile-boundary de-duplication test passes; throughput benchmark recorded.

### Task 4.5: Hazard fusion
Implement fusion of terrain hazard and ML detections: hazard if terrain hazard OR (ML confidence at or above threshold); thresholds configurable and recorded in `params`; conservative resampling (max-pool).
**Done when:** truth-table tests pass; the fused hazard product is registered with lineage to both inputs and the model version.

### Task 4.6: UI
Add the hazard layers (terrain, ML with confidence, fused) with a clear legend and a persistent note that ML detections are advisory. Show the model name and version in the layer info.
**Done when:** Playwright test passes; accessibility check passes.

## Phase 4 exit criteria
Signed model registry, evaluation report published in `docs/ml/evaluation-report.md` (with limitations), inference and fusion working, tests passing, `docs/demos/phase-4.md`.
