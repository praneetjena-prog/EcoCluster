from typing import List, Optional
from src.schemas import Job, ScheduleDecision, RegionName
from src.env_twin import EnvironmentalDigitalTwin, REGIONS


def evaluate_window(job: Job, region: RegionName, start_hour: int) -> ScheduleDecision:
    """Calculates the exact energy, carbon, water, cost, and Pareto score for a job executed in a specific window."""
    finish_hour = start_hour + job.duration_hrs
    sla_met = finish_hour <= job.deadline_hrs

    total_energy_kwh = 0.0
    total_carbon_kg = 0.0
    total_water_liters = 0.0
    total_cost_usd = 0.0

    profile = REGIONS[region]

    for h in range(start_hour, finish_hour):
        env = EnvironmentalDigitalTwin.get_environment(region, h)
        hourly_energy = job.energy_per_hr_kwh * env.pue

        total_energy_kwh += hourly_energy
        total_carbon_kg += (hourly_energy * env.carbon_intensity_g_kwh) / 1000.0
        total_water_liters += job.energy_per_hr_kwh * env.wue_site
        total_cost_usd += hourly_energy * env.electricity_cost_usd_kwh

    # Multi-objective penalty: CO2 + drought-weighted water + cost
    pareto_score = (
        (total_carbon_kg * 1.5)
        + (total_water_liters * profile.water_stress * 0.05)
        + (total_cost_usd * 0.2)
    )

    return ScheduleDecision(
        job_id=job.job_id,
        selected_region=region,
        start_hour=start_hour,
        finish_hour=finish_hour,
        sla_met=sla_met,
        total_energy_kwh=round(total_energy_kwh, 2),
        total_carbon_kg=round(total_carbon_kg, 2),
        total_water_liters=round(total_water_liters, 2),
        total_cost_usd=round(total_cost_usd, 2),
        pareto_score=round(pareto_score, 2),
    )


def get_all_valid_windows(job: Job) -> List[ScheduleDecision]:
    """Generates all spatio-temporal options that satisfy the job's SLA deadline."""
    decisions = []
    max_start = job.deadline_hrs - job.duration_hrs

    for region in RegionName:
        for start_hr in range(job.arrival_time_hr, max_start + 1):
            decisions.append(evaluate_window(job, region, start_hr))

    return decisions


class BaselineSchedulers:
    """Standard baseline policies used for comparative evaluation."""

    @staticmethod
    def greedy(job: Job, default_region: RegionName = RegionName.MUMBAI) -> ScheduleDecision:
        """Baseline 1: Runs immediately upon arrival at the local default data center."""
        return evaluate_window(job, default_region, start_hour=job.arrival_time_hr)

    @staticmethod
    def carbon_only(job: Job) -> Optional[ScheduleDecision]:
        """Baseline 2: Minimizes total CO2 emissions regardless of cooling water usage."""
        windows = get_all_valid_windows(job)
        return min(windows, key=lambda d: d.total_carbon_kg) if windows else None

    @staticmethod
    def water_only(job: Job) -> Optional[ScheduleDecision]:
        """Baseline 3: Minimizes total water consumption regardless of grid carbon."""
        windows = get_all_valid_windows(job)
        return min(windows, key=lambda d: d.total_water_liters) if windows else None