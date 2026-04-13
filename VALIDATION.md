# Validation Notes

The old `VALIDATION.md` has been replaced by a stricter playbook:

- [docs/validation_playbook.md](docs/validation_playbook.md)
- [docs/failure_modes.md](docs/failure_modes.md)
- `python -m thermal_ctrl validate-env`

This repo does not claim hardware validation. Use the playbook to separate:
- local simulation success
- environment readiness
- dry-run confidence
- real hardware evidence
