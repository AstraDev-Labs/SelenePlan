# selene-testing

SelenePlan scientific testing library providing synthetic lunar terrain generators with **exact analytic known answers** per `docs/06-testing-strategy.md` Section 3 and `AGENTS.md` Section 5.

## Generators

- **`make_flat_plane(shape, resolution_m, elevation_m)`**:
  - Exact flat horizontal plane ($0.0^\circ$ slope and $0.0\text{ m}$ roughness everywhere).
- **`make_inclined_plane(shape, resolution_m, slope_deg, aspect_deg, base_elevation_m)`**:
  - Mathematically exact linear inclined plane with known slope $\theta$ and aspect azimuth $\alpha$.
  - Formula: $z(x, y) = z_0 + x \tan(\theta) \sin(\alpha) + y \tan(\theta) \cos(\alpha)$.
- **`make_cone(shape, resolution_m, radius_m, height_m, center)`**:
  - Conical peak with known flank slope $\arctan(H / R)$.
  - Known shadow length $L = H / \tan(\beta)$ under sun elevation $\beta$.
- **`make_bowl_crater(shape, resolution_m, radius_m, depth_m, rim_height_m, center)`**:
  - Parabolic bowl depression with raised rim and ejecta decay profile.
  - Known horizon angles for shadow and line-of-sight tests.
- **`make_ridge(shape, resolution_m, length_m, width_m, height_m, azimuth_deg, center)`**:
  - Linear topographic barrier for line-of-sight and Earth-visibility testing.
- **`add_seeded_noise(raster, seed, amplitude_m)`**:
  - Deterministic pseudo-random noise generator.

## Usage

```python
from selene_testing import make_inclined_plane, make_cone

# 1. 10-degree inclined plane facing East (aspect=90)
plane = make_inclined_plane(shape=(100, 100), resolution_m=20.0, slope_deg=10.0, aspect_deg=90.0)
assert plane.metadata["analytic_slope_deg"] == 10.0

# 2. Conical mountain
cone = make_cone(shape=(200, 200), resolution_m=10.0, radius_m=500.0, height_m=150.0)
flank_slope = cone.metadata["analytic_flank_slope_deg"]
```
