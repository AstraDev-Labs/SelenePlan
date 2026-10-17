# Phase 2: Illumination and shadow engine

**Goal:** correct, reasonably fast time-varying illumination for the small AOI with a timeline UI. This is the scientific core. Go slowly and verify.

**Read first:** `services/illumination-service/SPEC.md`, `docs/08-science-notes.md` (sections 1, 4, 8, 9), `docs/adr/0004-cog-postgis-storage.md`, `docs/06-testing-strategy.md` (golden and property tests).

**Important:** you are not allowed to invent astronomy. Use SPICE (SpiceyPy) with NAIF kernels recorded in provenance. If kernel file names or frames are uncertain, stop and ask me to confirm them.

## Tasks

### Task 2.1: ADRs before code
Write two ADRs and wait for my approval:
1. **Illumination algorithm:** compare horizon-profile, per-time ray marching, and hybrid for our needs (many time steps, AOI about 10 to 20 km at 20 m/px, 1 lunar day to 1 year). Include complexity estimates, accuracy issues (curvature over long rays, padding margin), and a recommendation.
2. **Time-stack storage:** banded COG per time step vs Zarr vs hybrid; benchmark plan for slice reads and per-cell time-series reads.
Do not implement yet.

### Task 2.2: Sun geometry module
Implement `sun/` using SPICE: Sun direction in the Moon-fixed frame over a time axis, converted to local azimuth and elevation per cell (account for the local vertical). Record kernel names and checksums.
**Done when:** known-answer checks against independent SPICE calls for several timestamps pass; units and frames documented; no hand-rolled ephemerides.

### Task 2.3: Horizon computation (`libs/selene-horizon`)
Implement horizon-profile computation for the DEM (azimuth bins configurable), tiled with halos and padding margin computed from relief and minimum sun elevation. Shared library because comms-service will reuse it.
**Done when:** golden tests pass: flat plane (horizon 0), cone (analytic horizon angle), bowl crater (rim angle). Performance benchmark recorded for 1k x 1k and 4k x 4k tiles; Numba with `nogil` and parallelism used where justified.

### Task 2.4: Illumination worker
Implement the pipeline per the ADRs: consume `illumination.analysis.requested`, compute lit masks per time step, write the time stack, compute stats (lit fraction, longest dark, longest lit, permanently shadowed), emit completion event, register provenance.
**Done when:** SPEC acceptance criteria 1 to 6 pass, including the convergence test and the brute-force reference property test for longest-dark.

### Task 2.5: API and serving
Implement `slice`, `timeseries`, `stats` endpoints, TiTiler integration for tiles, Redis caching for slices, authz and project scoping.
**Done when:** slice p95 under 500 ms with cache on a test AOI (k6 or equivalent evidence), authz negative tests pass.

### Task 2.6: UI timeline
Add the timeline scrubber to the map: play/pause, speed, debounced slice requests, prefetch, point inspector with the lit/dark series.
**Done when:** scrubbing is smooth; Playwright test covers it with a mocked backend; accessibility check passes (keyboard control).

### Task 2.7: Validation
Pick one well-studied south-polar location and compare lit fraction and longest dark period against **published values I provide or you find with citations**. Document method, results, discrepancies, and likely causes in `docs/validation/illumination-validation.md`. Do not tune parameters to force agreement without saying so.
**Done when:** the document exists and is honest about limits. Flag results for my expert review.

## Phase 2 exit criteria
Time-stacked illumination with timeline UI, golden/property/convergence tests passing, validation note written, performance baseline recorded against NFR-03, `docs/demos/phase-2.md`.
