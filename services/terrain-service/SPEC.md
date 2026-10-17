# SPEC: terrain-service

**Port:** 8103 | **Tech:** FastAPI, worker, NumPy, Numba, Rasterio | **Phase:** 1

## Purpose
Derive terrain products from a DEM: slope, aspect, roughness, and a terrain-only hazard mask using rover-profile thresholds.

## Responsibilities
- Compute slope and aspect with a documented operator (default Horn 3x3; record choice in `DECISIONS.md`). Account for projection scale if the AOI is large (see `docs/08-science-notes.md` section 3).
- Compute roughness (documented measure) over a configurable window.
- Optional resampling to a planning resolution with documented interpolation (bilinear for elevation).
- Produce a **terrain hazard mask** from thresholds in the rover profile: `slope_deg > max_slope_deg` or `roughness > max_roughness`; unknown/no-data = hazardous (configurable).
- Write COG outputs, record lineage, emit completion events.
- Tile large AOIs with overlap (halo) so edge effects do not appear at tile seams.

## Non-goals
ML detection, illumination, planning.

## API
| Method and path | Purpose |
|---|---|
| `GET /v1/products/{id}` | Product metadata (kind, params, lineage refs, URIs) |
| `GET /v1/products/{id}/stats` | Summary (min, max, mean, percentiles, hazard area fraction) |
| `POST /internal/v1/terrain/analyze` | Synchronous small-AOI analysis for tests and previews (disabled in prod if abused) |

## Events
Consumes `terrain.analysis.requested`. Produces `terrain.analysis.completed` (`product_ids`, `storage_uris`, `sha256s`, `metrics`), `audit.event`.

## Inputs and parameters
DEM dataset version (verified by SHA-256 before use), AOI polygon, output resolution, slope operator, roughness window, thresholds (from request, copied from the rover profile at request time and recorded in `params`).

## Acceptance criteria
1. Inclined plane at 10 degrees gives 10 degrees within 0.1 on interior cells; flat plane gives 0 (golden tests).
2. Adding a constant to the DEM does not change slope (property test).
3. Rotating the DEM 90 degrees rotates slope and hazard maps accordingly (property test).
4. No visible seams across tile boundaries on a synthetic surface (tile vs full-raster comparison within tolerance).
5. No-data propagates; a no-data cell is never reported as 0 degrees.
6. Output COGs validate; manifest and lineage recorded; completion event emitted with correct hashes.
7. Throughput benchmark recorded in `docs/validation/perf-terrain.md` (pixels per second per core).

## Folder layout
```
services/terrain-service/
  src/terrain_service/{api,worker,algorithms,io,events}/
  tests/{unit,property,component}/
```
