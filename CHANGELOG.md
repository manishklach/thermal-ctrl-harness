# Changelog

## v0.2.1
- hardened README and docs for reviewer accuracy and command correctness
- clarified that a `404` from `validate-env` means the service responded but the prototype control endpoint is still unconfirmed
- added a sharper canonical local review path with explicit install, run, and artifact inspection steps
- added `Known Limitations` to the README
- added small artifact-bundle README files to improve inspection and reviewability

## v0.2.0
- reframed the repo as a thermal-control simulation and validation harness
- added a first-class CLI for simulate, compare, dry-run, and validate-env
- introduced adapter boundaries for sensors and backends
- replaced the simple threshold toggle with a policy engine that includes hysteresis, dwell, cooldown, anti-flap logic, and degraded hold mode
- added deterministic artifact generation with config, events, CSV, summary, and SVG plots
- expanded documentation around architecture, simulation assumptions, failure modes, and validation
- upgraded tests to cover control policy, runtime determinism, config validation, and artifact generation
