# Architectural & Science Decisions: planner-service

**Phase:** 5
**Service:** `planner-service`
**Status:** Approved

---

## 1. Energy Model Assumptions (Task 5.1)

### 1.1 Solar Power Generation
- **Solar Constant at 1 AU ($S_0$):** $1361.0\text{ W/m}^2$ (standard IAU/WMO solar irradiance at mean Earth-Moon distance).
- **Photovoltaic Conversion:**
  $$P_{\text{solar}} = A_{\text{panel}} \cdot \eta_{\text{panel}} \cdot S_0 \cdot \max(0, \sin(\theta_{\text{sun\_elev}}))$$
  Where:
  - $A_{\text{panel}}$: Effective solar array area (default $1.2\text{ m}^2$, configurable in rover profile).
  - $\eta_{\text{panel}}$: Solar cell efficiency under cryogenic lunar temperatures (default $0.28$ or $28\%$, triple-junction GaAs cells).
  - $\theta_{\text{sun\_elev}}$: Solar elevation angle above horizontal. If the sun is below the local horizon ($\theta_{\text{sun\_elev}} \le 0$) or the cell is shadowed by terrain, $P_{\text{solar}} = 0\text{ W}$.
  - Incidence on tilted terrain: Optional cosine-corrected projection when local slope and aspect vectors are enabled. Default operates with horizontal array projection.

### 1.2 Power Consumption by Operational Mode
- **Drive Mode ($P_{\text{drive}}$):** Active motor locomotion and autonomous terrain sensing: $80.0\text{ W}$ nominal (scales linearly with uphill slope: $+1.5\text{ W/deg}$).
- **Wait / Charging Mode ($P_{\text{wait}}$):** Stationary charging while sunlit: $15.0\text{ W}$ (housekeeping avionics and thermal survival).
- **Idle / Sleep Mode ($P_{\text{idle}}$):** Stationary during shadow/darkness: $12.0\text{ W}$ (deep low-power survival mode).
- **Comms Transmission Mode ($P_{\text{comms}}$):** Active direct-to-Earth X-band high-gain downlink: $+25.0\text{ W}$ adder.

### 1.3 Battery Dynamics & Survival Constraint
- **Capacity ($E_{\text{cap}}$):** Nominal rover battery capacity (default $500.0\text{ Wh}$).
- **Survival Minimum ($E_{\text{min}}$):** Minimum allowable State of Charge (SoC) for survival (default $100.0\text{ Wh}$, $20\%$ reserve). Any traverse candidate dropping below $E_{\text{min}}$ is strictly infeasible and rejected with an explicit explanation.
- **State Transition:**
  $$\Delta E = (P_{\text{in}} - P_{\text{out}}) \cdot \Delta t$$
  $$E(t + \Delta t) = \min(E_{\text{cap}}, \max(0, E(t) + \Delta E))$$

---

## 2. Planning Grid Resolution & Resampling
- Planning resolution is configurable (default $20\text{ m}$ to $40\text{ m}$ per cell).
- Resampling of hazard rasters uses **conservative max-pooling**: if any fine-grid sub-pixel within the planning cell is hazardous, the entire cell is marked hazardous.
- Graph search uses an **8-connected grid** with diagonal distance cost $\sqrt{2} \Delta x$.

---

## 3. Determinism and Tie-Breaking
- All sorting, priority queues, and A* evaluations apply strict deterministic tie-breaking based on lexically sorted cell coordinates $(x, y, t)$.
- Seeded pseudo-randomness only; no non-deterministic hash iteration.
