import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schemas import Job
from src.simulator import ClusterSimulator

# Set styling for academic / technical publication
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
})


def load_jobs(filepath: str) -> list[Job]:
    df = pd.read_parquet(filepath)
    return [Job(**row) for row in df.to_dict(orient="records")]


def main():
    trace_path = "data/traces/cluster_workload.parquet"
    if not Path(trace_path).exists():
        print(f"Error: {trace_path} not found. Run scripts/ingest_traces.py first.")
        return

    jobs = load_jobs(trace_path)
    sim = ClusterSimulator(regional_capacity_kw=500.0)

    policies = ["greedy", "carbon_only", "water_only", "pareto"]
    metrics = {p: sim.run_simulation(jobs, policy=p) for p in policies}

    output_dir = Path("reports/figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # -------------------------------------------------------------
    # Figure 1: Carbon vs. Water Trade-off Space
    # -------------------------------------------------------------
    colors = {
        "greedy": "#e63946",       # Red
        "carbon_only": "#f4a261",  # Orange
        "water_only": "#457b9d",   # Steel Blue
        "pareto": "#2a9d8f",       # Teal Green
    }
    markers = {"greedy": "X", "carbon_only": "s", "water_only": "^", "pareto": "o"}

    for p in policies:
        m = metrics[p]
        ax1.scatter(
            m.total_carbon_kg,
            m.total_water_liters,
            color=colors[p],
            marker=markers[p],
            s=160,
            label=f"{p.upper()} ({m.sla_success_rate_pct:.1f}% SLA)",
            edgecolor="black",
            linewidth=1.2,
            zorder=4,
        )
        ax1.annotate(
            f" {p.upper()}",
            (m.total_carbon_kg, m.total_water_liters),
            textcoords="offset points",
            xytext=(8, 4),
            fontweight="bold",
            fontsize=9,
        )

    # Conceptual Pareto Trade-off Frontier curve between single-objective bounds
    frontier_x = sorted([metrics["carbon_only"].total_carbon_kg, metrics["pareto"].total_carbon_kg, metrics["water_only"].total_carbon_kg])
    frontier_y = [metrics["carbon_only"].total_water_liters, metrics["pareto"].total_water_liters, metrics["water_only"].total_water_liters]
    ax1.plot(frontier_x, frontier_y, linestyle="--", color="#6c757d", alpha=0.8, label="Pareto Frontier")

    ax1.set_title("Carbon vs. Water Consumption Trade-off")
    ax1.set_xlabel("Total Carbon Emissions (kg CO₂eq)")
    ax1.set_ylabel("Evaporative Cooling Water (Liters)")
    ax1.legend(loc="upper right", frameon=True)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # -------------------------------------------------------------
    # Figure 2: Regional Workload Placement Distribution
    # -------------------------------------------------------------
    regions = ["mumbai", "rajasthan", "stockholm", "oregon"]
    dist_data = {r: [metrics[p].regional_job_distribution.get(r, 0) for p in policies] for r in regions}
    df_dist = pd.DataFrame(dist_data, index=[p.upper() for p in policies])

    palette = ["#d62828", "#f77f00", "#003049", "#669bbc"]
    df_dist.plot(
        kind="bar",
        stacked=True,
        ax=ax2,
        color=palette,
        edgecolor="black",
        linewidth=0.8,
        width=0.6,
    )

    ax2.set_title("Regional Job Placement by Policy")
    ax2.set_xlabel("Scheduling Policy")
    ax2.set_ylabel("Total Jobs Executed")
    ax2.set_xticklabels([p.upper() for p in policies], rotation=0)
    ax2.legend(title="Data Center Region", loc="upper right", frameon=True)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    fig_path = output_dir / "pareto_benchmark_comparison.png"
    plt.savefig(fig_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Publication-ready comparison figure saved to: {fig_path}")


if __name__ == "__main__":
    main()