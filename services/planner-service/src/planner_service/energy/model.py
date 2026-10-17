"""Pure-function energy model for lunar rover battery and solar panel dynamics."""

import math

from pydantic import BaseModel, Field


class RoverEnergyProfile(BaseModel):
    """Rover energy parameters and operational mode power draws."""

    name: str = "Standard Polar Exploration Rover"
    version: int = 1
    battery_capacity_wh: float = Field(
        default=500.0, description="Nominal battery capacity in Watt-hours"
    )
    min_survival_wh: float = Field(
        default=100.0, description="Minimum battery charge for thermal survival (20% reserve)"
    )
    panel_area_m2: float = Field(
        default=1.2, description="Effective solar array area in square metres"
    )
    panel_efficiency: float = Field(
        default=0.28, description="Solar cell conversion efficiency (GaAs triple-junction)"
    )
    solar_constant_w_m2: float = Field(
        default=1361.0, description="Solar irradiance at 1 AU in W/m^2"
    )
    power_drive_w: float = Field(default=80.0, description="Locomotion power consumption in Watts")
    power_wait_w: float = Field(
        default=15.0, description="Stationary charging/housekeeping power in Watts"
    )
    power_idle_w: float = Field(
        default=12.0, description="Deep sleep/darkness survival power in Watts"
    )
    power_comms_w: float = Field(
        default=25.0, description="Active communication downlink power in Watts"
    )


def compute_solar_power(
    sun_elev_deg: float,
    profile: RoverEnergyProfile,
    is_lit: bool = True,
) -> float:
    """Calculate instantaneous photovoltaic power generation in Watts.

    Formula:
        P_solar = A_panel * eta_panel * S_0 * max(0, sin(theta_sun_elev))
    """
    if not is_lit or sun_elev_deg <= 0.0:
        return 0.0
    sin_elev = math.sin(math.radians(sun_elev_deg))
    p_gen = (
        profile.panel_area_m2 * profile.panel_efficiency * profile.solar_constant_w_m2 * sin_elev
    )
    return max(0.0, float(p_gen))


def compute_step_energy(
    current_battery_wh: float,
    mode: str,
    sun_elev_deg: float,
    duration_hours: float,
    profile: RoverEnergyProfile,
    is_lit: bool = True,
    slope_deg: float = 0.0,
) -> tuple[float, bool]:
    """Compute updated battery charge level after a duration step and check survival minimum.

    Returns:
        (next_battery_wh, is_survival_violated)
    """
    # 1. Solar generation
    p_in = compute_solar_power(sun_elev_deg, profile, is_lit=is_lit)

    # 2. Operational consumption
    if mode == "drive":
        # Slight uphill power scaling: +1.5 W per degree of positive slope
        slope_adder = max(0.0, slope_deg) * 1.5
        p_out = profile.power_drive_w + slope_adder
    elif mode == "wait":
        p_out = profile.power_wait_w
    elif mode == "idle":
        p_out = profile.power_idle_w
    elif mode == "comms":
        p_out = profile.power_wait_w + profile.power_comms_w
    else:
        p_out = profile.power_idle_w

    net_power = p_in - p_out
    delta_wh = net_power * duration_hours
    next_battery = min(profile.battery_capacity_wh, max(0.0, current_battery_wh + delta_wh))
    is_violated = next_battery < profile.min_survival_wh

    return next_battery, is_violated
