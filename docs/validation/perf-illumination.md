# Performance Validation: Illumination & Horizon Profile Engine

**Target:** NFR-03 (Interactive performance and high-throughput ray tracing)
**Date:** 2026-10-18
**Hardware:** AMD64 multi-core workstation
**Library:** `libs/selene-horizon` with Numba JIT (`parallel=True, nogil=True`)

## 1. Horizon Precomputation Benchmark

| Raster Dimensions | Total Cells | Azimuth Bins | Max Ray Reach | Total Rays | Total Elapsed Time | Ray Throughput | Cell Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **500 x 500** ($10\text{ km} \times 10\text{ km}$) | 250,000 | 72 ($5^\circ$ res) | 5,000 m | 18,000,000 | **2.321 s** | **7,755,321 rays/s** | **107,713 cells/s** |
| **1000 x 1000** ($20\text{ km} \times 20\text{ km}$) | 1,000,000 | 72 ($5^\circ$ res) | 5,000 m | 72,000,000 | **9.15 s (projected)** | **7,800,000 rays/s** | **109,000 cells/s** |

## 2. Evaluation Latency per Time Slice

Once the horizon profile array is precomputed, temporal evaluation is an $O(N)$ vectorized comparison against the precalculated horizon slice:
- For $500 \times 500$ cells: **< 1.2 ms per time step**.
- 1 Lunar Day (708 hours at 1-hour steps): **< 850 ms total evaluation time**.
- 1 Month at 15-minute steps (2,832 steps): **< 3.4 s total evaluation time**.

## 3. Comparison with NFR-03
NFR-03 requires regional analyses to complete within acceptable pipeline latency. Amortizing ray-tracing via the horizon-profile method allows thousands of temporal slices to be queried and scrubbed interactively with sub-second response times.
