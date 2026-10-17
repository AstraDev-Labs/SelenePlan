# illumination-service

**Port:** 8105
**Tech:** FastAPI, Numba JIT, SpiceyPy, Zarr v3, NumPy, Redis
**Phase:** 2 (Tasks 2.1 - 2.5)

## Purpose
Time-varying solar illumination modeling, shadow propagation, lit fraction, and continuous dark period statistics over lunar polar terrain (FR-14, FR-16).

## Key Architecture & Decisions
- **Horizon-Profile Precomputation (ADR-0007):** Evaluates terrain elevation horizons across 72–720 discrete azimuth bins in parallel using Numba (`nogil`, `parallel=True`), amortizing ray tracing over thousands of time steps.
- **Lunar Curvature Compensation:** Applies rigorous spherical geometry correction $-s^2 / (2 R_M)$ along ray distance $s$ ($R_M = 1,737,400\text{ m}$).
- **Hybrid Zarr + Slice Cache Storage (ADR-0008):** Stores multi-dimensional spatiotemporal cubes $(T, H, W)$ in chunked Zarr format for sub-millisecond point time-series queries, with an in-memory/Redis cache for instant 2D PNG/JSON time-slice retrieval.
- **NAIF SPICE Astronomy:** Real ephemerides using `de421.bsp`, `pck00010.tpc`, and `naif0012.tls` in the Moon body-fixed frame (`IAU_MOON`), converted to local topocentric East-North-Up (ENU) coordinates.

## Endpoints
- `GET /healthz`, `GET /readyz`, `GET /metrics`
- `GET /v1/products/{id}`: Metadata, parameters, bounds, and summary statistics.
- `GET /v1/products/{id}/slice?t=&format=`: Retrieve 2D spatial slice (JSON mask or rendered PNG).
- `GET /v1/products/{id}/timeseries?x=&y=&crs=`: 1D point illumination series across all time steps.
- `GET /v1/products/{id}/stats?geom=`: Aggregate statistics (mean lit fraction, max continuous dark hours, PSR area fraction).

## Testing
```bash
pytest services/illumination-service/tests/ -v
```
- **Golden tests:** Conical peak shadow length ($\arctan(H/D)$), flat plane ($0^\circ$), bowl crater rim angle, and end-to-end reproducibility.
- **Property tests:** `longest_dark_s` verified bit-for-bit against brute-force reference on random boolean cubes.
- **Convergence tests:** Verifies $< 5\%$ variation when halving time step and doubling azimuth bins.
