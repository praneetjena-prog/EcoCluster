import os
import random
import pandas as pd
from src.schemas import Job

def generate_sample_cluster_workload(num_jobs: int = 100) -> pd.DataFrame:
    """
    Simulates real-world Alibaba/Google cluster trace arrivals:
    a mix of short batch tasks and long distributed AI training jobs.
    """
    random.seed(42)
    workload = []

    for i in range(num_jobs):
        job_type = random.choices(["micro_batch", "llm_fine_tune", "distributed_pretrain"], weights=[0.6, 0.3, 0.1])[0]

        if job_type == "micro_batch":
            duration = random.randint(1, 3)
            energy_per_hr = random.choice([50.0, 80.0, 100.0])
            deadline_slack = random.randint(4, 8)
        elif job_type == "llm_fine_tune":
            duration = random.randint(4, 8)
            energy_per_hr = random.choice([150.0, 250.0, 350.0])
            deadline_slack = random.randint(8, 16)
        else:  # distributed_pretrain
            duration = random.randint(8, 16)
            energy_per_hr = random.choice([400.0, 600.0, 800.0])
            deadline_slack = random.randint(16, 32)

        arrival = random.randint(0, 48)  # Arrives within first 2 days
        deadline = arrival + duration + deadline_slack

        job = Job(
            job_id=f"TRACE-PAI-{i:04d}",
            arrival_time_hr=arrival,
            duration_hrs=duration,
            energy_per_hr_kwh=energy_per_hr,
            deadline_hrs=deadline,
            priority=random.randint(1, 5),
        )
        workload.append(job.model_dump())

    return pd.DataFrame(workload)

def main():
    os.makedirs("data/traces", exist_ok=True)
    df = generate_sample_cluster_workload(num_jobs=150)
    
    parquet_path = "data/traces/cluster_workload.parquet"
    csv_path = "data/traces/cluster_workload.csv"

    # Export to Parquet for fast columnar reading and CSV for inspection
    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    df.to_csv(csv_path, index=False)

    print(f"Successfully normalized and exported {len(df)} cluster trace jobs:")
    print(f"  -> Parquet: {parquet_path}")
    print(f"  -> CSV:     {csv_path}")
    print("\nSample records:")
    print(df.head(5)[["job_id", "arrival_time_hr", "duration_hrs", "energy_per_hr_kwh", "deadline_hrs"]])

if __name__ == "__main__":
    main()