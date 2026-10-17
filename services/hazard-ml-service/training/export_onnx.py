"""Export reproducible ONNX crater detection model with Dual-Head outputs."""

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper


def build_crater_onnx_model(output_path: str | Path, seed: int = 42) -> Path:
    """Build and save a standard ONNX crater detector model with dual heads.

    Inputs:
        input_image: Tensor of shape [1, 1, 256, 256] (float32, [0, 1])
    Outputs:
        hazard_heatmap: Tensor of shape [1, 1, 256, 256] (float32, [0, 1])
        centroid_heatmap: Tensor of shape [1, 1, 256, 256] (float32, [0, 1])
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Inputs and Outputs
    input_tensor = helper.make_tensor_value_info("input_image", TensorProto.FLOAT, [1, 1, 256, 256])
    hazard_heatmap_out = helper.make_tensor_value_info(
        "hazard_heatmap", TensorProto.FLOAT, [1, 1, 256, 256]
    )
    centroid_heatmap_out = helper.make_tensor_value_info(
        "centroid_heatmap", TensorProto.FLOAT, [1, 1, 256, 256]
    )

    # 2. Weights and Initializers
    # Conv1: 1 -> 8 filters of size 7x7
    w_conv1 = np.zeros((8, 1, 7, 7), dtype=np.float32)
    y, x = np.ogrid[-3:4, -3:4]
    dist = np.sqrt(x**2 + y**2)

    # Filter 0: Small crater bowl/rim matched filter
    k0 = np.zeros((7, 7), dtype=np.float32)
    k0[dist <= 1.5] = -2.0
    k0[(dist > 1.5) & (dist <= 3.0)] = 1.0
    k0 -= k0.mean()
    w_conv1[0, 0] = k0

    # Filter 1: Medium crater bowl/rim matched filter
    k1 = np.zeros((7, 7), dtype=np.float32)
    k1[dist <= 2.2] = -2.0
    k1[(dist > 2.2) & (dist <= 3.2)] = 1.2
    k1 -= k1.mean()
    w_conv1[1, 0] = k1

    # Filter 2: Solar gradient (illuminated rim / shadow contrast at 45 deg)
    k2 = (x + y).astype(np.float32)
    k2 -= k2.mean()
    w_conv1[2, 0] = k2 * 0.1

    # Filter 3: Orthogonal gradient (-45 deg)
    k3 = (x - y).astype(np.float32)
    k3 -= k3.mean()
    w_conv1[3, 0] = k3 * 0.1

    # Filter 4: Circular laplacian
    k4 = np.zeros((7, 7), dtype=np.float32)
    k4[3, 3] = 8.0
    k4[(dist >= 1.0) & (dist <= 2.0)] = -1.0
    k4 -= k4.mean()
    w_conv1[4, 0] = k4 * 0.2

    # Filters 5-7: Directional edge filters
    for idx, angle in enumerate([0.0, 90.0, 180.0], start=5):
        rad = np.radians(angle)
        kf = (np.cos(rad) * x + np.sin(rad) * y).astype(np.float32)
        kf -= kf.mean()
        w_conv1[idx, 0] = kf * 0.1

    b_conv1 = np.zeros(8, dtype=np.float32)

    # Conv2: 8 -> 8 filters (3x3)
    w_conv2 = np.zeros((8, 8, 3, 3), dtype=np.float32)
    for i in range(8):
        w_conv2[i, i, 1, 1] = 0.5
        w_conv2[i, (i + 1) % 8, :, :] = 0.05
    b_conv2 = np.zeros(8, dtype=np.float32)

    # Branch 1 (Hazard Heatmap): Conv_h1 (8 -> 4, 3x3), Conv_h2 (4 -> 1, 3x3)
    w_h1 = np.zeros((4, 8, 3, 3), dtype=np.float32)
    for i in range(4):
        w_h1[i, i, :, :] = 0.25
        w_h1[i, i + 4, :, :] = 0.15
    b_h1 = np.zeros(4, dtype=np.float32)

    w_h2 = np.zeros((1, 4, 3, 3), dtype=np.float32)
    w_h2[0, 0, :, :] = 0.3
    w_h2[0, 1, :, :] = 0.3
    b_h2 = np.array([-0.6], dtype=np.float32)

    # Branch 2 (Centroid Peaks): Conv_c1 (8 -> 1, 3x3)
    w_c1 = np.zeros((1, 8, 3, 3), dtype=np.float32)
    w_c1[0, 0, 1, 1] = 0.8
    w_c1[0, 1, 1, 1] = 0.8
    b_c1 = np.array([-1.2], dtype=np.float32)

    initializers = [
        helper.make_tensor("w_conv1", TensorProto.FLOAT, [8, 1, 7, 7], w_conv1.flatten().tolist()),
        helper.make_tensor("b_conv1", TensorProto.FLOAT, [8], b_conv1.tolist()),
        helper.make_tensor("w_conv2", TensorProto.FLOAT, [8, 8, 3, 3], w_conv2.flatten().tolist()),
        helper.make_tensor("b_conv2", TensorProto.FLOAT, [8], b_conv2.tolist()),
        helper.make_tensor("w_h1", TensorProto.FLOAT, [4, 8, 3, 3], w_h1.flatten().tolist()),
        helper.make_tensor("b_h1", TensorProto.FLOAT, [4], b_h1.tolist()),
        helper.make_tensor("w_h2", TensorProto.FLOAT, [1, 4, 3, 3], w_h2.flatten().tolist()),
        helper.make_tensor("b_h2", TensorProto.FLOAT, [1], b_h2.tolist()),
        helper.make_tensor("w_c1", TensorProto.FLOAT, [1, 8, 3, 3], w_c1.flatten().tolist()),
        helper.make_tensor("b_c1", TensorProto.FLOAT, [1], b_c1.tolist()),
    ]

    # 3. Nodes
    nodes = [
        # Backbone (7x7 conv with pad=3 maintains exact 256x256 dimensions)
        helper.make_node(
            "Conv", ["input_image", "w_conv1", "b_conv1"], ["c1_out"], pads=[3, 3, 3, 3]
        ),
        helper.make_node("Relu", ["c1_out"], ["relu1_out"]),
        helper.make_node(
            "Conv", ["relu1_out", "w_conv2", "b_conv2"], ["c2_out"], pads=[1, 1, 1, 1]
        ),
        helper.make_node("Relu", ["c2_out"], ["features"]),
        # Hazard Heatmap Head
        helper.make_node("Conv", ["features", "w_h1", "b_h1"], ["h1_out"], pads=[1, 1, 1, 1]),
        helper.make_node("Relu", ["h1_out"], ["h1_relu"]),
        helper.make_node("Conv", ["h1_relu", "w_h2", "b_h2"], ["h2_out"], pads=[1, 1, 1, 1]),
        helper.make_node("Sigmoid", ["h2_out"], ["hazard_heatmap"]),
        # Centroid Heatmap Head
        helper.make_node("Conv", ["features", "w_c1", "b_c1"], ["c_conv_out"], pads=[1, 1, 1, 1]),
        helper.make_node("Sigmoid", ["c_conv_out"], ["centroid_heatmap"]),
    ]

    # 4. Graph & Model
    graph = helper.make_graph(
        nodes,
        "SelenePlanCraterDetector",
        [input_tensor],
        [hazard_heatmap_out, centroid_heatmap_out],
        initializers,
    )

    model = helper.make_model(
        graph,
        producer_name="SelenePlan ML Pipeline",
        producer_version="1.0.0",
        opset_imports=[helper.make_opsetid("", 17)],
        ir_version=10,
    )

    onnx.checker.check_model(model)
    onnx.save(model, str(output_path))
    return output_path


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "model-cards"
    model_file = build_crater_onnx_model(out_dir / "crater_detector_v1.onnx")
    print(f"Exported model to: {model_file} (size: {model_file.stat().st_size} bytes)")
