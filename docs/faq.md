# FAQ

## Do I need an H100/H200 to use this repo?
No. The primary workflow in v0.2.1 is the simulation and validation harness, which runs locally without target hardware.

## Is this hardware-validated?
No. The repo explicitly separates implemented behavior, simulated behavior, and hardware validation that still needs to happen.

## Are the vLLM admin endpoints real?
Treat them as experimental adapter targets. This repo does not claim that any specific upstream endpoint is stable, present, or validated in your deployment.

## What exactly is simulated?
Temperature rise, queue pressure, batch control, KV-relief effects, recovery hysteresis, and latency degradation are all modeled by a transparent toy system.

## Why should I trust the results?
Trust the repo for reproducibility and systems reasoning, not for unvalidated hardware claims. The value is in explicit assumptions, deterministic runs, and inspectable artifacts.

## How would I adapt this to a real cluster?
Start by validating telemetry and backend semantics with `python -m thermal_ctrl validate-env`, then replace mock adapters one boundary at a time and follow `docs/validation_playbook.md`.

## What does a 404 in `validate-env` mean?
It means an HTTP service answered, but the control endpoint path used by this prototype was not confirmed there. That is a compatibility signal, not a successful validation.
