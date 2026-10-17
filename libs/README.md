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

Each library has its own `pyproject.toml`, `README.md`, `requirements-lock.txt`, tests, and semantic version.

## Python Runtime & Dependency Management
- **Runtime:** Python 3.12 strictly.
- **Lockfiles:** Each library maintains a `requirements-lock.txt` pinning exact tested versions of its dependencies and transitive sub-dependencies.
- **Installation in Local Dev:**
  ```bash
  pip install -e libs/selene-events
  pip install -e libs/selene-observability
  pip install -e libs/selene-auth
  ```

## Installing `libs/` in Service Docker Builds

In accordance with ADR-0001, services must not depend directly on other services, but share common infrastructure via `libs/`.

When building service Docker images, the Docker build context should be the monorepo root:
```bash
docker build -f services/<service-name>/Dockerfile -t selene/<service-name>:latest .
```

Within each service's `Dockerfile`, copy `libs/` and install them into the container's Python environment before copying the service source code:

```dockerfile
# Multi-stage build example for services
FROM python:3.12-slim AS builder

WORKDIR /app

# 1. Copy shared libraries
COPY libs/ /libs/

# 2. Install shared libraries (pip compiles wheels / handles dependencies)
RUN pip install --no-cache-dir \
    /libs/selene-events \
    /libs/selene-observability \
    /libs/selene-auth

# 3. Copy and install service dependencies
COPY services/<service-name>/pyproject.toml .
RUN pip install --no-cache-dir .

# 4. Copy service source code
COPY services/<service-name>/src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```
