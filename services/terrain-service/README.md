# terrain-service

**Port:** 8103
**Tech:** FastAPI, NumPy, Pillow, Boto3, selene-geo
**Phase:** 1 (Task 1.4)

## Purpose
Derives high-precision lunar terrain safety products from Digital Elevation Models (DEMs):
- **Slope:** Horn 3x3 finite-difference elevation gradient in degrees ($0 \le \theta < 90^\circ$).
- **Aspect:** Gradient compass bearing clockwise from North ($0 \le \theta < 360^\circ$).
- **Roughness:** Terrain Ruggedness Index (TRI - Riley et al. 1999) measuring RMS elevation variation across 8 neighbors.
- **Rover Hazard Mask:** Binary traversability mask ($0 = \text{safe}, 1 = \text{hazard}$) evaluating slope and roughness thresholds with fail-closed no-data treatment.
- **Tiled Seam-Free Execution:** Leverages `selene_geo.tiling` with 1-pixel halos to ensure zero tile seam artifacts.
- **Cloud-Optimized GeoTIFF (COG) Output:** Emits tiled TIFFs with power-of-2 downsampled overview pyramids.

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/terrain-service/SPEC.md) for full endpoint and algorithm documentation.
See [DECISIONS.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/terrain-service/DECISIONS.md) for architectural decision records (ADR-0101 to ADR-0104).
See [perf-terrain.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/validation/perf-terrain.md) for benchmark performance telemetry ($> 5.5\text{ Mpix/s}$).

## Events
- **Publishes:** `selene.terrain.analysis.completed.v1`, `audit.event`
- **Endpoints:**
  - `GET /v1/products/{id}`: Product metadata, dimensions, CRS, and storage URI.
  - `GET /v1/products/{id}/stats`: Quantile summaries (p10, p25, p50, p75, p90) and hazard fraction.
  - `POST /internal/v1/terrain/analyze`: Synchronous analysis pipeline for Small AOIs.
  - `GET /healthz`, `GET /readyz`, `GET /metrics`: Service liveness, readiness, and Prometheus instrumentation.

## Local Development & Testing

### Running Tests
```bash
python -m pytest services/terrain-service/tests
```

### Type Checking & Linting
```bash
python -m ruff check services/terrain-service
python -m ruff format --check services/terrain-service
python -m mypy --strict services/terrain-service/src
```

### Running the Service
```bash
uvicorn terrain_service.main:app --host 0.0.0.0 --port 8103 --reload
```

## Security & Scientific Constraints
- **Lunar CRS & Units:** All distances and coordinates are in SI metres and degrees. Uses IAU 2015 lunar reference sphere (radius 1,737.4 km).
- **Fail-Closed Hazard Policy:** Incomplete, corrupted, or no-data cells propagate to the 3x3 filter neighborhood and are treated as traversability hazards (`1`).
- **Project Isolation:** Role-based access control enforces that only members of the product's project (or global `admin`/`auditor`) can retrieve product metadata and statistics.
