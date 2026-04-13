#!/usr/bin/env python3
"""Compatibility wrapper for the original entrypoint."""

from thermal_ctrl.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["dry-run", "--config", "configs/config.yaml"]))
