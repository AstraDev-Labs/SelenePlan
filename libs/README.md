# Shared libraries

Services may import only from `libs/`, never from another service (ADR-0001). Libraries are installed in editable mode in each service's dev environment and versioned with the repo.

| Library | Purpose | Created in |
|---|---|---|
| `selene-auth` | JWT validation (JWKS cache, algorithm pinning, issuer/audience checks), RBAC decorators, project-membership helpers, OPA client | Phase 0 |
| `selene-events` | Event envelope models and JSON Schema validation, Kafka producer with outbox helper, idempotent consumer base class, DLQ handling | Phase 0 |
| `selene-observability` | OpenTelemetry setup, JSON structured logging with `trace_id`, Prometheus metrics, health endpoints, log scrubbing | Phase 0 |
| `selene-geo` | Lunar CRS helpers, raster window/tiling helpers, COG utilities, units and constants (Moon radius, etc.) | Phase 1 |
| `selene-horizon` | Horizon-profile computation shared by illumination and comms | Phase 2 |
| `selene-testing` | Synthetic terrain generators (planes, cones, craters, ridges) with analytic answers, fixtures, Testcontainers helpers | Phase 1 |

Each library has its own `pyproject.toml`, `README.md`, tests, and semantic version.
