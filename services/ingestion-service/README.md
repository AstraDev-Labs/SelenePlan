# ingestion-service

**Port:** 8102
**Tech:** FastAPI + worker, GDAL, Rasterio
**Phase:** 1

## Purpose
Egress-controlled dataset registration and ingestion, converting lunar DEMs and imagery into Cloud-Optimized GeoTIFFs (COGs) with immutable manifests and provenance tracking (FR-01, FR-02, SEC-08).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/ingestion-service/SPEC.md) for host allowlists, SSRF protections, and raster processing constraints.

## Events
- **Consumes:** `selene-dataset-ingest-requested`
- **Produces:** `selene-dataset-registered`, `selene-dataset-ingest-failed`

## Local Development & Testing
```bash
pytest tests/
```
