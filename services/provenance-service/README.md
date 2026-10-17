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

### Running Tests
```bash
python -m pytest services/provenance-service/tests
```

### Type Checking & Linting
```bash
python -m ruff check services/provenance-service
python -m ruff format --check services/provenance-service
python -m mypy --strict services/provenance-service/src
```

### Running the Service
```bash
uvicorn provenance_service.main:app --host 0.0.0.0 --port 8111 --reload
```

## Security & Architecture Constraints
- **Immutability & Integrity:** Artifact records are strictly insert-only for existing hashes. Attempting to register an existing artifact ID with a conflicting SHA-256 raises `409 Conflict` and triggers an audit alert.
- **Lineage Cycle Detection:** Enforces strict directed acyclic graph (DAG) invariants. Any edge insertion that would form a direct self-loop or transitive cycle is rejected with `400 Bad Request`.
- **Project Isolation:** Access to artifact metadata, lineage DAGs, and replay specifications is restricted to members of the artifact's owning project (unless the caller holds the `auditor` or `admin` role).
- **Corrupted Object Detection:** `POST /internal/v1/verify-artifact` streams objects from S3 storage, re-computes the SHA-256 digest, and flags bit rot or tampering with `valid=False`.
- **Automatic Event Lineage:** Kafka consumer processes `selene-dataset-registered` and `selene-terrain-analysis-completed` to register artifacts and link parent-child derivations automatically.
