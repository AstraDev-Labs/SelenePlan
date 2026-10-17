"""Performance benchmark for selene-horizon ray-tracing engine on 1k x 1k and tiled AOIs."""

import time
import numpy as np

from selene_horizon.horizon import compute_horizon_profile


def run_benchmark(
    size: int = 500, azimuth_bins: int = 72, max_ray_dist_m: float = 10_000.0
) -> dict[str, float]:
    """Benchmark horizon calculation for a given raster size."""
    print(f"Generating synthetic DEM {size}x{size}...")
    dem = np.random.uniform(0.0, 500.0, (size, size)).astype(np.float64)

    # Warmup / JIT compilation
    print("Warmup JIT...")
    _ = compute_horizon_profile(
        dem[:32, :32], cell_size_m=20.0, azimuth_bins=12, max_ray_dist_m=500.0
    )

    print(
        f"Running benchmark on {size}x{size} DEM ({size*size:,} cells, {azimuth_bins} azimuth bins)..."
    )
    t0 = time.perf_counter()
    horizon, _ = compute_horizon_profile(
        dem=dem,
        cell_size_m=20.0,
        azimuth_bins=azimuth_bins,
        max_ray_dist_m=max_ray_dist_m,
    )
    t1 = time.perf_counter()

    elapsed_s = t1 - t0
    cells = size * size
    rays_computed = cells * azimuth_bins
    throughput = rays_computed / elapsed_s

    print(f"Size: {size}x{size} ({cells:,} cells)")
    print(f"Elapsed: {elapsed_s:.3f} s")
    print(f"Rays computed: {rays_computed:,}")
    print(f"Throughput: {throughput:,.0f} rays/sec ({cells / elapsed_s:,.0f} cells/sec)")
    return {
        "size": float(size),
        "cells": float(cells),
        "elapsed_s": elapsed_s,
        "rays_computed": float(rays_computed),
        "throughput_rays_per_s": throughput,
    }


if __name__ == "__main__":
    run_benchmark(size=500, azimuth_bins=72, max_ray_dist_m=5_000.0)
