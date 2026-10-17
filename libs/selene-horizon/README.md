# selene-horizon

Shared, high-performance lunar horizon profile computation library. Reusable across `illumination-service` and `comms-service`.

## Features
- **Numba Parallel Ray Tracing:** Multi-core JIT ray-marching kernel (`parallel=True, nogil=True`) for 360-720 azimuth bins.
- **Lunar Spherical Curvature:** Rigorous $-s^2 / (2 R_M)$ spherical drop applied to all distant terrain samples ($R_M = 1,737,400\text{ m}$).
- **Halo & Tiling Engine:** Zero-seam horizon extraction with relief-dependent padding margins.
- **Golden Validation Suite:** Analytic tests for flat plane ($0^\circ$), conical peak ($\arctan(H/D)$), and bowl crater rim elevation angles.
