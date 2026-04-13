# Failure Modes

This harness is useful partly because it makes failure modes easy to discuss before rollout.

## Noisy temperature readings
- **Symptom**: repeated threshold crossings with inconsistent control actions
- **Likely cause**: sensor jitter or low-quality telemetry
- **Mitigation**: increase dwell time, add smoothing, validate sensor quality
- **Observe via**: event log churn, oscillation count, jitter in `gpu_hbm_temp_celsius`

## Missing NVML or unsupported `nvidia-smi` fields
- **Symptom**: stale or zero temperature readings
- **Likely cause**: `memory.temp` unavailable, tool missing, unsupported platform
- **Mitigation**: use `validate-env`, switch to simulated mode, add a validated adapter
- **Observe via**: stale sensor flag, environment validation output

## Fake correlation between temp and latency
- **Symptom**: the model suggests gains that do not appear in production
- **Likely cause**: queueing or scheduler effects dominate thermal behavior
- **Mitigation**: treat simulation as a hypothesis generator, not proof
- **Observe via**: compare simulated artifacts against real traces before rollout

## Too-aggressive throttling hurts throughput
- **Symptom**: p99 improves but average throughput collapses
- **Likely cause**: throttle ratio too large or cooldown too long
- **Mitigation**: reduce step-down severity, shorten cooldown carefully
- **Observe via**: comparison report deltas, average batch size, throughput stats

## Multi-GPU coordination issues
- **Symptom**: one device throttles repeatedly while others stay cool
- **Likely cause**: per-GPU hotspots, uneven sharding, no coordination layer
- **Mitigation**: add multi-GPU policies before production use
- **Observe via**: per-GPU temps, per-device event logs

## Backend endpoint 404/500/timeouts
- **Symptom**: actions requested but not applied
- **Likely cause**: experimental adapter mismatch or service instability
- **Mitigation**: use dry-run or mock backends until the endpoint contract is validated
- **Observe via**: backend failure counter, event log `backend_status=error`

## Clock skew or stale sensor reads
- **Symptom**: control reacts to old temperatures
- **Likely cause**: delayed scrape or stale telemetry cache
- **Mitigation**: hold state on stale reads, expose sensor freshness in metrics
- **Observe via**: `sensor_stale`, hold events with `stale_sensor_reading`

## Poor recovery tuning causes oscillation
- **Symptom**: repeated throttle and recover events
- **Likely cause**: recover threshold too high or cooldown too short
- **Mitigation**: widen hysteresis, increase dwell and cooldown
- **Observe via**: oscillation count, event timeline

## Simulated success does not translate to real hardware
- **Symptom**: nice artifacts, disappointing cluster behavior
- **Likely cause**: model simplifications or unvalidated assumptions
- **Mitigation**: follow the validation playbook and treat this repo as an RFC harness
- **Observe via**: divergence between simulated and measured traces
