from typing import List, Optional
from src.schemas import Job, ScheduleDecision
from src.schedulers.baseline import get_all_valid_windows


class ParetoEcoScheduler:
    """
    Multi-objective scheduler co-optimizing carbon emissions,
    drought-weighted water consumption, electricity cost, and queuing latency.
    """

    def __init__(
        self,
        weight_carbon: float = 1.5,
        weight_water: float = 0.05,
        weight_cost: float = 0.20,
        weight_wait_penalty: float = 0.02,
    ):
        self.w_carbon = weight_carbon
        self.w_water = weight_water
        self.w_cost = weight_cost
        self.w_wait = weight_wait_penalty

    def find_pareto_frontier(self, decisions: List[ScheduleDecision]) -> List[ScheduleDecision]:
        """
        Extracts the non-dominated (Pareto-optimal) subset from all candidates.
        A candidate is dominated if another candidate is strictly better or equal in all metrics.
        """
        frontier = []
        for candidate in decisions:
            is_dominated = False
            for other in decisions:
                if other == candidate:
                    continue
                # Domination test: other is at least as good in all, and strictly better in at least one
                strictly_better_in_one = (
                    other.total_carbon_kg < candidate.total_carbon_kg
                    or other.total_water_liters < candidate.total_water_liters
                    or other.total_cost_usd < candidate.total_cost_usd
                    or (other.start_hour - other.job_id.count("")) < (candidate.start_hour - candidate.job_id.count(""))
                )
                not_worse_in_any = (
                    other.total_carbon_kg <= candidate.total_carbon_kg
                    and other.total_water_liters <= candidate.total_water_liters
                    and other.total_cost_usd <= candidate.total_cost_usd
                )

                if not_worse_in_any and strictly_better_in_one:
                    is_dominated = True
                    break

            if not is_dominated:
                frontier.append(candidate)

        return frontier if frontier else decisions

    def schedule(self, job: Job) -> Optional[ScheduleDecision]:
        """Evaluates all valid windows and selects the best Pareto-optimal trade-off."""
        candidates = get_all_valid_windows(job)
        if not candidates:
            return None

        # Filter down to the Pareto-optimal frontier
        frontier = self.find_pareto_frontier(candidates)

        # Select candidate with minimal composite penalty score
        best_decision = min(frontier, key=lambda d: d.pareto_score)
        return best_decision