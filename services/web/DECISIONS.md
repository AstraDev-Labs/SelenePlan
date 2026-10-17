# Architecture Decision Records: Web Frontend

## ADR-0201: 2D Polar Map Visualization Engine

### Status
Accepted

### Context
Lunar mission planning at the South Pole ($80^\circ\text{S} - 90^\circ\text{S}$) requires rendering high-resolution raster layers (slope, aspect, roughness, hazard, illumination) in a polar stereographic projection (`IAU_2015:30100`). Standard Earth web mapping libraries (e.g. Leaflet) assume Web Mercator (EPSG:3857), which causes infinite distortion at the poles.

We evaluated two candidate frameworks:
1. **MapLibre GL JS**: Mature 2D vector and raster tile renderer. Supports custom projections, raster tile sources from TiTiler (`/cog/tiles/{z}/{x}/{y}`), and raster color ramps.
2. **deck.gl**: WebGL2/WebGPU layer engine. Excellent for non-geospatial flat Cartesian coordinate grids ($x, y$ in metres) and custom shader blending.

### Decision
We select **MapLibre GL / Canvas Polar Engine** as the primary 2D polar mapping foundation, with TiTiler raster tile endpoints and colormap styling (e.g., magma/viridis for slope, discrete categorical styling for hazard masks).

### Consequences
- True-to-scale meters coordinates near the lunar south pole without equatorial mercator stretching.
- Seamless tile streaming from Cloud-Optimized GeoTIFFs via TiTiler microservice.
- 3D lunar globe visualization will be lazy-loaded via CesiumJS with an explicit Moon ellipsoid (radius 1,737.4 km).

---

## ADR-0202: In-Memory Token Storage (No localStorage)

### Status
Accepted

### Context
`AGENTS.md` and `services/web/SPEC.md` mandate:
"No tokens in localStorage. Tokens in memory; silent refresh."
Storing JWTs in `localStorage` or `sessionStorage` exposes tokens to cross-site scripting (XSS) exfiltration.

### Decision
Store access and ID tokens exclusively in JavaScript in-memory state (Zustand state store). Refresh tokens are managed via HttpOnly, SameSite=Strict cookies or silent iframe refresh against Keycloak. Any attempt to write tokens to `localStorage` is blocked and checked by automated tests.

### Consequences
- Hardened protection against XSS token exfiltration.
- Page reloads trigger silent re-authentication without user credentials exposure.
