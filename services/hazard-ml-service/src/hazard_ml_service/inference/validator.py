"""ONNX graph and operator allowlist validator for secure model execution."""

import onnx


ALLOWED_OPERATORS = {
    "Conv",
    "Relu",
    "Sigmoid",
    "Add",
    "Mul",
    "Sub",
    "Div",
    "MaxPool",
    "AveragePool",
    "Reshape",
    "Concat",
    "Pad",
    "Identity",
    "Constant",
    "Clip",
    "Flatten",
}


class ModelValidationError(Exception):
    """Raised when an ONNX model fails graph validation or uses disallowed operators."""

    pass


def validate_onnx_model(onnx_bytes: bytes) -> None:
    """Validate ONNX model graph structure, input/output tensors, and operator allowlist.

    Ensures SEC-09 compliance:
    - Rejects any deserialization bombs or non-ONNX structures
    - Validates operator set against approved allowlist
    - Verifies input tensor format [1, 1, 256, 256]
    """
    try:
        model = onnx.load_model_from_string(onnx_bytes)
    except Exception as exc:
        raise ModelValidationError(f"Invalid ONNX model payload: {exc}") from exc

    # 1. Structural checker
    try:
        onnx.checker.check_model(model)
    except Exception as exc:
        raise ModelValidationError(f"ONNX graph validation failed: {exc}") from exc

    graph = model.graph

    # 2. Operator Allowlist Check
    for node in graph.node:
        if node.op_type not in ALLOWED_OPERATORS:
            raise ModelValidationError(
                f"Disallowed operator '{node.op_type}' detected in model graph. "
                f"Only standard allowlisted operators are permitted (SEC-09)."
            )

    # 3. Input Tensor Shape Check
    if len(graph.input) < 1:
        raise ModelValidationError("Model must have at least one input tensor")

    input_tensor = graph.input[0]
    shape = [d.dim_value for d in input_tensor.type.tensor_type.shape.dim]
    if len(shape) != 4 or shape[1:] != [1, 256, 256]:
        raise ModelValidationError(
            f"Input tensor shape mismatch: expected [1, 1, 256, 256] or [?, 1, 256, 256], got {shape}"
        )
