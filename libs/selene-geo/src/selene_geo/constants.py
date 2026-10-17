"""Physical constants and standard unit conversions for lunar spatial analysis."""

from __future__ import annotations

import math

# IAU standard lunar reference sphere radius in metres (docs/08-science-notes.md Section 1, AS-01)
MOON_RADIUS_M: float = 1_737_400.0

# Moon surface gravity in m/s^2
MOON_GRAVITY_M_S2: float = 1.62

# Solar constant at 1 AU in W/m^2 (AS-03)
SOLAR_CONSTANT_1AU_W_M2: float = 1361.0


def deg_to_rad(degrees: float) -> float:
    """Convert degrees to radians (internal SI representation)."""
    return math.radians(degrees)


def rad_to_deg(radians: float) -> float:
    """Convert radians to degrees (API / UI boundary representation)."""
    return math.degrees(radians)


def m_to_km(metres: float) -> float:
    """Convert metres to kilometres."""
    return metres / 1000.0


def km_to_m(kilometres: float) -> float:
    """Convert kilometres to metres."""
    return kilometres * 1000.0
