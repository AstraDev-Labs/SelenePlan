# Machine Learning Data and Labels Plan: Crater & Hazard Detection

**Document Version:** 1.0.0
**Phase:** 4 (ML Hazard Detection & Hazard Fusion)
**Status:** Approved
**Author:** SelenePlan Core Engineering Team

---

## 1. Objective and Scope
The goal of the ML hazard detection pipeline in SelenePlan is to identify landing and traverse hazards (primarily impact craters and boulders) in high-resolution lunar orthoimagery (e.g., LRO NAC at 0.5–2.0 m/px and LOLA shaded relief products). The detector produces confidence-calibrated detections and a hazard raster layer that is fused with deterministic physical terrain hazards (slope and topographic roughness).

In accordance with `AGENTS.md` and `docs/08-science-notes.md`:
- Detections are advisory and treated as a secondary constraint.
- Synthetic training/testing fixtures are explicitly labeled as synthetic.
- All real data and catalog sources are checked for licensing and redistribution permissions.

---

## 2. Data Sources and Licensing

| Dataset / Catalog | Source / Instrument | Resolution / Coverage | License / Rights | Planned Role |
|---|---|---|---|---|
| **LRO NAC Orthoimages** | NASA PDS Imaging Node / ASU LROC | 0.5 – 1.5 m/pixel; targeted polar and equatorial AOIs | US Government Public Domain (NASA Open Data Policy) | Primary imagery for crater and boulder detection |
| **Robbins Crater Database** | Robbins et al. (2014, 2018), USGS / NASA | Global catalog down to ~1–2 km diameter; regional high-resolution catalogs down to ~100 m | Public Domain / CC0 (USGS Publications) | Primary reference catalog for medium-to-large craters |
| **LOLA Altimetry Relief** | NASA PDS Geosciences Node / GSFC | 5 – 20 m/pixel south-polar DEM / hillshade | US Government Public Domain | Auxiliary elevation and morphological feature maps |
| **Synthetic Crater Benchmark** | Procedural crater synthesis engine (`selene-testing`) | Arbitrary resolution, ground truth analytic ellipses | SelenePlan Apache-2.0 / Internal | Golden test suites, robustness and degradation benchmarks |

---

## 3. Tiling Strategy and Spatial Indexing
Lunar orthoimages are large (tens of gigabytes per strip). To support efficient CPU-based inference and eliminate memory bottlenecks:
1. **Tile Dimensions:** Canonical tile size is $256 \times 256$ pixels (with $512 \times 512$ supported for high-resolution passes).
2. **Overlap:** Adjacent tiles overlap by $32$ pixels ($12.5\%$) on each dimension:
   $$\text{Stride} = \text{Tile Size} - \text{Overlap} = 256 - 32 = 224\text{ px}$$
3. **Boundary Handling:** Edge pixels are padded using reflection or zero-fill with no-data masking. Detections falling within the overlap margins are deduplicated via spatial Non-Maximum Suppression (NMS) in global projected coordinates (Stereographic IAU_MOON, EPSG:3031 equivalent for Moon).

---

## 4. Train / Validation / Test Geographic Split

> **CRITICAL RULE (Leakage Prevention):**
> Splitting randomly across tiles creates spatial autocorrelation and severe data leakage due to overlapping tiles and contiguous crater ejecta blankets.
> Therefore, data must be partitioned strictly by **discrete geographic areas (quadrangles / polar regions)**.

```
+-------------------------------------------------------------------+
|                        LUNAR SOUTH POLAR REGION                   |
|                                                                   |
|   TRAINING AOI-A (85°S-88°S, 0°-90°E)    TRAINING AOI-B           |
|   [Amundsen / Faustini Rim]              [Shoemaker / Faustini]   |
|                                                                   |
|   VALIDATION AOI (88°S-89°S, 90°E-180°E)                          |
|   [Nobile / Haworth Plateau]                                      |
|                                                                   |
|   TEST / BENCHMARK AOI (89°S-90°S, All Longitudes)                |
|   [Shackleton Crater & Connecting Ridge - Artemis III Zone]       |
+-------------------------------------------------------------------+
```

- **Training Set (65% area):** Discrete sub-polar quadrangles with varying illumination and topography.
- **Validation Set (15% area):** Spatially disjoint quadrangle used for hyperparameter tuning, NMS threshold calibration, and ONNX quantization verification.
- **Test Set (20% area):** Shackleton Crater and de Gerlache connecting ridge ($89.5^\circ\text{S} - 90^\circ\text{S}$). Never accessed during training or hyperparameter search.

---

## 5. Lighting-Condition Bins
Crater detection performance is fundamentally linked to solar incidence angle $i$:
- **Low Sun ($i > 80^\circ$, Elevation $< 10^\circ$):** Extreme south polar conditions. Long casting shadows delineate rim crests prominently, but deep crater interiors and permanently shadowed regions (PSRs) suffer total signal loss (no-data shadow saturation).
- **Medium Sun ($60^\circ \le i \le 80^\circ$, Elevation $10^\circ - 30^\circ$):** Distinct contrast and shadow geometry; optimal balance between feature delineation and interior terrain visibility.
- **High Sun ($i < 60^\circ$, Elevation $> 30^\circ$):** Low morphological shadow contrast; high albedo variations (fresh ray systems) dominate and can produce false positives.

**Evaluation Protocol:**
All precision and recall metrics MUST be reported independently across these three bins, as well as an aggregate metric.

---

## 6. Size-Binned Metrics
Craters represent distinct hazards depending on rover scale (e.g., $1.5\text{ m}$ wheelbase):
1. **Small Craters ($D < 15\text{ m}$):** Direct wheel entrapment and high slope hazard.
2. **Medium Craters ($15\text{ m} \le D \le 100\text{ m}$):** Navigational obstacles requiring path circumnavigation.
3. **Large Craters ($D > 100\text{ m}$):** Macro-topographic structures dominating landing ellipse feasibility and comms line-of-sight.

Evaluation pipelines will measure precision, recall, and F1 per size bin.

---

## 7. Boulder Labeling Plan
While Phase 4 focuses primarily on craters, boulders represent high-consequence puncture/rollover hazards.
1. **Resolution Requirement:** Boulders require high-resolution NAC imagery ($\le 0.5\text{ m/px}$). A $2\text{ m}$ boulder spans only $4\text{ px}$.
2. **Labeling Protocol:**
   - Semi-automated shadow-tip extrusion: Shadows of positive relief features point away from the sun azimuth; length of shadow $L = h / \tan(\theta_{\text{elev}})$.
   - Human-in-the-loop verification on sampled benchmark quads.
   - Dual-annotator agreement: Minimum IoU of $0.70$ required between two independent analysts for inclusion in the ground-truth benchmark set.
