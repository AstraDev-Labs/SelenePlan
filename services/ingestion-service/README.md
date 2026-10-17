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

### Running Tests
Run unit, security, and component tests:
```bash
python -m pytest services/ingestion-service/tests
```

### Type Checking & Linting
```bash
python -m ruff check services/ingestion-service
python -m ruff format --check services/ingestion-service
python -m mypy --strict services/ingestion-service/src
```

### Running the Service
```bash
uvicorn ingestion_service.main:app --host 0.0.0.0 --port 8102 --reload
```

## Security & Architectural Constraints
- **SSRF Protection:** Resolves hostnames and verifies that every resolved IP does not belong to private networks (RFC 1918), loopback, link-local, carrier-grade NAT, or cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`). Checks are repeated on every HTTP redirect hop. Rejections emit `audit.event`.
- **Egress Allowlist:** Only sources defined in `config/allowed_sources.yaml` with valid HTTPS URLs and registered path prefixes can be ingested.
- **Decompression Bomb Guard:** Enforces width/height <= 30,000, total pixels <= 500,000,000, and a maximum uncompressed-to-compressed ratio cap of 100:1.
- **Transactional Rollback:** All metadata operations on PostgreSQL (`ingestion` schema) are transactional. Failures roll back versions cleanly without orphan artifacts.
- **Integrity:** MinIO object uploads verify SHA-256 digests; read-back verifies manifest digests and raises `DataCorruptionError` if objects are tampered with.
