# Phase 1: Data ingestion and terrain analysis

**Goal:** securely ingest a DEM, convert it to a COG, compute slope/aspect/roughness, show it on a map, and record provenance.

**Read first:** `services/ingestion-service/SPEC.md`, `services/terrain-service/SPEC.md`, `services/provenance-service/SPEC.md`, `services/web/SPEC.md`, `docs/04-data-model.md`, `docs/08-science-notes.md` (sections 1 to 3), `docs/06-testing-strategy.md`.

**Precondition:** Phase 0 exit criteria met. Choose the AOI and datasets in `docs/validation/aoi.md` (P-0) before Task 1.5, and check dataset licenses.

## Tasks

### Task 1.1: `selene-geo` and `selene-testing` libraries
- `selene-geo`: constants (Moon radius), lunar polar stereographic CRS helpers (explicit WKT strings, never an Earth default), raster window and tiling helpers with halo support, COG validation helper.
- `selene-testing`: synthetic terrain generators with **analytic answers**: inclined plane (given slope and aspect), flat plane, cone, bowl crater, ridge, plus seeded noise.
**Done when:** unit tests verify generators produce the stated geometry (e.g., plane slope is exactly as requested).

### Task 1.2: Ingestion service
Implement `services/ingestion-service` per SPEC, including: source allowlist config, **SSRF protections**, size and dimension limits, decompression guard, COG conversion with overviews, SHA-256 of source and output, manifest, registry tables, events, upload path for Stewards.
**Done when:** all acceptance criteria pass, especially the full SSRF test matrix and bomb tests. Show the test output.

### Task 1.3: Provenance service MVP
Implement artifact registry, lineage edges, `verify-artifact`, and automatic registration from `dataset.registered` and `terrain.analysis.completed` events. Skip manifest signing until Phase 4 but leave the interface.
**Done when:** corrupting a stored object makes `verify-artifact` fail; lineage query returns correct ancestors on a synthetic pipeline.

### Task 1.4: Terrain service
Implement per SPEC: slope (Horn), aspect, roughness, hazard mask from thresholds, tiled processing with halos, no-data propagation, COG outputs, events. Record the operator choice and roughness definition in `services/terrain-service/DECISIONS.md`.
**Done when:** golden tests (10-degree plane, flat plane), property tests (constant offset invariance, 90-degree rotation), tile-seam test, and no-data tests pass.

### Task 1.5: Real data run (small AOI)
Using a script `scripts/ingest_sample.py`, ingest one small real DEM tile for the chosen AOI (download via the allowlisted source mechanism; do not commit data). Run terrain analysis. Record resolution, throughput, and any anomalies (seams, voids) in `docs/validation/terrain-notes.md`.
**Done when:** products exist, hashes verify, and results look physically reasonable (describe what you checked).

### Task 1.6: Web shell
Create `services/web` per SPEC: Vite React TypeScript app, OIDC login with PKCE, role-aware navigation, project list, a map view (choose MapLibre or deck.gl for the 2D polar view and note it in an ADR) that renders a COG layer from TiTiler with a slope colormap, and layer toggles. Generate the API client from the OpenAPI contract.
**Done when:** you can log in as an Analyst, open the map, and see the slope layer. Playwright smoke test and an accessibility check pass. No tokens in localStorage.

## Phase 1 exit criteria
Ingestion with SSRF protections, DEM to COG with manifest, terrain outputs on the map, provenance records, golden and property tests passing, `docs/demos/phase-1.md` written.
