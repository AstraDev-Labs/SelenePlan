# ADR-0003: Python 3.12, FastAPI, Numba; Rust only if profiling demands

**Status:** Accepted
**Context:** The domain is raster and geospatial heavy (GDAL, Rasterio, NumPy, SpiceyPy, PyTorch, OR-Tools), all strong in Python. The developer is productive in Python and AI agents generate it reliably. Hot loops (horizon computation, graph search) need speed.
**Decision:**
- Services in Python 3.12 with FastAPI and Pydantic v2. Typed (`mypy --strict` for new code).
- Hot loops in NumPy vectorization first, then Numba. Profile before optimizing.
- If a kernel cannot meet NFR-03 after Numba and tiling, port **only that kernel** to Rust (PyO3) behind the same Python interface, via a new ADR.
- Frontend: TypeScript, React, Vite, CesiumJS.
**Consequences:**
- (+) Fast development, rich geospatial ecosystem.
- (-) GIL and memory overhead. Mitigation: process-level parallelism (multiple worker replicas), tiling, Numba `nogil`.
**Alternatives:** Go for services (fewer geo libs), Rust everywhere (slower to build), Java/Spring (heavier).
