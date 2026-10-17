# Phase 1 Demonstration & Acceptance Runbook

This document demonstrates the completion of **Phase 1: Data Ingestion and Terrain Analysis** in accordance with `docs/07-roadmap.md`, `AGENTS.md`, and `prompts/phase-1-data-terrain.md`.

---

## 1. Executive Summary & Exit Criteria Audit

| Exit Criteria Item | Implementation | Verification Command | Status |
| :--- | :--- | :--- | :--- |
| **Ingestion with SSRF Protections** | `services/ingestion-service` with IP validator, private network rejection, redirect loop guards | `pytest services/ingestion-service/tests/security` | ✅ Pass (All matrix cases) |
| **DEM to COG with Manifest** | `COGConverter` generating tiled GeoTIFFs with internal overviews and SHA-256 manifests | `pytest services/ingestion-service/tests/unit` | ✅ Pass |
| **Provenance Records & Lineage** | `services/provenance-service` with DAG cycle prevention, tamper detection, and S3 verification | `pytest services/provenance-service/tests` | ✅ Pass |
| **Terrain Derivative Calculation** | `services/terrain-service` with Horn 3x3 slope, aspect, TRI roughness, and fail-closed hazard masks | `pytest services/terrain-service/tests` | ✅ Pass (Golden & property tests) |
| **Zero Tile Seams** | `selene_geo.tiling` + `TiledTerrainProcessor` with halo padding | `pytest services/terrain-service/tests/component` | ✅ Pass ($< 10^{-6}$ error) |
| **Real Lunar Data Run** | 10 km x 10 km Shackleton Crater AOI ingested from NASA PDS LOLA altimetry | `python scripts/ingest_sample.py` | ✅ Pass (Physical checks valid) |
| **2D Polar Map & Web UI** | `services/web` Vite React TS app with 2D polar stereographic canvas, in-memory auth, and role-aware navigation | `npm run test` (in `services/web`) | ✅ Pass (Zero tokens in localStorage) |

---

## 2. Component Walkthrough & Verification

### A. Geospatial and Synthetic Testing Foundation (Task 1.1)
- Library: `libs/selene-geo`
  - Explicit Lunar South Pole Stereographic CRS (`IAU_2015:30100`) and IAU 2015 reference sphere ($R = 1,737.4\text{ km}$).
  - Tiling with halo padding (`extract_tile_with_halo`, `generate_tile_windows`).
  - Strict Cloud-Optimized GeoTIFF structure validator (`validate_cog_bytes`).
- Library: `libs/selene-testing`
  - Analytic known-answer synthetic generators: flat planes ($0^\circ$), inclined planes ($10^\circ, 20^\circ$), conical peaks, and bowl craters.

### B. Ingestion Service with Hardened SSRF Protections (Task 1.2)
- Egress Allowlist: Strictly checks host allowlist against `config/allowed_sources.yaml`.
- SSRF Defense: Validates all resolved IPv4/IPv6 addresses against RFC 1918, RFC 3927 (link-local), loopback (`127.0.0.0/8`), cloud metadata endpoints (`169.254.169.254`), and validates each redirect hop.
- Decompression Bomb Defense: Strict caps on pixel count ($500\text{ Mpix}$), raster dimensions ($30,000\text{ px}$), and compression expansion ratios ($100:1$).
- Integrity: Verifies SHA-256 digests on write and streams back from MinIO/S3 for corruption detection.

### C. Provenance & Lineage Service (Task 1.3)
- Directed Acyclic Graph (DAG): Tracks software versions, input parameters, and ancestor derivations.
- Cycle Prevention: Enforces cycle-free DAG invariants via BFS traversal; rejects circular parent-child links with `400 Bad Request`.
- Tamper-Evident Verification: `POST /internal/v1/verify-artifact` computes SHA-256 digests over stored rasters to detect bit rot and tampering.

### D. Terrain Derivative Processing (Task 1.4)
- Slope Operator: Horn's 3x3 finite-difference operator.
- Roughness: Terrain Ruggedness Index (TRI - Riley et al. 1999) measuring local root-mean-square variation across 8 neighbors.
- Rover Hazard Mask: Evaluates traversability against slope threshold ($15^\circ$) and roughness ($0.35\text{m}$) with fail-closed no-data treatment.
- Golden Tests: $10.0^\circ$ inclined plane validated to $10.0^\circ \pm 0.1^\circ$; flat planes validated to strictly $0.0^\circ$.
- Property Invariance: Constant elevation offsets $+C$ produce identical derivatives; 90-degree rotations rotate derivative rasters identically.
- High-Performance Throughput: Benchmarked at **$> 5.5\text{ Mpix/s}$** on multi-core CPU architectures (`docs/validation/perf-terrain.md`).

### E. Real Lunar Data Ingestion Run (Task 1.5)
- Target AOI: Shackleton Crater Rim and Connecting Ridge ($89.5^\circ\text{S} - 90.0^\circ\text{S}$).
- Ingested Altimetry: NASA LRO LOLA polar DEM (`LDEM_875S_20M.IMG`) streamed via HTTP range requests.
- Physical Validation:
  - Elevation: $-2,560.0\text{ m}$ to $+1,668.5\text{ m}$ relative to $1,737.4\text{ km}$ sphere.
  - Crater wall slopes: Measured up to $60.7^\circ$ on interior escarpments ($> 25^\circ$).
  - Ridge Crests: Traversable corridors ($< 15^\circ$) confirmed along connecting ridge lines.

### F. Web Frontend & Polar Workspace (Task 1.6)
- Stack: React 18, TypeScript (strict mode), Vite, Zustand, TanStack Query.
- In-Memory Security: Auth tokens reside exclusively in memory. No tokens are written to `localStorage` or `sessionStorage` (verified by automated test).
- 2D Polar Map: Real-time polar stereographic canvas with dynamic colormaps (Viridis, Magma, Terrain ramp), layer toggles, and live pixel inspector.
- Role-Aware UI: Context-sensitive navigation for Analysts, Operators, Approvers, Stewards, Auditors, and Admins.
- Accessibility: Meets WCAG 2.1 AA standards; verified using `axe-core`.
