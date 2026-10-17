# comms-service

**Port:** 8106
**Tech:** FastAPI, Numba JIT, SpiceyPy, Zarr, NumPy
**Phase:** 3 (Tasks 3.1 - 3.5)

## Purpose
Direct-to-Earth communication line-of-sight analysis and lunar libration modeling (FR-15).

## Key Features & Architecture
- **Shared Horizon Engine (`libs/selene-horizon`):** Reuses the shared multi-core Numba ray-tracing kernel with spherical curvature correction ($-s^2 / (2 R_M)$).
- **Libration-Aware Earth Geometry:** Direct SPICE ephemerides (`de421.bsp`, `pck00010.tpc`, `naif0012.tls`) calculate Earth's apparent position and distance (~375,000 km) in Moon-fixed coordinates (`IAU_MOON`), converted to local topocentric East-North-Up angles.
- **Window Extraction Engine:** Detects and extracts contiguous communication intervals with edge-case handling (start/end open, isolated windows, continuous coverage) and computes longest blackout durations.
- **Path LOS Evaluation (`POST /v1/products/{id}/along-path`):** Evaluates line-of-sight communication connectivity for time-stamped waypoint sequences along candidate traverse routes.

## Endpoints
- `GET /healthz`, `GET /readyz`, `GET /metrics`
- `GET /v1/products/{id}`: Metadata, bounding box, resolution, parameters, and blackout summary stats.
- `GET /v1/products/{id}/slice?t=`: 2D spatial visibility mask slice at time step `t`.
- `GET /v1/products/{id}/windows?x=&y=&crs=`: List of line-of-sight communication windows for a point.
- `POST /v1/products/{id}/along-path`: Dynamic visibility lookup along time-stamped waypoints.
- `GET /v1/products/{id}/stats?geom=`: Summary metrics (mean visible fraction, max blackout hours).

## Testing
```bash
pytest services/comms-service/tests/ -v
```
- **Golden tests:** Flat plane ($0^\circ$), analytic 300m ridge occultation, libration bounds and known-answer comparison with SPICE, along-path query evaluation.
- **Property tests:** Window extraction verified against independent brute-force contiguous span finder on random binary series.
- **Component tests:** Full REST API coverage and authz negative tests.
