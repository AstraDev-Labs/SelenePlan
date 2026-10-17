# SPEC: provenance-service

**Port:** 8111 | **Tech:** FastAPI, PostgreSQL, S3 client | **Phase:** 1 (MVP), 4 (models), 5 (replay)

## Purpose
Record and verify **where every artifact came from**: checksums, signed manifests, and lineage edges from inputs to outputs (FR-03, SEC-06, T6, T7).

## Responsibilities
1. **Artifact registry:** register artifacts (datasets, products, models, SPICE kernel sets, plans, reports) with URI, SHA-256, size, and producing service.
2. **Lineage graph:** edges `child ← parent` with relation and parameter hash. Query ancestors and descendants (bounded depth).
3. **Manifests:** store a manifest per artifact; sign manifests for datasets and models (Vault Transit key `selene-manifest-signing`, separate from plan signing).
4. **Verification:** `POST /internal/v1/verify-artifact` reads the object from storage (or accepts a hash) and compares with the registry. Services call this before using datasets and models.
5. **Replay support:** `GET /v1/lineage/{artifact_id}/replay-spec` returns the full recipe (inputs with hashes, parameters, code versions, model versions, SPICE kernels) used by the replay tool.
6. **Consume events** (`*.completed`, `dataset.registered`, `plan.completed`) to register artifacts and edges automatically.

## API
| Method and path | Purpose |
|---|---|
| `GET /v1/artifacts/{id}` | Metadata |
| `GET /v1/lineage/{id}?direction=up|down&depth=` | Lineage graph |
| `GET /v1/lineage/{id}/replay-spec` | Recipe for replay |
| `POST /internal/v1/artifacts` | Register (service-to-service) |
| `POST /internal/v1/verify-artifact` | Verify artifact hash and manifest signature |

## Security
Service identity required for internal endpoints. Read access for lineage restricted by project. Manifest signing key isolated from plan signing key. Registry rows insert-only for existing hashes (a different hash for the same artifact ID is an alert).

## Acceptance criteria
1. Registering an artifact and then corrupting the object makes `verify-artifact` fail.
2. Lineage query returns correct ancestors for a synthetic pipeline (dataset → terrain → hazard → plan).
3. Unsigned or tampered model manifest is reported as invalid (used by hazard-ml-service).
4. `replay-spec` contains all inputs, parameters, code versions, and kernel checksums needed; the replay tool reproduces a small plan within tolerance (Phase 5).
5. Cycle detection prevents lineage cycles.
6. Cross-project access to lineage is denied.

## Folder layout
```
services/provenance-service/
  src/provenance_service/{api,registry,lineage,manifest,verify,consumer,db}/
  tests/{unit,component,security}/
tools/replay/                 # CLI that consumes replay-spec (Phase 5)
```
