# Simulation Model

This repo uses a transparent toy model. It is designed for explainability, not realism theater.

## What is modeled
- a workload burst raises a `pressure_index`
- pressure pushes modeled HBM temperature upward
- high temperature increases latency penalties
- throttling reduces active batch size
- KV migration provides temporary pressure relief
- hysteresis and dwell timers control recovery

## Temperature model
Each step computes a target temperature from:
- ambient temperature
- workload pressure
- cooling term
- optional KV relief term

The next temperature is:

`next_temp = inertia * current_temp + (1 - inertia) * target_temp + noise`

This keeps the system smooth enough to show delayed response without pretending to be a hardware thermal simulator.

## Latency model
Simulated latency is driven by:
- base latency
- queue depth penalty
- thermal penalty above the recovery region
- optional oscillation penalty when the controller keeps changing state

The resulting p50, p95, and p99 are model outputs for comparative reasoning only.

## Baseline vs controlled
- `configs/baseline.yaml` disables meaningful control and KV relief
- `configs/simulated.yaml` enables throttling, hysteresis, cooldown, and modeled relief

Run:

```bash
python -m thermal_ctrl compare --baseline configs/baseline.yaml --controlled configs/simulated.yaml --seed 7
```

## Determinism
Every run uses a seed. Same config plus same seed should produce the same summary and event sequence.

## What the model does not claim
- absolute thermal accuracy
- accurate HBM thermal limits for any real accelerator
- exact p99 numbers on a real cluster
- correctness of any specific admin API
