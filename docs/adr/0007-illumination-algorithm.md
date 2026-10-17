# ADR-0007: Illumination Algorithm: Horizon-Profile Precomputation with Curvature Correction

**Status:** Accepted
**Date:** 2026-10-18
**Context:**
The illumination service must compute sunlight and shadow across an AOI of 10 to 20 km at 20 m/pixel ($500 \times 500$ to $1000 \times 1000$ cells, $N \approx 2.5 \times 10^5$ to $10^6$ cells) across durations from one lunar day (708 hours) to one year (~8,760 hours) with sub-hourly time steps ($T \approx 1,000$ to $10,000$ steps).

Three candidate algorithms were evaluated:
1. **Per-time Ray Marching:** Cast rays from every cell toward the Sun at each time step.
   - *Complexity:* $O(T \cdot N \cdot \frac{R}{\Delta r})$. For $T=1,000, N=10^6, R=50\text{ km}, \Delta r=20\text{ m}$, operations $\approx 2.5 \times 10^{12}$. Computationally prohibitive for interactive scrubbing and rapid pipeline execution.
2. **Horizon-Profile Method (Amortized Precomputation):** For each cell, precompute the maximum terrain elevation angle $H(i, j, \phi_k)$ across $K$ discrete azimuth bins ($K \in [360, 720]$, $0.5^\circ$ to $1^\circ$ resolution).
   - *Complexity:* Precomputation: $O(N \cdot K \cdot \frac{R}{\Delta r})$ executed once per DEM version. Evaluation: $O(N)$ per time step via binary comparison $\text{el}_\odot(t) > H(i, j, \text{az}_\odot(t))$. For $T=1,000$, evaluation takes $< 50\text{ ms}$ per slice.
   - *Reusability:* The identical horizon profile is directly reused by `comms-service` for Earth line-of-sight visibility.
3. **Hybrid (Coarse Horizon + Fine Local Raytrace):** Precompute coarse horizons at 50 m and refine local raytraces at 20 m.
   - *Complexity:* Added implementation complexity with marginal performance gains over vectorized horizon lookup.

**Accuracy & Physical Constraints:**
- **Lunar Spherical Curvature:** Over ray reach $R=50\text{ km}$, drop due to lunar curvature ($R_M = 1737.4\text{ km}$) is $\Delta z = \frac{R^2}{2 R_M} \approx 719\text{ m}$. Neglecting curvature causes severe over-shadowing. The horizon kernel must apply $-s^2 / (2 R_M)$ curvature compensation at ray distance $s$.
- **DEM Padding Margin:** Distant high relief casts shadows into the AOI. With maximum regional relief $\Delta h = 2,000\text{ m}$ and minimum solar elevation $\text{el}_{\text{min}} = 1.5^\circ$, the required padding halo is $R_{\text{pad}} = \frac{\Delta h}{\tan(\text{el}_{\text{min}})} \approx 76\text{ km}$.
- **Finite Solar Disk:** The Sun subtends $\approx 0.53^\circ$ at 1 AU. The baseline evaluates center-of-disk point source; fractional penumbra is computed by evaluating 5 sample points across $[-\theta_{\odot}/2, +\theta_{\odot}/2]$.

**Decision:**
Adopt the **Horizon-Profile Precomputation Method** implemented in a shared library (`libs/selene-horizon`), accelerated via Numba parallel compilation (`nogil`, `parallel=True`), with spherical curvature correction.

**Consequences:**
- Precomputing horizons incurs an initial upfront cost ($O(N \cdot K)$), amortized across thousands of temporal evaluations.
- High-frequency temporal querying (scrubbing, time series) achieves sub-second latency.
- Horizon profiles can be persisted and cached per DEM hash.
