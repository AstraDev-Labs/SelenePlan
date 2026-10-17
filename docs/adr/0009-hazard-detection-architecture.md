# ADR-0009: Hazard Detection Architecture: Dual-Head Circle-Aware CNN with ONNX Runtime CPU Serving

**Status:** Accepted
**Date:** 2026-10-18
**Context:**
The hazard ML service (`hazard-ml-service`) must detect impact craters (and discrete obstacles) in high-resolution lunar orthoimagery (256x256 tiles) and serve predictions on standard CPU worker nodes without GPU dependencies (SEC-09, T7, T8). The detector must output both:
1. Discrete vector entities (crater center $x, y$, radius $r$, confidence score) for GIS cataloging, distance-to-hazard queries, and mission reporting.
2. Dense confidence hazard rasters $[H, W] \in [0.0, 1.0]$ for cell-by-cell Boolean fusion with slope and topographic roughness rasters from `terrain-service`.

Three candidate architectures were evaluated:
1. **Generic Bounding Box Detectors (e.g., YOLOv8 / Faster R-CNN):**
   - *Pros:* Widely supported, pretrained weights available.
   - *Cons:* Rectangular bounding boxes poorly represent circular and elliptical crater geometries, especially overlapping craters. Post-processing requires complex anchor decoding and non-standard custom NMS ops often unsupported across pure ONNX CPU runtimes.
2. **Pure Pixel-Level Semantic Segmentation (e.g., U-Net / DeepLabV3):**
   - *Pros:* Clean dense mask output directly matching the hazard raster format.
   - *Cons:* Does not natively separate adjacent or nested overlapping craters into discrete catalog objects without post-hoc morphological watershed segmentation, which is brittle under low-sun shadow conditions.
3. **Dual-Head Circle/Feature-Aware CNN with Standard ONNX Operators (Adopted):**
   - *Architecture:* Fully convolutional backbone with a feature extraction trunk followed by two parallel heads:
     - **Dense Hazard Heatmap Head:** Produces per-pixel obstacle probability $[1, 1, H, W]$ through a spatial sigmoid activation.
     - **Centroid & Geometry Head:** Produces peak centroid activations, radius regression ($r$), and confidence scores $[N, 4]$ ($x, y, r, \text{conf}$).
   - *Runtime & Portability:* Uses only standard ONNX operators (`Conv`, `Relu`, `MaxPool`, `Sigmoid`, `Concat`, `Add`) supported natively by ONNX Runtime 1.31+ on CPU. No custom C++ operators or Python `pickle` deserialization.
   - *Boundary Stitching:* Overlapping tiles ($256 \times 256$ with $32\text{ px}$ stride) are stitched using coordinate projection and spatial circular Non-Maximum Suppression ($\text{IoU}_{\text{circle}} \ge 0.40$).

**Decision:**
Adopt the **Dual-Head Circle/Feature-Aware CNN** architecture exported to signed ONNX (opset 17), served via `onnxruntime` on CPU with strict input/output tensor schema validation and operator allowlisting.

**Consequences:**
- Zero GPU dependency for production inference workers; fast sub-100ms per-tile CPU execution.
- Vector detections and raster masks are produced in a single forward pass with consistent confidence calibration.
- Models must be signed and validated against a model card metrics gate before approval in the registry.
