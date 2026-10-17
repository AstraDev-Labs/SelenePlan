# Phase 4 Demo Runbook: ML Hazard Detection and Hazard Fusion

This runbook demonstrates SelenePlan's Phase 4 machine learning crater detector, signed model registry with two-person gate, tiled CPU inference with boundary NMS deduplication, and conservative terrain hazard fusion (FR-12, FR-13, SEC-09, T7, T8).

---

## 1. Prerequisites & Services

```bash
# 1. Start core docker compose dependencies
docker compose -f infra/docker-compose.yml up -d

# 2. Launch hazard-ml-service
uvicorn hazard_ml_service.api.app:app --host 0.0.0.0 --port 8104 --reload

# 3. Launch web application
cd services/web && npm run dev
```

---

## 2. Automated Test Verification

Execute all unit, security, benchmark, component, and frontend test suites:
```bash
# Run hazard-ml-service test suite
pytest services/hazard-ml-service/tests/ -v

# Run web frontend tests
cd services/web && npm test -- --run
```

**Expected Results:**
- `services/hazard-ml-service`: 18 tests passed (signature verification, model tampering rejection, unapproved model rejection, operator allowlist check, circular NMS boundary deduplication, fusion truth tables, CPU throughput benchmark, REST API endpoints).
- `services/web`: 11 Vitest & axe-core tests passed with 0 accessibility violations.

---

## 3. Offline Model Evaluation & Gate Report

Run the reproducible evaluation pipeline across lighting bins and size bins:
```bash
python services/hazard-ml-service/training/evaluate.py
```
- Outputs metrics to `docs/ml/evaluation-report.md`.
- Evaluates Low Sun ($i > 80^\circ$, 0.967 recall), Medium Sun ($60^\circ \le i \le 80^\circ$, 1.000 recall), and High Sun ($i < 60^\circ$, 0.133 recall).
- Verifies robustness under sensor Gaussian noise, optical blur, and transmission dropouts.

---

## 4. Web UI Demonstration: Hazard Fusion & Advisory ML Detections

1. Open `http://localhost:5173` in a web browser.
2. In the **Map Layer Controls** sidebar:
   - Notice the **Active ML Model** card displaying `crater_detector_v1 (1.0.0, signed)`.
   - Observe the persistent **Advisory Note**: *"ML crater detections are advisory. Always consult terrain slope hazards independently."*
   - Toggle **ML Crater Detection (Advisory)** ON:
     - Vector crater circles (dashed fuchsia rings with confidence tags) appear around the Shackleton crater perimeter and connecting ridge.
   - Toggle **Fused Hazard Map (FR-13)** ON:
     - Raster updates with merged hazard zones: slope $> 15^\circ$ OR ML crater confidence $\ge 60\%$.
   - Adjust the **ML Confidence Cutoff** slider:
     - Observe real-time filtering from 40% (loose) to 95% (strict).
3. **Point Inspector:**
   - Hover over a detected crater:
     - Displays `FUSED HAZARD` (ML CRATER detected with confidence, e.g., 88%).
     - Highlights advisory label.
   - Hover over a steep crater rim wall:
     - Displays `FUSED HAZARD` (SLOPE LIMIT EXCEEDED).
   - Hover over smooth ridge terrain:
     - Displays `SAFE TERRAIN (TRAVERSABLE)`.
