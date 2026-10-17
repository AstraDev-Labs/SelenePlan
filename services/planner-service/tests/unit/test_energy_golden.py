"""Golden tests for rover energy model and survival limits (Task 5.1)."""

import math

from planner_service.energy.model import (
    RoverEnergyProfile,
    compute_solar_power,
    compute_step_energy,
)


def test_energy_golden_constant_power_times_time() -> None:
    profile = RoverEnergyProfile(
        battery_capacity_wh=500.0,
        panel_area_m2=1.2,
        panel_efficiency=0.28,
        solar_constant_w_m2=1361.0,
        power_drive_w=80.0,
    )

    # Sun elevation 30 degrees: sin(30) = 0.5
    sun_elev = 30.0
    p_solar_expected = 1.2 * 0.28 * 1361.0 * 0.5  # 228.648 W
    p_solar = compute_solar_power(sun_elev, profile, is_lit=True)
    assert math.isclose(p_solar, p_solar_expected, rel_tol=1e-5)

    # 2 hours of driving under constant illumination
    # Net power = 228.648 W - 80 W = 148.648 W
    # Delta E = 148.648 * 2 = 297.296 Wh
    start_bat = 150.0
    duration_h = 2.0
    expected_next = min(
        profile.battery_capacity_wh, start_bat + (p_solar - profile.power_drive_w) * duration_h
    )

    next_bat, violated = compute_step_energy(
        current_battery_wh=start_bat,
        mode="drive",
        sun_elev_deg=sun_elev,
        duration_hours=duration_h,
        profile=profile,
        is_lit=True,
    )

    assert math.isclose(next_bat, expected_next, rel_tol=1e-4)
    assert violated is False


def test_energy_golden_long_dark_segment_violates_survival_minimum() -> None:
    profile = RoverEnergyProfile(
        battery_capacity_wh=500.0,
        min_survival_wh=100.0,
        power_drive_w=80.0,
    )

    # Driving in complete shadow (is_lit=False) for 6 hours
    # Consumption: 80 W * 6 h = 480 Wh
    start_bat = 300.0
    next_bat, violated = compute_step_energy(
        current_battery_wh=start_bat,
        mode="drive",
        sun_elev_deg=0.0,
        duration_hours=6.0,
        profile=profile,
        is_lit=False,
    )

    # 300 - 480 = 0 (clamped) < 100 Wh minimum
    assert next_bat == 0.0
    assert violated is True


def test_energy_zero_generation_below_horizon() -> None:
    profile = RoverEnergyProfile()
    p_neg = compute_solar_power(-1.5, profile, is_lit=True)
    assert p_neg == 0.0

    p_zero = compute_solar_power(0.0, profile, is_lit=True)
    assert p_zero == 0.0
