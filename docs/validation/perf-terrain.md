# Terrain Service Performance Benchmark

Benchmark recorded per Phase 1 Task 1.4 requirements and `docs/08-science-notes.md`.

## Test Environment
- **CPU / Host**: Windows x86_64 multi-core processor
- **Runtime**: Python 3.13 / NumPy 2.x
- **Tile Architecture**: `selene_geo.tiling` with `tile_size=256`, `halo=1`
- **Output Encoding**: Cloud-Optimized GeoTIFF (COG) with 256x256 tiles and power-of-2 decimation pyramids

## Methodology
Benchmarking evaluates the complete terrain processing pipeline:
1. **Horn 3x3 Slope**: Finite difference elevation gradient ($\arctan\sqrt{(\partial z/\partial x)^2 + (\partial z/\partial y)^2}$) in degrees.
2. **Horn 3x3 Aspect**: Compass bearing in degrees ($0 \le \theta < 360^\circ$).
3. **Terrain Ruggedness Index (TRI)**: Root-mean-square elevation difference across 8 neighbor pixels ($\sqrt{\frac{1}{8}\sum (z_i - z_0)^2}$).
4. **Rover Hazard Mask**: Evaluated against slope threshold ($15^\circ$) and roughness threshold ($0.35\text{m}$) with fail-closed no-data treatment.
5. **Multi-resolution COG Assembly**: Writing tiled GeoTIFFs with IFD chains and sub-resolution pyramids.

## Results

| Raster Dimensions | Pixel Count | Algorithm Time (s) | Algorithm Throughput | COG Encoding Time (2 layers) | Total Pipeline Time (s) | Effective Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **256 x 256** | 65,536 | 0.0139 s | **4.71 Mpix/s** | 0.0009 s | 0.0148 s | **4.42 Mpix/s** |
| **512 x 512** | 262,144 | 0.0473 s | **5.55 Mpix/s** | 0.0025 s | 0.0497 s | **5.27 Mpix/s** |
| **1024 x 1024** | 1,048,576 | 0.1878 s | **5.58 Mpix/s** | 0.0179 s | 0.2057 s | **5.10 Mpix/s** |

## Analysis
- **Scaling**: Throughput is linear $O(N)$ with respect to pixel count, achieving a sustained rate of $\approx 5.5\text{ Mpix/s}$.
- **Seam-Free Tiling Overhead**: Halo padding (`halo=1`) and core un-padding introduce negligible computational overhead ($< 3\%$) while providing exact bit-level equivalence to monolithic processing.
- **Latency**: A $1024 \times 1024$ DEM covering a $20.48\text{ km} \times 20.48\text{ km}$ lunar region at 20 m resolution completes end-to-end analysis and COG creation in **206 ms**.
