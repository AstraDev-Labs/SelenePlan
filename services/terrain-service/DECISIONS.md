# Architectural & Algorithmic Decisions: terrain-service

## ADR-0101: Slope and Aspect Operator Selection
- **Status:** Accepted
- **Context:** Calculating lunar surface slope and aspect from digital elevation models (DEMs) requires an operator that balances numerical precision, noise resistance, and rotation invariance.
- **Decision:** Implement Horn's 3x3 weighted finite-difference gradient operator:
  $$\frac{\partial z}{\partial x} = \frac{(z_{13} + 2z_{23} + z_{33}) - (z_{11} + 2z_{21} + z_{31})}{8 \cdot \Delta x}$$
  $$\frac{\partial z}{\partial y} = \frac{(z_{31} + 2z_{32} + z_{33}) - (z_{11} + 2z_{12} + z_{13})}{8 \cdot \Delta y}$$
  $$\theta_{\text{slope}} = \arctan\left(\sqrt{\left(\frac{\partial z}{\partial x}\right)^2 + \left(\frac{\partial z}{\partial y}\right)^2}\right)$$
- **Rationale:** Horn's method applies higher weight to orthogonal neighbors than diagonal neighbors, reducing directional bias and suppressing grid noise commonly found in laser altimetry (LOLA) DEMs.
- **Scale Adjustment:** For polar stereographic coordinates, $\Delta x$ and $\Delta y$ are evaluated in metres.

## ADR-0102: Surface Roughness Metric Definition
- **Status:** Accepted
- **Context:** Rover trafficability depends not just on regional slope but also on sub-grid micro-relief and surface roughness.
- **Decision:** Implement Riley et al. (1999) Terrain Ruggedness Index (TRI) over a $3 \times 3$ moving window:
  $$\text{TRI} = \sqrt{\frac{1}{8} \sum_{i \ne \text{center}} (z_i - z_{\text{center}})^2}$$
- **Rationale:** TRI measures absolute root-mean-square elevation difference between adjacent cells, directly representing surface irregularity and obstacle height relative to rover wheel clearance.

## ADR-0103: No-Data Masking and Trafficability Policy
- **Status:** Accepted
- **Context:** Dem tiles may contain missing data, shadow voids, or border no-data cells.
- **Decision:**
  1. No-data cells are never coerced to 0 elevation or 0 slope.
  2. Any 3x3 calculation window containing a no-data neighbor propagates no-data to the output derivative.
  3. In terrain hazard evaluation, no-data cells are treated as **hazardous** (`hazard = 1`) by default (`nodata_is_hazard = True`) to fail-closed against unverified terrain.

## ADR-0104: Tiled Processing with Halos
- **Status:** Accepted
- **Context:** Large AOIs exceed memory limits if processed as single monolithic arrays. Direct tiling causes boundary artifacts.
- **Decision:** Use `selene_geo.tiling` with a configurable halo (minimum 1 cell for 3x3 kernels). The halo provides the necessary neighborhood context for edge pixels, and only the interior valid tile is written to the destination raster, eliminating tile seams.
