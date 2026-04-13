# Policy Notes

The control policy is designed to be understandable before it is ambitious.

## Why these controls exist
- **Hysteresis** keeps the controller from bouncing at the threshold edge.
- **Minimum dwell time** prevents repeated identical actions before the system has time to respond.
- **Cooldown** delays recovery so the controller does not immediately re-inflate batch size.
- **Max action budget** and **anti-flap hold** protect against oscillation during unstable periods.
- **Degraded hold mode** avoids issuing more actions when the backend is already failing.
- **Dry-run mode** lets operators inspect decisions before enabling real control.

## Tradeoffs
- Safer policies typically recover more slowly.
- Larger throttle steps reduce temperature faster but can hurt throughput.
- Stronger recovery increases utilization but raises oscillation risk.
- KV relief can help the model cool faster, but only if the real backend actually supports a safe pressure-relief mechanism.

## Recommended workflow
1. Start with simulation mode.
2. Tune for fewer oscillations before tuning for maximum throughput.
3. Validate the sensor and backend surface.
4. Run dry-run in your environment.
5. Only then consider a real backend rollout.
