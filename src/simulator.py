from collections import defaultdict
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas import Job, ScheduleDecision, RegionName
from src.schedulers.baseline import BaselineSchedulers, evaluate_window, get_all_valid_windows
from src.schedulers.pareto import ParetoEcoScheduler


class SimulationMetrics(BaseModel):
    """Aggregate environmental and operational metrics for a simulation run."""
    policy_name: str
    total_jobs: int
    completed_jobs: int
    sla_violations: int
    sla_success_rate_pct: float
    total_energy_kwh: float
    total_carbon_kg: float
    total_water_liters: float
    total_cost_usd: float
    regional_job_distribution: Dict[str, int] = Field(default_factory=dict)


class ClusterSimulator:
    """
    Discrete-event trace simulator enforcing regional capacity constraints
    and evaluating ecological scheduling policies.
    """

    def __init__(
        self,
        regional_capacity_kw: float = 1000.0,  # Max concurrent power capacity per region
        pareto_scheduler: Optional[ParetoEcoScheduler] = None,
    ):
        self.capacity_per_region = regional_capacity_kw
        self.pareto = pareto_scheduler or ParetoEcoScheduler()

    def _check_capacity(
        self,
        region: RegionName,
        start_hour: int,
        duration: int,
        energy_rate: float,
        usage_grid: Dict[RegionName, Dict[int, float]],
    ) -> bool:
        """Verifies if the region has sufficient unreserved capacity across all execution hours."""
        for h in range(start_hour, start_hour + duration):
            if usage_grid[region][h] + energy_rate > self.capacity_per_region:
                return False
        return True

    def _reserve_capacity(
        self,
        region: RegionName,
        start_hour: int,
        duration: int,
        energy_rate: float,
        usage_grid: Dict[RegionName, Dict[int, float]],
    ) -> None:
        """Allocates compute capacity in the regional grid."""
        for h in range(start_hour, start_hour + duration):
            usage_grid[region][h] += energy_rate

    def _schedule_with_capacity(
        self,
        job: Job,
        policy: str,
        usage_grid: Dict[RegionName, Dict[int, float]],
    ) -> Optional[ScheduleDecision]:
        """Finds the best valid scheduling window that fits within current cluster capacity."""
        candidates = get_all_valid_windows(job)
        if not candidates:
            return None

        # Filter candidates by available hardware capacity
        available_candidates = [
            c for c in candidates
            if self._check_capacity(c.selected_region, c.start_hour, job.duration_hrs, job.energy_per_hr_kwh, usage_grid)
        ]

        if not available_candidates:
            return None

        if policy == "greedy":
            # Earliest start hour in local region (Mumbai fallback)
            local_cand = [c for c in available_candidates if c.selected_region == RegionName.MUMBAI]
            return min(local_cand or available_candidates, key=lambda c: c.start_hour)

        elif policy == "carbon_only":
            return min(available_candidates, key=lambda c: c.total_carbon_kg)

        elif policy == "water_only":
            return min(available_candidates, key=lambda c: c.total_water_liters)

        elif policy == "pareto":
            frontier = self.pareto.find_pareto_frontier(available_candidates)
            return min(frontier, key=lambda c: c.pareto_score)

        raise ValueError(f"Unknown policy: {policy}")

    def run_simulation(self, jobs: List[Job], policy: str = "pareto") -> SimulationMetrics:
        """Executes a trace-driven simulation for a batch of jobs under a designated policy."""
        # Timeline tracking: usage_grid[region][hour] = current kW load
        usage_grid: Dict[RegionName, Dict[int, float]] = {
            r: defaultdict(float) for r in RegionName
        }

        completed: List[ScheduleDecision] = []
        sla_violations = 0
        distribution: Dict[str, int] = defaultdict(int)

        # Sort arrivals chronologically
        sorted_jobs = sorted(jobs, key=lambda j: j.arrival_time_hr)

        for job in sorted_jobs:
            decision = self._schedule_with_capacity(job, policy, usage_grid)

            if decision and decision.sla_met:
                self._reserve_capacity(
                    decision.selected_region,
                    decision.start_hour,
                    job.duration_hrs,
                    job.energy_per_hr_kwh,
                    usage_grid,
                )
                completed.append(decision)
                distribution[decision.selected_region.value] += 1
            else:
                sla_violations += 1

        total_energy = sum(d.total_energy_kwh for d in completed)
        total_carbon = sum(d.total_carbon_kg for d in completed)
        total_water = sum(d.total_water_liters for d in completed)
        total_cost = sum(d.total_cost_usd for d in completed)

        total_jobs = len(jobs)
        success_pct = round((len(completed) / total_jobs) * 100.0, 2) if total_jobs > 0 else 0.0

        return SimulationMetrics(
            policy_name=policy,
            total_jobs=total_jobs,
            completed_jobs=len(completed),
            sla_violations=sla_violations,
            sla_success_rate_pct=success_pct,
            total_energy_kwh=round(total_energy, 2),
            total_carbon_kg=round(total_carbon, 2),
            total_water_liters=round(total_water, 2),
            total_cost_usd=round(total_cost, 2),
            regional_job_distribution=dict(distribution),
        )