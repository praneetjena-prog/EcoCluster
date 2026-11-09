# Geo-Distributed Carbon- and Water-Aware Cluster Scheduler

An intelligent trace-driven cluster orchestration engine that co-optimizes compute cost, execution latency, carbon emissions (CO2), and on-site evaporative cooling water consumption across geo-distributed data centers.

## Research Focus
Standard carbon-aware schedulers often shift workloads to solar-abundant desert facilities during peak daylight hours. While this minimizes grid carbon intensity, high ambient wet-bulb temperatures force evaporative cooling towers to consume millions of liters of scarce fresh water. This scheduler models the physical trade-offs between:
* Real-time grid carbon intensity (gCO2eq/kWh)
* Ambient wet-bulb temperature (Twb) and Power Usage Effectiveness (PUE)
* Water Usage Effectiveness (WUE, L/kWh) and regional Water Stress Index (WSI)
* Job deadlines and SLA constraints

## Core Architecture
* `src/schemas.py`: Pydantic data contracts for incoming job traces, regional weather/carbon environments, and scheduling allocations.
* `src/env_twin.py`: Environmental digital twin modeling thermodynamic cooling water loss and dynamic PUE.
* `src/simulator.py`: Discrete-event queue simulator replaying workloads from Google and Alibaba cluster traces.
* `src/schedulers/`: Baseline (Greedy, Carbon-Only, Water-Only) and Pareto-optimal multi-objective scheduling engines.
* `src/api.py`: FastAPI observability service for telemetry queries and simulation runs.