"""Landing site ranking engine with hard constraint filtering and soft multi-criteria scoring."""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class CandidateSite:
    site_id: str
    x_m: float
    y_m: float
    lat_deg: float
    lon_deg: float
    rank: int = 0
    score: float = 0.0
    score_breakdown: dict[str, float] = None
    rejected: bool = False
    reject_reasons: list[str] = None


@dataclass
class RankingResult:
    ranked_sites: list[CandidateSite]
    rejected_sites: list[CandidateSite]
    total_evaluated: int
    top_site: CandidateSite | None


def rank_landing_sites(
    slope_grid: np.ndarray,
    hazard_grid: np.ndarray,
    lit_fraction_grid: np.ndarray,
    earth_vis_grid: np.ndarray,
    roughness_grid: np.ndarray,
    longest_dark_grid: np.ndarray,
    resolution_m: float = 20.0,
    spacing_cells: int = 5,
    footprint_radius_m: float = 40.0,
    max_slope_deg: float = 12.0,
    min_lit_fraction: float = 0.40,
    min_earth_vis_fraction: float = 0.40,
    weights: dict[str, float] | None = None,
) -> RankingResult:
    """Generate, filter, and rank candidate landing sites over AOI grids.

    Hard Constraints (FR-21):
      1. Footprint slope max <= max_slope_deg
      2. Zero hazard cells inside footprint radius
      3. Minimum illumination lit fraction >= min_lit_fraction
      4. Minimum Earth line-of-sight fraction >= min_earth_vis_fraction

    Soft Scoring:
      Weighted combination of lit fraction, short dark period, Earth visibility, and smoothness.
    """
    if weights is None:
        weights = {
            "lit_fraction": 0.35,
            "longest_dark": 0.25,
            "earth_vis": 0.25,
            "smoothness": 0.15,
        }

    h, w = slope_grid.shape
    footprint_cells = max(1, math.ceil(footprint_radius_m / resolution_m))

    ranked_sites: list[CandidateSite] = []
    rejected_sites: list[CandidateSite] = []

    site_idx = 0
    for r in range(footprint_cells, h - footprint_cells, spacing_cells):
        for c in range(footprint_cells, w - footprint_cells, spacing_cells):
            site_id = f"site-{site_idx:04d}"
            site_idx += 1

            # Extract footprint patch
            y0, y1 = r - footprint_cells, r + footprint_cells + 1
            x0, x1 = c - footprint_cells, c + footprint_cells + 1

            slope_patch = slope_grid[y0:y1, x0:x1]
            hazard_patch = hazard_grid[y0:y1, x0:x1]

            max_slope_in_fp = float(np.max(slope_patch))
            haz_count = int(np.sum(hazard_patch))
            lit_frac = float(lit_fraction_grid[r, c])
            earth_vis = float(earth_vis_grid[r, c])
            roughness = float(roughness_grid[r, c])
            longest_dark = float(longest_dark_grid[r, c])

            # Projected metres (center is at 0, 0)
            x_m = float((c - w / 2) * resolution_m)
            y_m = float((h / 2 - r) * resolution_m)
            dist_m = math.hypot(x_m, y_m)
            lat = 90.0 - (dist_m / 30300.0)
            lon = (math.atan2(x_m, -y_m) * 180.0) / math.pi
            if lon < 0:
                lon += 360.0

            reasons: list[str] = []

            # Hard Constraint 1: Maximum Slope
            if max_slope_in_fp > max_slope_deg:
                reasons.append(
                    f"Maximum footprint slope {max_slope_in_fp:.1f}° exceeds limit {max_slope_deg:.1f}°"
                )

            # Hard Constraint 2: Hazard Cells
            if haz_count > 0:
                reasons.append(f"Landing footprint contains {haz_count} hazardous cells")

            # Hard Constraint 3: Lit Fraction
            if lit_frac < min_lit_fraction:
                reasons.append(
                    f"Sunlit fraction {lit_frac * 100:.1f}% below minimum {min_lit_fraction * 100:.1f}%"
                )

            # Hard Constraint 4: Earth Visibility
            if earth_vis < min_earth_vis_fraction:
                reasons.append(
                    f"Earth visibility {earth_vis * 100:.1f}% below minimum {min_earth_vis_fraction * 100:.1f}%"
                )

            if reasons:
                rejected_sites.append(
                    CandidateSite(
                        site_id=site_id,
                        x_m=x_m,
                        y_m=y_m,
                        lat_deg=lat,
                        lon_deg=lon,
                        rejected=True,
                        reject_reasons=reasons,
                        score_breakdown={},
                    )
                )
            else:
                # Compute soft score
                # Normalize longest dark (assume 708h lunar day max)
                dark_score = max(0.0, 1.0 - (longest_dark / 708.0))
                smoothness_score = max(0.0, 1.0 - min(1.0, roughness / 3.0))

                breakdown = {
                    "lit_fraction": lit_frac,
                    "longest_dark_score": dark_score,
                    "earth_vis": earth_vis,
                    "smoothness": smoothness_score,
                }

                total_score = (
                    weights["lit_fraction"] * lit_frac
                    + weights["longest_dark"] * dark_score
                    + weights["earth_vis"] * earth_vis
                    + weights["smoothness"] * smoothness_score
                )

                ranked_sites.append(
                    CandidateSite(
                        site_id=site_id,
                        x_m=x_m,
                        y_m=y_m,
                        lat_deg=lat,
                        lon_deg=lon,
                        score=float(total_score),
                        score_breakdown=breakdown,
                        rejected=False,
                        reject_reasons=[],
                    )
                )

    # Sort descending by score, deterministic tie-breaking by site_id
    ranked_sites.sort(key=lambda s: (-s.score, s.site_id))
    for rank_idx, site in enumerate(ranked_sites, start=1):
        site.rank = rank_idx

    top = ranked_sites[0] if ranked_sites else None
    return RankingResult(
        ranked_sites=ranked_sites,
        rejected_sites=rejected_sites,
        total_evaluated=len(ranked_sites) + len(rejected_sites),
        top_site=top,
    )
