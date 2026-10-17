# provenance-service

**Port:** 8111
**Tech:** FastAPI, PostgreSQL, SQLAlchemy 2
**Phase:** 5

## Purpose
Maintains the complete, immutable directed acyclic graph (DAG) of data lineage, software/model versions, parameter sets, and checksums for all derived mission products (FR-03, FR-32, C-INT-3).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/provenance-service/SPEC.md) for lineage schemas and verification APIs.

## Events
- **Consumes:** `selene-*.completed`
- **Internal APIs:** `POST /internal/v1/artifacts`, `GET /v1/provenance/...`

## Local Development & Testing
```bash
pytest tests/
```
