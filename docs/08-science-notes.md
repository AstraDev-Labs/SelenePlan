# 08. Science Notes: Data, Algorithms, Validation, Assumptions

This document guides implementation and keeps scientific claims honest. **Items marked VERIFY must be checked against the primary source before relying on them.** Nothing here is mission-certified.

## 1. Reference frame and coordinates
- Moon treated as a sphere of radius **1737.4 km** for geometry unless a dataset defines otherwise (VERIFY dataset metadata; record it per dataset).
- Region of interest: south polar region, typically poleward of about 80 degrees south.
- Projection: south polar stereographic in metres for analysis; store CRS WKT with each product.
- Distinguish **planetocentric** latitude (used by most lunar data products) from planetographic. For a sphere they coincide, but keep the habit and the field names explicit.
- Elevation reference: elevations are relative to the lunar reference sphere in many LOLA products (VERIFY product label).

## 2. Data sources (public)
| Data | Source | Notes |
|---|---|---|
| Lunar DEMs (south polar) | LRO LOLA gridded products via the NASA PDS Geosciences Node | Multiple resolutions exist, including polar products and site-specific higher-resolution tiles (VERIFY current product names and resolutions) |
| Orthoimagery | LRO LROC NAC / WAC products via PDS and LROC site | NAC resolution is roughly sub-metre to a few metres per pixel depending on image; lighting varies by image (VERIFY) |
| Ephemeris and frames | NAIF SPICE kernels (planetary ephemeris SPK, leap-second LSK, lunar orientation PCK, frame kernels) | Use SpiceyPy; record kernel file names and checksums in provenance |
| Chandrayaan products | ISRO PRADAN portal | Access may require registration; **VERIFY license and redistribution terms** before ingesting or exporting |
| Crater catalog | A published lunar crater database (for ML labels and evaluation) | VERIFY license and citation requirements |
| Illumination reference | Published LOLA-derived south-pole illumination studies and maps | Use only to validate, cite properly |

Record `source_url`, `license`, `terms_note`, `redistributable`, and checksums for every dataset (FR-01).

