# SPEC: comms-service

**Port:** 8106 | **Tech:** FastAPI, worker, SpiceyPy, NumPy, Numba, Rasterio | **Phase:** 3

## Purpose
Compute **direct-to-Earth line-of-sight** visibility over an AOI and time period, accounting for terrain horizon and lunar libration.

## Responsibilities
1. Earth direction over time in the Moon-fixed frame from SPICE; convert to local azimuth and elevation per cell.
2. Terrain horizon check: Earth is visible if its elevation exceeds the horizon angle in the Earth azimuth. **Reuse the horizon-profile code** from illumination via a shared library (`libs/selene-horizon`) rather than duplicating it.
3. Per-time visibility mask stack; statistics: visible fraction, longest blackout, number of windows, window list for a point or route.
4. Route/window query: given a time-stamped path (waypoints), return visibility along it (used by planner and reports).
5. Storage and serving mirror illumination (same format decision).

## Non-goals
Link budget, antenna pattern, relay satellites, Doppler (document as v1 limitations).

## API
| Method and path | Purpose |
|---|---|
| `GET /v1/products/{id}` | Metadata |
| `GET /v1/products/{id}/slice?t=` | Visibility slice |
| `GET /v1/products/{id}/windows?x=&y=&crs=` | Visibility windows for a point |
| `POST /v1/products/{id}/along-path` | Visibility along time-stamped waypoints (body validated, size limited) |
| `GET /v1/products/{id}/stats?geom=` | Visible fraction, longest blackout |

## Events
Consumes `comms.analysis.requested`. Produces `comms.analysis.completed`, `audit.event`.

## Acceptance criteria
1. Flat plane: visible if and only if Earth elevation is above 0 (golden test).
2. Ridge test: blocked when Earth elevation is below the analytic ridge angle, visible above (golden test).
3. Window extraction merges adjacent visible steps correctly and handles edge cases (start visible, end visible, single-step windows). Property test against a brute-force reference.
4. Libration check: Earth direction series is compared against an independent SPICE computation for a few timestamps (known-answer tolerance documented).
5. Shared horizon library has a single implementation with tests used by both services.
6. SPICE kernels used are listed with checksums in the product `params`.

## Folder layout
```
services/comms-service/
  src/comms_service/{api,worker,earth,windows,storage,events}/
  tests/{unit,property,golden,component}/
```
