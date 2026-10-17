"""Golden end-to-end pipeline and convergence tests for illumination service."""

import math
from pathlib import Path

import numpy as np
import pytest

from illumination_service.storage.zarr_store import ZarrCubeStore
from illumination_service.worker.pipeline import IlluminationPipeline
from selene_geo.spice import default_spice_manager


@pytest.fixture(scope="module")
def setup_spice_and_pipeline(tmp_path_factory: pytest.TempPathFactory) -> IlluminationPipeline:
    spice_dir = Path("data/spice")
    tls = spice_dir / "naif0012.tls"
    tpc = spice_dir / "pck00010.tpc"
    bsp = spice_dir / "de421.bsp"

    if not (tls.is_file() and tpc.is_file() and bsp.is_file()):
        pytest.skip("SPICE kernels not found in data/spice/")

    default_spice_manager.load_kernels([tls, tpc, bsp])
    temp_dir = tmp_path_factory.mktemp("illum_zarr")
    store = ZarrCubeStore(base_dir=temp_dir)
    return IlluminationPipeline(cube_store=store)


def test_pipeline_reproducibility(setup_spice_and_pipeline: IlluminationPipeline) -> None:
    """Acceptance Criterion 5: Same inputs and parameters give bit-for-bit identical results across two runs."""
    pipeline = setup_spice_and_pipeline

    # Create synthetic conical terrain
    size = 41
    cr, cc = 20, 20
    r_idx, c_idx = np.ogrid[:size, :size]
    dist = np.sqrt((r_idx - cr) ** 2 + (c_idx - cc) ** 2) * 20.0
    dem = np.maximum(0.0, 300.0 * (1.0 - dist / 300.0))

    lat_rad = math.radians(-89.5)
    lon_rad = 0.0
    start = "2026-03-01T00:00:00Z"
    end = "2026-03-01T12:00:00Z"
    step_s = 7200.0  # 2 hours

    # Run 1
    prod1_id, meta1 = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=lat_rad,
        obs_lon_rad=lon_rad,
        start_iso=start,
        end_iso=end,
        time_step_s=step_s,
        dataset_version_id="dem-v1",
        crs_wkt="LOCAL_CRS",
        bounds=[-400.0, -400.0, 400.0, 400.0],
        azimuth_bins=36,
        max_ray_dist_m=1000.0,
    )

    # Run 2
    prod2_id, meta2 = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=lat_rad,
        obs_lon_rad=lon_rad,
        start_iso=start,
        end_iso=end,
        time_step_s=step_s,
        dataset_version_id="dem-v1",
        crs_wkt="LOCAL_CRS",
        bounds=[-400.0, -400.0, 400.0, 400.0],
        azimuth_bins=36,
        max_ray_dist_m=1000.0,
    )

    # Read back products
    cube1 = pipeline.cube_store.read_slice(prod1_id, 0)
    cube2 = pipeline.cube_store.read_slice(prod2_id, 0)
    assert np.array_equal(cube1, cube2)

    lit1 = pipeline.cube_store.read_layer(prod1_id, "lit_fraction")
    lit2 = pipeline.cube_store.read_layer(prod2_id, "lit_fraction")
    assert np.array_equal(lit1, lit2)

    assert meta1.summary_stats == meta2.summary_stats


def test_pipeline_convergence(setup_spice_and_pipeline: IlluminationPipeline) -> None:
    """Acceptance Criterion 4: Halving time step and doubling azimuth bins changes lit fraction by < 5%."""
    pipeline = setup_spice_and_pipeline

    size = 41
    dem = np.full((size, size), 50.0, dtype=np.float64)
    # Add a ridge
    dem[:, 20] = 200.0

    lat_rad = math.radians(-89.5)
    lon_rad = 0.0
    start = "2026-03-01T00:00:00Z"
    end = "2026-03-01T12:00:00Z"

    # Coarse run: dt = 7200s (2h), bins = 36
    prod_coarse, meta_coarse = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=lat_rad,
        obs_lon_rad=lon_rad,
        start_iso=start,
        end_iso=end,
        time_step_s=7200.0,
        dataset_version_id="dem-v1",
        crs_wkt="LOCAL_CRS",
        bounds=[-400.0, -400.0, 400.0, 400.0],
        azimuth_bins=36,
        max_ray_dist_m=1000.0,
    )

    # Refined run: dt = 3600s (1h, halved), bins = 72 (doubled)
    prod_fine, meta_fine = pipeline.run_analysis(
        dem=dem,
        cell_size_m=20.0,
        obs_lat_rad=lat_rad,
        obs_lon_rad=lon_rad,
        start_iso=start,
        end_iso=end,
        time_step_s=3600.0,
        dataset_version_id="dem-v1",
        crs_wkt="LOCAL_CRS",
        bounds=[-400.0, -400.0, 400.0, 400.0],
        azimuth_bins=72,
        max_ray_dist_m=1000.0,
    )

    f_coarse = meta_coarse.summary_stats["mean_lit_fraction"]
    f_fine = meta_fine.summary_stats["mean_lit_fraction"]

    # Difference must converge within 5%
    diff = abs(f_coarse - f_fine)
    assert diff < 0.05