## 3. Terrain analysis
- **Slope and aspect:** use a documented gradient operator (e.g., Horn's method on a 3x3 window). State the choice in an ADR. Account for polar stereographic scale distortion if the analysis footprint is large (VERIFY magnitude for the chosen AOI and correct if non-negligible).
- **Roughness:** choose a measure and document it (e.g., local standard deviation of elevation after detrending, or terrain ruggedness index). Rover constraints use slope plus roughness thresholds from the rover profile.
- **No-data handling:** never treat no-data as zero. Propagate masks. Planner treats unknown cells as untraversable unless configured otherwise.
- **Scale dependence:** slope depends on pixel size. Record `resolution_m` and keep hazard thresholds tied to a stated baseline length.

## 4. Illumination and shadow
Goal: for each cell and time, determine whether the **Sun** is above the local horizon and unobstructed by terrain, and optionally the fraction of the solar disk visible.

**Inputs:** DEM, sun position over time (from SPICE in a Moon-fixed frame), AOI.

**Approach options (decide via ADR in Phase 2):**
1. **Horizon-profile method:** for each cell, precompute a horizon elevation angle as a function of azimuth (for example 360 or 720 azimuth bins). A cell is lit at time t if the Sun elevation exceeds the horizon angle in the Sun's azimuth direction. Cost is paid once for the horizon, then each time step is cheap. Good fit for many time steps.
2. **Per-time ray marching:** for each time step, march rays toward the Sun across the DEM. Simpler, costlier when time steps are many.
3. **Hybrid:** coarse horizon from large-scale terrain plus fine local checks.

**Details to handle:**
- Sun elevation near zero at the poles: the Sun skims the horizon. Small elevation errors matter greatly, so use accurate ephemerides and the true local horizontal at each cell (account for terrain curvature over long ray distances; planar approximation may be insufficient for tens of kilometres, VERIFY error for chosen AOI).
- **Finite solar disk:** the Sun spans about 0.5 degrees. Optionally compute the visible fraction (penumbra) by sampling several disk points. Start with a point-source Sun and document the limitation.
- Ray reach: terrain far outside the AOI can cast shadows. Pad the DEM beyond the AOI by a computed margin (maximum relevant shadow length from the largest relief and lowest sun elevation).
- Time axis: choose `time_step_s` that resolves terminator motion for the AOI (VERIFY by convergence test: halve the step, compare lit fractions).
- Outputs: per-time lit mask (or fraction), lit fraction over period, longest continuous dark interval, longest continuous lit interval, and permanently shadowed mask over the period.

## 5. Earth visibility
- Compute the direction to Earth in the local topocentric frame (azimuth and elevation) for each cell over time using SPICE and the Moon-fixed frame (this includes libration).
- A cell has direct-to-Earth line of sight when Earth elevation exceeds the terrain horizon in the Earth azimuth (same horizon machinery as illumination can be reused).
- Near the south pole, Earth appears near the horizon and moves slowly, so visibility depends strongly on local terrain. Windows can be long or absent.
- Outputs: visible mask per time, visibility fraction, longest blackout, window list per cell or per path.
- Limitation: line of sight only. No link budget, antenna pattern, or relay satellites in v1.

## 6. Hazard detection (ML)
- Task: detect craters and boulders (and optionally shadow masks) in orthoimagery tiles. Start with craters (public catalogs exist), then add boulders with a labeling plan.
- Model: choose a known detection or segmentation architecture; document the choice in an ADR. Train with seeded, reproducible scripts. Export to ONNX for serving.
- **Lighting dependence:** images taken at low sun angles produce strong shadows that help crater detection but hide terrain inside shadows. Evaluate separately by incidence angle.
- **Policy:** ML output is advisory. The hazard map fuses (a) terrain-derived hazard (slope, roughness) and (b) ML detections above a confidence threshold. The planner treats either as a constraint according to config.
- Provide a **model card**: data, metrics, limitations, intended use.

## 7. Planning model
**Site ranking**
- Hard constraints: slope under a limit over a landing ellipse footprint (configurable radius), no hazardous detections inside the footprint, minimum lit fraction (optional), minimum Earth visibility fraction (optional).
- Soft score: weighted sum of normalized criteria (lit fraction, shortest longest-dark interval, Earth visibility fraction, distance to science targets, terrain roughness). Weights are user-set; show the breakdown.
- Rejection reasons are stored and shown (FR-23).

**Traverse planning**
- Grid at planning resolution (coarser than the DEM, e.g., 20 to 40 m, configurable). 8- or 16-connected moves with slope-dependent speed and cost.
- **Time-expanded search:** state is (cell, time bucket, battery bucket). Actions: drive, wait, charge (while lit), idle. Cost: weighted combination of time, energy, risk. Prune with admissible heuristics where possible.
- **Energy model (simple, configurable):** solar power = panel area x efficiency x flux x cos(incidence), with incidence from sun direction and local slope if panel orientation model is enabled; otherwise use a horizontal panel approximation. Consumption by mode (drive, idle, comms). Survival constraint: battery above a minimum; during long darkness the plan must include enough stored energy or fail with an explanation. (VERIFY solar flux value and document assumptions.)
- Comms: optional checkpoints that require Earth visibility, and optional "maximum consecutive blackout" constraint.
- **Explanation:** when an alternative fails, record the first violated constraint with location and time and aggregate into a human-readable statement.

## 8. Validation plan
1. **Analytic tests** (see `06-testing-strategy.md`).
2. **Convergence tests:** change DEM resolution, time step, azimuth bins. Illumination statistics should converge. Record results in `docs/validation/convergence.md`.
3. **Comparison with published results:** choose one well-studied south-polar location. Compare lit fraction and longest dark period to published values. Document method, differences, and likely causes. Do not tune parameters to force agreement without noting it.
4. **Independent review:** have an advisor, professor, or domain expert review assumptions and the validation notes before publishing claims.

## 9. Known limitations (state them in the UI and reports)
- Point-source Sun by default; no penumbra unless enabled.
- No dust, regolith mechanics, thermal environment, or wheel-soil interaction.
- Line-of-sight communication only.
- Accuracy bounded by DEM resolution and artifacts.
- ML detector recall and precision are limited and vary with lighting.
- Not a flight-qualified tool.

## 10. Assumptions register (fill in during development)
| ID | Assumption | Source or rationale | Owner | Status |
|---|---|---|---|---|
| AS-01 | Moon radius 1737.4 km | IAU value | Terrain | VERIFY vs dataset |
| AS-02 | Default rover max slope | Configurable placeholder | Planner | Needs mission input |
| AS-03 | Solar constant at 1 AU | Standard value | Planner | VERIFY and cite |
| AS-04 | Point-source Sun | Simplification | Illumination | Revisit |
| AS-05 | Planning grid resolution | Performance tradeoff | Planner | Tune |

## 11. Citations to collect (do this early)
Keep `docs/references.md` with full citations for: LOLA instrument and DEM products, LROC NAC, SPICE toolkit and kernels, any illumination studies used for validation, any crater catalog used, and the ML architecture papers.
