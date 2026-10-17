# SPEC: illumination-service

**Port:** 8105 | **Tech:** FastAPI, worker, NumPy, Numba, SpiceyPy, Rasterio, Zarr (decided by ADR in Phase 2) | **Phase:** 2

## Purpose
Compute time-varying sunlight and shadow over an AOI and serve slices and statistics. This is the scientific core; correctness and performance matter most.

## Responsibilities
1. **Sun geometry:** use SPICE (kernels registered in provenance, checksums verified) to get Sun direction in the Moon-fixed frame over the requested period. Convert to local azimuth and elevation for each cell (account for the local vertical).
2. **Illumination computation:** produce for each time step a lit mask (and optional visible-solar-disk fraction). Algorithm chosen by ADR (horizon-profile recommended as the first candidate; see `docs/08-science-notes.md` section 4).
3. **Derived statistics:** lit fraction over period, longest continuous dark interval, longest continuous lit interval, permanently shadowed mask, number of sunrise/sunset transitions.
4. **Storage:** time stack in the format selected by the Phase 2 ADR (banded COG per time step and/or Zarr).
5. **Serving:** time slice endpoint, per-point time series endpoint, region statistics endpoint. Tiles via TiTiler for display.
6. **Padding:** pad the DEM beyond the AOI by the computed margin so distant terrain can cast shadows.

## Non-goals
Thermal modeling, penumbra in v1 (design hook only), scattered light.

## API
| Method and path | Purpose |
|---|---|
| `GET /v1/products/{id}` | Metadata (time axis, params, lineage) |
| `GET /v1/products/{id}/slice?t=` | Slice reference (tile template and COG window) |
| `GET /v1/products/{id}/timeseries?x=&y=&crs=` | Lit/dark series for a point |
| `GET /v1/products/{id}/stats?geom=` | Lit fraction, longest dark, longest lit for a region |

## Events
Consumes `illumination.analysis.requested`. Produces `illumination.analysis.completed` (`product_id`, `time_axis`, `stats_summary`), `audit.event`.

## Parameters (recorded for reproducibility)
`dem_dataset_version_id` (+sha256), `aoi`, `period_start/end`, `time_step_s`, `azimuth_bins`, `max_ray_distance_m`, `sun_model` (point | disk with samples), `spice_kernels` (names + sha256), `algorithm` and version, `resolution_m`.

## Performance plan
Target NFR-03. Steps: vectorize, then Numba with `nogil` and parallel tiles; choose horizon-profile to amortize over time; cache horizon profiles per DEM version and AOI; process in tiles with halos; record benchmarks per resolution in `docs/validation/perf-illumination.md`. If the target is missed, open an ADR for kernel changes (including Rust).

## Acceptance criteria
1. Flat plane with Sun above horizon: lit everywhere. Below: dark everywhere.
2. Conical mountain test: shadow length equals height divided by tan(elevation) within pixel tolerance.
3. Bowl crater test: floor is dark when Sun elevation is below the analytic rim angle; transition time matches analytic expectation within one time step.
4. **Convergence:** halving time step and doubling azimuth bins changes lit fraction by less than a documented tolerance on a test AOI.
5. Reproducibility: same inputs and parameters give identical outputs (or within documented tolerance) across two runs.
6. `stats` longest-dark computation matches a brute-force reference on random small cases (property test).
7. Validation note comparing one real polar location against published data exists in `docs/validation/`.
8. Performance baseline recorded and compared against NFR-03.

## Folder layout
```
services/illumination-service/
  src/illumination_service/{api,worker,sun,horizon,raytrace,stats,storage,events}/
  tests/{unit,property,golden,component}/
  bench/
```
