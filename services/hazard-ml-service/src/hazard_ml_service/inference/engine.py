"""Inference engine orchestrating tiled ONNX CPU evaluation and NMS deduplication."""

import time
from dataclasses import dataclass
from typing import Any
import numpy as np
import onnxruntime as ort
from scipy.ndimage import maximum_filter

from hazard_ml_service.inference.tiler import generate_overlapping_tiles, stitch_hazard_heatmap
from hazard_ml_service.inference.nms import non_maximum_suppression_circles


@dataclass
class InferenceResult:
    hazard_raster: np.ndarray  # [H, W] float32 in [0, 1]
    detections: list[dict[str, Any]]
    tiles_processed: int
    elapsed_seconds: float
    tiles_per_second: float
    megapixels_per_second: float


class InferenceEngine:
    """Manages tiled ONNX model execution with boundary deduplication and throughput metrics."""

    def __init__(
        self,
        session: ort.InferenceSession,
        tile_size: int = 256,
        overlap: int = 32,
        conf_threshold: float = 0.75,
        nms_iou_threshold: float = 0.35,
    ) -> None:
        self.session = session
        self.tile_size = tile_size
        self.overlap = overlap
        self.conf_threshold = conf_threshold
        self.nms_iou_threshold = nms_iou_threshold

    def run_image(
        self,
        image: np.ndarray,
        batch_size: int = 4,
    ) -> InferenceResult:
        """Execute full inference pipeline over a single-band orthoimage raster."""
        h, w = image.shape[:2]
        tiles = generate_overlapping_tiles(image, tile_size=self.tile_size, overlap=self.overlap)

        t0 = time.perf_counter()
        heatmaps: list[np.ndarray] = []
        raw_detections: list[dict[str, Any]] = []

        # Process in batches
        for i in range(0, len(tiles), batch_size):
            batch_tiles = tiles[i : i + batch_size]
            batch_arr = np.stack([t.data[np.newaxis, :, :] for t in batch_tiles], axis=0).astype(
                np.float32
            )

            # ONNX model input
            # If model expects batch dimension [N, 1, 256, 256] or loop if static [1, 1, 256, 256]
            # Since our static model has shape [1, 1, 256, 256], iterate per tile
            for t_idx, tile in enumerate(batch_tiles):
                single_inp = batch_arr[t_idx : t_idx + 1]
                res = self.session.run(None, {"input_image": single_inp})
                h_map = res[0][0, 0]
                c_map = res[1][0, 0]
                heatmaps.append(h_map)

                # Extract local peaks in tile
                local_peaks = (maximum_filter(c_map, size=21) == c_map) & (
                    c_map >= self.conf_threshold
                )
                y_coords, x_coords = np.where(local_peaks)

                for cy, cx in zip(y_coords, x_coords, strict=False):
                    conf = float(c_map[cy, cx])
                    global_x = float(cx + tile.x_min)
                    global_y = float(cy + tile.y_min)
                    raw_detections.append(
                        {
                            "center_x": global_x,
                            "center_y": global_y,
                            "radius_px": 14.0,
                            "confidence": conf,
                            "tile_index": tile.tile_index,
                        }
                    )

        # Stitch hazard heatmap
        global_hazard = stitch_hazard_heatmap(tiles, heatmaps, (h, w))

        # Deduplicate detections across overlapping borders
        deduped_detections = non_maximum_suppression_circles(
            raw_detections,
            iou_threshold=self.nms_iou_threshold,
            center_dist_ratio=0.60,
        )

        elapsed = max(1e-6, time.perf_counter() - t0)
        tiles_processed = len(tiles)
        tiles_per_sec = tiles_processed / elapsed
        mp_per_sec = (h * w / 1e6) / elapsed

        return InferenceResult(
            hazard_raster=global_hazard,
            detections=deduped_detections,
            tiles_processed=tiles_processed,
            elapsed_seconds=elapsed,
            tiles_per_second=tiles_per_sec,
            megapixels_per_second=mp_per_sec,
        )
