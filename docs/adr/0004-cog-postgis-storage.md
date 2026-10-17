# ADR-0004: Cloud-Optimized GeoTIFF on S3-compatible storage, PostGIS for vectors and metadata

**Status:** Accepted (time-stack format to be finalized in Phase 2; see Open)
**Context:** Rasters are large and read in windows (tiles, time slices). Metadata and vector geometry need transactional queries.
**Decision:**
- Rasters stored as **COG** (internal tiling, overviews, compression) in S3-compatible storage (MinIO locally). Content-addressed by SHA-256 recorded in a manifest.
- Vectors (AOIs, sites, routes) in **PostgreSQL with PostGIS**.
- Tile and window serving via **TiTiler** reading COGs directly.
- Time-stacked products: choose in Phase 2 between **one COG per time step** (simple, good for slices) and **Zarr** (efficient for per-pixel time series). Per-cell time series (for stats and the planner) favors Zarr or a derived compact index; per-time slices favor COG. A hybrid is acceptable (Zarr for analysis, COG for display).
**Consequences:** immutable rasters make caching and reproducibility straightforward; no raster DB to operate. The planner needs efficient time-series reads, which is why the Phase 2 ADR matters.
**Open:** time-stack format decision and benchmark (Phase 2).
