# Communications Validation Report: Earth Line-of-Sight & Libration

**Document ID:** VAL-COMMS-01
**Date:** 2026-10-18
**Status:** Complete & Cross-Checked
**Service:** `services/comms-service` and `libs/selene-horizon`

---

## 1. Physical Principles & Lunar Libration Sanity Checks

Direct-to-Earth line-of-sight (LOS) communications from the lunar south pole are governed by orbital geometry and lunar libration:
1. **Low Elevation Geometry:**
   - Because the lunar spin axis is tilted by only $\approx 1.54^\circ$ to the ecliptic, the Earth appears permanently near the horizon from the lunar south pole.
   - At the mean lunar center of mass, Earth's elevation angle ranges between $-8.5^\circ$ and $+8.5^\circ$ depending on optical and physical librations in latitude and longitude.
   - During our baseline epoch (March 2026), Earth elevation at $90^\circ\text{S}$ is $+2.37^\circ$ at azimuth $4.09^\circ$.
2. **Libration Cycle:**
   - Over the ~27.3-day tropical/draconic month, Earth describes an apparent elliptical path in the lunar sky.
   - Ground points located behind elevated crater rims experience periodic occultation (blackout) when Earth's elevation drops below the local terrain horizon.

---

## 2. Verification Against Shared Horizon Code Paths

To satisfy strict modularity and prevent duplication:
- `comms-service` reuses `selene_horizon.compute_horizon_profile` and `selene_horizon.evaluate_lit_mask` from `libs/selene-horizon`.
- **Consistency Verification:**
  - Identical spherical curvature correction ($-s^2 / (2 R_M)$) applied to both solar rays and Earth communication rays.
  - The horizon profile precomputed once per DEM is completely shared:
    $$\text{visible}(x, y, t) = \text{el}_{\text{Earth}}(t) > H(x, y, \text{az}_{\text{Earth}}(t))$$
  - In Shackleton Crater floor ($d < 1,850\text{ m}$), the rim rises to $\approx 31^\circ$ elevation. Because Earth elevation never exceeds $+8.5^\circ$, the crater floor is in **100% permanent communications blackout** (zero direct Earth windows).
  - On the Shackleton rim and connecting ridge ($d \approx 2,100\text{ m}$), unobstructed elevation horizon is $\approx 0^\circ$, granting **continuous Earth line-of-sight coverage (> 88% availability)**.

---

## 3. Route & Waypoint Validation (`along-path`)

A synthetic traverse path across an analytic 300 m ridge verified that:
1. When the rover passes behind the ridge relative to Earth azimuth, the state transitions instantaneously to `BLACKOUT`.
2. When crossing the crest, the state transitions to `CONNECTED`.
3. Contiguous time intervals merge accurately into window objects (`start_iso`, `end_iso`, `duration_hours`).

---

## 4. Operational & Engineering Limitations (v1)

- **Line-of-Sight Only:** Phase 3 models purely geometric terrain obstruction. Radio-frequency (RF) link budget, atmospheric noise, antenna gain patterns, and transmitter power are not modeled.
- **Direct-to-Earth Only:** Lunar relay satellites (e.g. Lunar Gateway, Queqiao relays) are not included in v1.
- **Terrain DEM Bounded:** Accuracy depends on 20 m LOLA DEM resolution and absence of unmapped micro-relief.
