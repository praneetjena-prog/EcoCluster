from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.schemas import Job, ScheduleDecision, RegionName, HourlyEnvironment
from src.env_twin import EnvironmentalDigitalTwin
from src.schedulers.baseline import BaselineSchedulers
from src.schedulers.pareto import ParetoEcoScheduler
from src.simulator import ClusterSimulator, SimulationMetrics

app = FastAPI(
    title="Eco-Cluster Scheduler API",
    description="Carbon- and water-aware trace scheduling engine for geo-distributed clusters",
    version="1.0.0",
)

pareto_engine = ParetoEcoScheduler()
simulator = ClusterSimulator(regional_capacity_kw=500.0, pareto_scheduler=pareto_engine)


class BenchmarkRequest(BaseModel):
    jobs: List[Job]
    regional_capacity_kw: Optional[float] = 500.0


@app.get("/")
def root():
    return {
        "service": "Eco-Cluster Scheduler",
        "status": "operational",
        "supported_regions": [r.value for r in RegionName],
        "endpoints": ["/telemetry/environment", "/schedule/single", "/simulate/batch"],
    }


@app.get("/telemetry/environment", response_model=HourlyEnvironment)
def get_environment_telemetry(
    region: RegionName = Query(..., description="Target data center region"),
    hour: int = Query(0, ge=0, le=8760, description="Simulated hour (0-8760)"),
):
    """Returns dynamic wet-bulb temperature, carbon intensity, PUE, and WUE for a region."""
    return EnvironmentalDigitalTwin.get_environment(region, hour)


@app.post("/schedule/single", response_model=ScheduleDecision)
def schedule_single_job(job: Job, policy: str = Query("pareto", enum=["greedy", "carbon_only", "water_only", "pareto"])):
    """Schedules an individual job using the selected ecological policy."""
    if policy == "greedy":
        return BaselineSchedulers.greedy(job)
    elif policy == "carbon_only":
        decision = BaselineSchedulers.carbon_only(job)
    elif policy == "water_only":
        decision = BaselineSchedulers.water_only(job)
    elif policy == "pareto":
        decision = pareto_engine.schedule(job)
    else:
        raise HTTPException(status_code=400, detail="Invalid policy specified")

    if not decision or not decision.sla_met:
        raise HTTPException(status_code=422, detail="No valid window found that meets SLA deadline")

    return decision


@app.post("/simulate/batch", response_model=List[SimulationMetrics])
def simulate_batch(request: BenchmarkRequest):
    """Runs a multi-job comparative trace simulation across all 4 policies under capacity caps."""
    sim = ClusterSimulator(
        regional_capacity_kw=request.regional_capacity_kw or 500.0,
        pareto_scheduler=pareto_engine,
    )
    
    policies = ["greedy", "carbon_only", "water_only", "pareto"]
    results = [sim.run_simulation(request.jobs, policy=p) for p in policies]
    return results