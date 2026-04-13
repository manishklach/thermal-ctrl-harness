# Architecture

The v0.2.1 architecture is built around explicit interfaces so the repo is useful before hardware validation and adaptable afterward.

## Components
- **TemperatureSensor**
  Produces GPU temperature readings. Current implementations are `SimulatedTemperatureSensor` and `NvidiaSmiTemperatureSensor`.
- **WorkloadSignal**
  Produces modeled request rate, queue depth, and pressure index. The default is a transparent toy workload model.
- **PolicyEngine**
  Applies hysteresis, dwell timers, cooldowns, anti-flap protection, and degraded mode logic.
- **BatchControllerBackend**
  Applies batch-size changes. The repo ships mock and experimental HTTP adapters.
- **KVMigrationBackend**
  Models or applies a KV pressure-relief action.
- **MetricsSink**
  Records in-memory metrics for artifact generation and can optionally export Prometheus metrics.
- **Artifact Writer**
  Emits config, events, summaries, CSV, and SVG charts for every run.

## Why adapters matter
The original prototype was tightly coupled to assumed admin endpoints. In v0.2.1 the adapter boundary makes the trust model explicit:
- you can exercise the control loop entirely with mocks
- you can swap in `nvidia-smi` without changing policy logic
- you can experiment with HTTP control surfaces without claiming they are validated upstream APIs

## Policy controls
- `throttle_temp_c` and `recover_temp_c` define hysteresis
- `min_dwell_s` prevents repeated identical actions in rapid succession
- `cooldown_s` delays recovery after a throttle event
- `max_actions_per_window` and `anti_flap_window_s` prevent thrash
- `degraded_retries_before_hold` stops control actions after repeated backend failures
- `throttle_step_ratio` and `recover_step_ratio` bound step sizes

## Data flow
![Architecture](architecture.svg)

## Production intent
The architecture is meant to be production-possible, not production-proven. The simulated path should be enough to review policy quality. Real deployment should only happen after environment validation plus workload-specific testing.

In particular, the checked-in HTTP adapters are experimental integration points, not validated claims about any upstream serving API.
