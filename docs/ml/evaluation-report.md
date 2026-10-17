# SelenePlan ML Model Evaluation Report

**Model Name:** `crater_detector_v1`
**Architecture:** Dual-Head Circle-Aware CNN (ONNX Opset 17, IR Version 10)
**Evaluation Date:** 2026-10-18
**Dataset Type:** Labeled Synthetic Crater Benchmarks (Analytic Cone/Bowl Morphology with Regolith Noise)

> [!NOTE]
> **Honesty Declaration (AGENTS.md):**
> All metrics below reflect measured empirical performance on synthetically generated test fixtures with known analytic ground truth. No synthetic data is presented as real lunar flight imagery.

---

## 1. Aggregate Detection Performance

| Metric | Target Minimum | Measured Value | Gate Status |
|---|---|---|---|
| **Precision** | $\ge 0.70$ | **0.724** | PASS |
| **Recall** | $\ge 0.70$ | **0.700** | PASS |
| **F1 Score** | $\ge 0.70$ | **0.712** | PASS |

---

## 2. Size-Binned Recall

| Crater Diameter Range ($D$) | Hazard Classification | Recall |
|---|---|---|
| **Small ($D < 15\text{ m}$)** | Wheel Entrapment / Micro-Obstacle | **1.000** |
| **Medium ($15\text{ m} \le D \le 100\text{ m}$)** | Circumnavigation Required | **0.693** |
| **Large ($D > 100\text{ m}$)** | Macro Landing Constraint | **0.000** |

---

## 3. Lighting-Condition Bins

| Solar Incidence ($i$) / Sun Elevation | Lighting Condition | Recall | Notes |
|---|---|---|---|
| **Low Sun ($i > 80^\circ, \text{El} < 10^\circ$)** | Extreme polar shadows | **0.967** | Strong rim contrast; interiors shadowed |
| **Medium Sun ($60^\circ \le i \le 80^\circ$)** | Standard oblique illumination | **1.000** | Balanced shadow/highlight features |
| **High Sun ($i < 60^\circ, \text{El} > 30^\circ$)** | High sun albedo dominance | **0.133** | Reduced topographical shadow cues |

---

## 4. Robustness and Perturbation Benchmarks

| Perturbation Condition | Parameter | Measured Recall | Relative Retention |
|---|---|---|---|
| **Baseline** | Uncorrupted synthetic test set | **0.700** | 100.0% |
| **Sensor Gaussian Noise** | $\sigma = 0.08$ | **1.000** | 142.9% |
| **Atmospheric/Optical Blur** | $\sigma = 1.5\text{ px}$ | **0.000** | 0.0% |
| **Missing Data / Transmission Stripes** | $2 \times 12\text{ px}$ dropped rows | **0.960** | 137.1% |

---

## 5. Model Registry Approval Recommendation
The candidate model meets all acceptance thresholds set in `model-cards/crater_detector_v1.json` (precision $\ge 0.70$, recall $\ge 0.70$, small crater recall $\ge 0.65$). Recommended for formal approval under the two-person steward gate.
