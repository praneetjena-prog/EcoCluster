import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schemas import Job
from src.simulator import ClusterSimulator

def load_jobs_from_parquet(filepath: str) -> list[Job]:
    df = pd.read_parquet(filepath)
    return [Job(**row) for row in df.to_dict(orient="records")]

def main():
    trace_path = "data/traces/cluster_workload.parquet"
    if not Path(trace_path).exists():
        print(f"Error: {trace_path} not found. Run scripts/ingest_traces.py first.")
        return

    jobs = load_jobs_from_parquet(trace_path)
    print(f"Loaded {len(jobs)} jobs from {trace_path}\n")

    # Set 500 kW concurrent capacity per region
    sim = ClusterSimulator(regional_capacity_kw=500.0)
    policies = ["greedy", "carbon_only", "water_only", "pareto"]

    results = []
    print("Executing trace simulations across 4 policies...")
    for policy in policies:
        metric = sim.run_simulation(jobs, policy=policy)
        results.append(metric)

    # Use greedy baseline as 100% reference point
    baseline = results[0]

    print("\n" + "=" * 110)
    print(f"{'POLICY':<14} | {'SLA MET':<8} | {'CO2 (kg)':<12} | {'WATER (L)':<12} | {'COST ($)':<10} | {'CO2 SAVED':<11} | {'WATER SAVED':<11}")
    print("=" * 110)

    for r in results:
        co2_saved = f"{(1.0 - r.total_carbon_kg / baseline.total_carbon_kg) * 100:.1f}%" if baseline.total_carbon_kg else "0.0%"
        water_saved = f"{(1.0 - r.total_water_liters / baseline.total_water_liters) * 100:.1f}%" if baseline.total_water_liters else "0.0%"
        
        print(
            f"{r.policy_name.upper():<14} | "
            f"{r.sla_success_rate_pct:>6.1f}% | "
            f"{r.total_carbon_kg:>12,.2f} | "
            f"{r.total_water_liters:>12,.2f} | "
            f"{r.total_cost_usd:>10,.2f} | "
            f"{co2_saved:>11} | "
            f"{water_saved:>11}"
        )
    print("=" * 110)

    print("\n--- REGIONAL JOB DISTRIBUTION ---")
    for r in results:
        print(f"{r.policy_name.upper():<14}: {r.regional_job_distribution}")

if __name__ == "__main__":
    main()