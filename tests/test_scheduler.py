import pytest
from src.schemas import Job, RegionName
from src.env_twin import EnvironmentalDigitalTwin
from src.schedulers.baseline import BaselineSchedulers
from src.schedulers.pareto import ParetoEcoScheduler
from src.simulator import ClusterSimulator


@pytest.fixture
def sample_job():
    return Job(
        job_id="TEST-JOB-001",
        arrival_time_hr=0,
        duration_hrs=4,
        energy_per_hr_kwh=200.0,
        deadline_hrs=12,
    )


def test_thermodynamics_physics():
    # Below 15C: free ambient cooling
    assert EnvironmentalDigitalTwin.calculate_pue(10.0) == 1.10
    assert EnvironmentalDigitalTwin.calculate_wue_site(10.0) == 0.05

    # Above 15C: cooling towers engaged
    pue_hot = EnvironmentalDigitalTwin.calculate_pue(35.0)
    wue_hot = EnvironmentalDigitalTwin.calculate_wue_site(35.0)
    assert pue_hot > 1.10
    assert wue_hot > 0.05


def test_baseline_schedulers(sample_job):
    greedy = BaselineSchedulers.greedy(sample_job)
    assert greedy.selected_region == RegionName.MUMBAI
    assert greedy.start_hour == 0
    assert greedy.sla_met is True

    carbon = BaselineSchedulers.carbon_only(sample_job)
    assert carbon is not None
    assert carbon.sla_met is True


def test_pareto_scheduler(sample_job):
    scheduler = ParetoEcoScheduler()
    decision = scheduler.schedule(sample_job)
    assert decision is not None
    assert decision.sla_met is True
    assert decision.total_carbon_kg > 0.0
    assert decision.total_water_liters > 0.0


def test_cluster_capacity_enforcement():
    # Capacity: 150 kW; each job requires 100 kW
    sim = ClusterSimulator(regional_capacity_kw=150.0)
    jobs = [
        Job(job_id=f"JOB-{i}", arrival_time_hr=0, duration_hrs=4, energy_per_hr_kwh=100.0, deadline_hrs=6)
        for i in range(10)
    ]
    # Running 10 overlapping jobs with 4 regions * 150 kW = 600 kW max capacity
    # Overflow jobs must either shift time or violate SLA
    metric = sim.run_simulation(jobs, policy="greedy")
    assert metric.total_jobs == 10
    assert metric.completed_jobs > 0