"""SelenePlan horizon computation library: parallel ray marching with lunar curvature correction."""

from selene_horizon.horizon import (
    compute_horizon_profile,
    compute_padding_margin_m,
    evaluate_lit_mask,
)

__all__ = [
    "compute_horizon_profile",
    "compute_padding_margin_m",
    "evaluate_lit_mask",
]
