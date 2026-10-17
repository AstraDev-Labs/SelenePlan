# Illumination Service Decisions

## ADR Summary

### ADR-0007: Horizon-Profile Precomputation with Curvature Correction
- **Decision:** Horizon-Profile method with 360-720 azimuth bins.
- **Rationale:** Amortizes ray-tracing across $T$ time steps; identical horizon profile re-used for Earth visibility in `comms-service`; applies $-s^2 / (2 R_M)$ spherical curvature correction.

### ADR-0008: Hybrid Zarr + COG Storage
- **Decision:** Chunked Zarr for primary analytical cube $(T, 32, 32)$ and point time-series queries; Redis-cached slices and COG export for TiTiler visual tiles.
- **Rationale:** Satisfies both sub-millisecond planner time-series queries and low-latency map timeline scrubbing.
