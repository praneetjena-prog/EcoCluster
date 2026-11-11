from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.schemas import Job, ScheduleDecision, RegionName, HourlyEnvironment
from src.env_twin import EnvironmentalDigitalTwin
from src.schedulers.baseline import BaselineSchedulers
from src.schedulers.pareto import ParetoEcoScheduler
from src.simulator import ClusterSimulator, SimulationMetrics

app = FastAPI(
    title="EcoCluster Telemetry & Pareto Engine",
    description="Carbon- and water-aware trace scheduling engine for geo-distributed clusters",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class BenchmarkRequest(BaseModel):
    jobs: List[Job]
    regional_capacity_kw: Optional[float] = 500.0
    weight_carbon: float = 1.5
    weight_water: float = 0.05
    weight_cost: float = 0.20


@app.get("/")
def root():
    return {
        "service": "Eco-Cluster Scheduler",
        "status": "operational",
        "dashboard_url": "http://127.0.0.1:8000/dashboard",
        "supported_regions": [r.value for r in RegionName],
        "endpoints": ["/dashboard", "/telemetry/environment", "/schedule/single", "/simulate/batch"],
    }


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="src/static/index.html not found")
    return FileResponse(index_file)


@app.get("/telemetry/environment", response_model=HourlyEnvironment)
def get_environment_telemetry(
    region: RegionName = Query(..., description="Target data center region"),
    hour: int = Query(0, ge=0, le=8760, description="Simulated hour (0-8760)"),
):
    """Returns dynamic wet-bulb temperature, carbon intensity, PUE, and WUE for a region."""
    return EnvironmentalDigitalTwin.get_environment(region, hour)


@app.post("/schedule/single")
def schedule_single_job(
    job: Job,
    weight_carbon: float = Query(1.5, ge=0.0, le=10.0),
    weight_water: float = Query(0.05, ge=0.0, le=2.0),
    weight_cost: float = Query(0.20, ge=0.0, le=5.0),
):
    """Evaluates all 4 policies side-by-side for a single job with live custom Pareto weights."""
    custom_pareto = ParetoEcoScheduler(
        weight_carbon=weight_carbon,
        weight_water=weight_water,
        weight_cost=weight_cost,
    )

    # Re-score candidates dynamically using custom weights
    from src.schedulers.baseline import get_all_valid_windows
    from src.env_twin import REGIONS

    candidates = get_all_valid_windows(job)
    if not candidates:
        raise HTTPException(status_code=422, detail="No valid window found that meets SLA deadline")

    for c in candidates:
        wsi = REGIONS[c.selected_region].water_stress
        c.pareto_score = round(
            (c.total_carbon_kg * weight_carbon)
            + (c.total_water_liters * wsi * weight_water)
            + (c.total_cost_usd * weight_cost),
            2,
        )

    frontier = custom_pareto.find_pareto_frontier(candidates)
    pareto_choice = min(frontier, key=lambda d: d.pareto_score)

    return {
        "greedy": BaselineSchedulers.greedy(job),
        "carbon_only": BaselineSchedulers.carbon_only(job),
        "water_only": BaselineSchedulers.water_only(job),
        "pareto": pareto_choice,
        "frontier_count": len(frontier),
        "total_windows": len(candidates),
    }


@app.post("/simulate/batch", response_model=List[SimulationMetrics])
def simulate_batch(request: BenchmarkRequest):
    """Runs a multi-job comparative trace simulation across all 4 policies under capacity caps."""
    custom_pareto = ParetoEcoScheduler(
        weight_carbon=request.weight_carbon,
        weight_water=request.weight_water,
        weight_cost=request.weight_cost,
    )
    sim = ClusterSimulator(
        regional_capacity_kw=request.regional_capacity_kw or 500.0,
        pareto_scheduler=custom_pareto,
    )
    policies = ["greedy", "carbon_only", "water_only", "pareto"]
    return [sim.run_simulation(request.jobs, policy=p) for p in policies]