"""CPU inference throughput benchmark for crater detection."""

from pathlib import Path

import numpy as np
import onnxruntime as ort
from hazard_ml_service.inference.engine import InferenceEngine


def test_cpu_inference_throughput_benchmark() -> None:
    onnx_path = (
        Path(__file__).resolve().parent.parent.parent / "model-cards" / "crater_detector_v1.onnx"
    )
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    # Simulate a 512x512 orthoimage (~4 overlapping 256x256 tiles)
    test_image = np.ones((512, 512), dtype=np.float32) * 0.5
    engine = InferenceEngine(session, tile_size=256, overlap=32)

    # Warmup
    engine.run_image(test_image[:256, :256])

    # Benchmark run
    result = engine.run_image(test_image)

    print("\n--- CPU INFERENCE BENCHMARK ---")
    print(f"Tiles Processed: {result.tiles_processed}")
    print(f"Elapsed Time: {result.elapsed_seconds * 1000:.2f} ms")
    print(f"Throughput: {result.tiles_per_second:.1f} tiles/sec")
    print(f"Megapixels/sec: {result.megapixels_per_second:.2f} MP/s")
    print("-------------------------------\n")

    # Target: At least 5 tiles per second on standard modern CPU
    assert result.tiles_per_second > 2.0
    assert result.tiles_processed >= 4
