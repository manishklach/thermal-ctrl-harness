# Validation Playbook

This repository does not claim hardware validation. This playbook exists so teams can validate the idea rigorously when hardware is available.

## Step 1: Validate the local harness
Run:

```bash
python -m thermal_ctrl compare --baseline configs/baseline.yaml --controlled configs/simulated.yaml --seed 7
python -m thermal_ctrl validate-env
```

This confirms the simulation path, artifacts, and environment checks are working.

## Step 2: Validate telemetry availability
- check that `nvidia-smi` exists
- inspect whether `memory.temp` is queryable
- decide whether shell-based telemetry is good enough or if you need NVML/DCGM

## Step 3: Validate the control surface
If you plan to use HTTP adapters, confirm:
- the endpoint exists
- the payload shape is correct
- the action is idempotent
- the service behavior under repeated calls is safe

Do not assume any upstream admin API from this repo alone.

## Step 4: Establish a baseline workload
Collect a baseline without any automated control:
- temp
- queue depth
- throughput
- p50/p95/p99
- batch or scheduler state

## Step 5: Introduce dry-run first
Run the controller in dry-run mode and confirm:
- reason codes make sense
- no action spam occurs
- stale telemetry is handled correctly
- the proposed actions line up with operator expectations

## Step 6: Controlled rollout
Only after the above:
- enable a real backend
- limit blast radius
- review every control action
- compare real traces against simulated expectations

## What would count as strong evidence
- reproducible thermal threshold crossings on your workload
- clear correlation between temperature and tail latency
- safe batch reductions that improve p99 without unacceptable throughput loss
- stable recovery without oscillation or endpoint failures
