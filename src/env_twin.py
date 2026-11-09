import math
from typing import Dict
from src.schemas import RegionName, HourlyEnvironment


class RegionalProfile:
    """Static regional characteristics and grid configuration."""
    def __init__(
        self,
        name: RegionName,
        base_temp_c: float,
        temp_swing_c: float,
        base_carbon: float,
        solar_drop: float,
        wind_night_drop: float,
        water_stress: float,
        electricity_cost: float,
    ):
        self.name = name
        self.base_temp_c = base_temp_c
        self.temp_swing_c = temp_swing_c
        self.base_carbon = base_carbon
        self.solar_drop = solar_drop
        self.wind_night_drop = wind_night_drop
        self.water_stress = water_stress
        self.electricity_cost = electricity_cost


# Environmental calibration for 4 distinct data center regions
REGIONS: Dict[RegionName, RegionalProfile] = {
    RegionName.MUMBAI: RegionalProfile(
        name=RegionName.MUMBAI,
        base_temp_c=27.0,
        temp_swing_c=4.0,
        base_carbon=710.0,       # Coal-dominant baseline
        solar_drop=90.0,
        wind_night_drop=40.0,
        water_stress=2.5,
        electricity_cost=0.12,
    ),
    RegionName.RAJASTHAN: RegionalProfile(
        name=RegionName.RAJASTHAN,
        base_temp_c=28.0,
        temp_swing_c=9.0,        # High day-to-night thermal swings
        base_carbon=560.0,
        solar_drop=530.0,        # Massive midday solar clean energy drop
        wind_night_drop=0.0,
        water_stress=5.0,        # Extreme drought vulnerability
        electricity_cost=0.06,
    ),
    RegionName.STOCKHOLM: RegionalProfile(
        name=RegionName.STOCKHOLM,
        base_temp_c=10.0,
        temp_swing_c=3.0,        # Naturally cold ambient Scandinavian climate
        base_carbon=50.0,        # Hydro/nuclear baseline
        solar_drop=10.0,
        wind_night_drop=30.0,    # Night wind generation surge
        water_stress=1.0,        # Low water stress
        electricity_cost=0.05,
    ),
    RegionName.OREGON: RegionalProfile(
        name=RegionName.OREGON,
        base_temp_c=14.0,
        temp_swing_c=5.0,
        base_carbon=120.0,       # Hydro-rich Pacific Northwest
        solar_drop=30.0,
        wind_night_drop=45.0,
        water_stress=1.5,
        electricity_cost=0.07,
    ),
}


class EnvironmentalDigitalTwin:
    """Physics engine for ambient weather, thermodynamics, and grid emission telemetry."""

    @staticmethod
    def calculate_pue(wet_bulb_temp_c: float) -> float:
        """Calculates Power Usage Effectiveness based on cooling air demand."""
        if wet_bulb_temp_c <= 15.0:
            return 1.10  # Free ambient air cooling requires minimal chiller overhead
        return round(1.10 + 0.012 * (wet_bulb_temp_c - 15.0), 3)

    @staticmethod
    def calculate_wue_site(wet_bulb_temp_c: float) -> float:
        """
        Calculates on-site evaporative cooling water loss in Liters/kWh.
        Spikes nonlinearly above 15°C when wet cooling towers engage.
        """
        if wet_bulb_temp_c <= 15.0:
            return 0.05  # Baseline closed-loop water loss
        return round(0.05 + 0.015 * ((wet_bulb_temp_c - 15.0) ** 2), 3)

    @classmethod
    def get_environment(cls, region: RegionName, hour: int) -> HourlyEnvironment:
        """Computes the full physical telemetry for a given region at a specific hour."""
        profile = REGIONS[region]

        # Diurnal phase: Hour 0 = 2:00 PM (peak heat/sun), Hour 12 = 2:00 AM (coolest night)
        diurnal_phase = (hour % 24 / 24.0) * 2 * math.pi

        # 1. Thermal wet-bulb curve
        wet_bulb = profile.base_temp_c + profile.temp_swing_c * math.cos(diurnal_phase)

        # 2. Grid carbon intensity factoring diurnal generation
        solar_effect = profile.solar_drop * max(0.0, math.cos(diurnal_phase))
        wind_effect = profile.wind_night_drop * max(0.0, -math.cos(diurnal_phase))
        carbon = max(10.0, profile.base_carbon - solar_effect - wind_effect)

        # 3. Cooling thermodynamics
        pue = cls.calculate_pue(wet_bulb)
        wue_site = cls.calculate_wue_site(wet_bulb)

        return HourlyEnvironment(
            region=region,
            hour=hour,
            wet_bulb_temp_c=round(wet_bulb, 2),
            carbon_intensity_g_kwh=round(carbon, 2),
            water_stress_multiplier=profile.water_stress,
            electricity_cost_usd_kwh=profile.electricity_cost,
            pue=pue,
            wue_site=wue_site,
        )