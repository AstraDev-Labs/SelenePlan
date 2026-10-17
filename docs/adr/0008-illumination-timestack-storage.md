# ADR-0008: Illumination Time-Stack Storage: Hybrid Zarr and COG Architecture

**Status:** Accepted
**Date:** 2026-10-18
**Context:**
The illumination service generates 3D spatiotemporal datasets $(T \times H \times W)$. Two primary access patterns exist:
1. **Time-Slice Reads (Map Visualization):** Retrieve 2D spatial slice $(H \times W)$ at a given time index $t$. High concurrency during interactive timeline scrubbing.
2. **Point Time-Series Reads (Rover Planning & Analytics):** Retrieve 1D illumination series $(T)$ at a specific coordinate $(x, y)$. Essential for A* traverse charging and battery budget evaluation.

Three storage formats were evaluated:
1. **Banded COG per Time Step:**
   - *Pros:* Native TiTiler compatibility, straightforward HTTP Range slice streaming.
   - *Cons:* Per-cell time-series queries require $T$ distinct file openings. For $T=1,000$, latency exceeds several seconds.
2. **Pure Zarr Array:**
   - *Pros:* Native n-dimensional chunking (e.g. chunks of $(T, 32, 32)$ or $(128, 64, 64)$). Point time-series query requires fetching only 1 chunk ($< 5\text{ ms}$). Blosc/zstd compression achieves high ratio on binary/byte lit masks.
   - *Cons:* TiTiler tile rendering requires dynamic slice slicing through an adapter or in-memory COG export.
3. **Hybrid Architecture:**
   - **Primary Analysis Store:** Multi-dimensional Zarr array persisted to S3/MinIO chunked along $(T, 32, 32)$, holding full temporal history and derived statistical bands.
   - **Visualization & Slice Serving:** On-demand slice generation with Redis caching and multi-band COG export for TiTiler polar map tile overlays.

**Decision:**
Implement the **Hybrid Architecture**:
- Store master illumination cubes in **Zarr** (format v2/v3) with chunk layout $(T, 32, 32)$ optimized for sub-millisecond point time-series reads by the rover planner.
- Serve interactive time slices via cached slice buffers, generating COG overlays on demand or pre-rendering key summary layers (lit fraction, permanently shadowed regions PSR, longest dark hours).

**Consequences:**
- Sub-5ms response time for point time-series queries (`/v1/products/{id}/timeseries`).
- Sub-50ms response time for cached time slices (`/v1/products/{id}/slice`).
- Efficient cloud storage footprint via bit-packing and Blosc zstd compression.
