from __future__ import annotations

import argparse
import json
import shutil
import subprocess

import requests

from thermal_ctrl import __version__
from thermal_ctrl.config import load_config
from thermal_ctrl.runtime import compare_runs, run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thermal_ctrl", description="Thermal-control simulation and validation harness")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim = subparsers.add_parser("simulate", help="Run a deterministic simulation scenario")
    sim.add_argument("--config", default="configs/simulated.yaml")
    sim.add_argument("--seed", type=int, default=None)

    compare = subparsers.add_parser("compare", help="Compare baseline and controlled scenarios")
    compare.add_argument("--baseline", default="configs/baseline.yaml")
    compare.add_argument("--controlled", default="configs/simulated.yaml")
    compare.add_argument("--seed", type=int, default=None)

    validate = subparsers.add_parser("validate-env", help="Inspect the current environment")
    validate.add_argument("--admin-url", default="http://localhost:8000/v1/admin")

    dry_run = subparsers.add_parser("dry-run", help="Run the configured scenario with dry-run actions")
    dry_run.add_argument("--config", default="configs/config.yaml")
    dry_run.add_argument("--seed", type=int, default=None)
    return parser


def command_simulate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.seed is not None:
        config["seed"] = args.seed
    result = run_simulation(config)
    print(json.dumps({"artifact_dir": result.artifact_dir, "summary": result.summary}, indent=2))
    return 0


def command_compare(args: argparse.Namespace) -> int:
    result = compare_runs(args.baseline, args.controlled, seed=args.seed)
    print(json.dumps(result, indent=2))
    return 0


def _available_nvidia_query_fields() -> dict:
    if shutil.which("nvidia-smi") is None:
        return {"status": "unavailable", "message": "nvidia-smi not found on PATH"}
    try:
        query_help = subprocess.check_output(["nvidia-smi", "--help-query-gpu"], stderr=subprocess.STDOUT, timeout=2).decode(
            "utf-8",
            errors="replace",
        )
        return {
            "status": "available",
            "memory_temp_field": "memory.temp" in query_help,
            "message": "nvidia-smi query help inspected",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _check_admin_endpoint(admin_url: str) -> dict:
    try:
        response = requests.get(f"{admin_url}/batch", timeout=1)
        if response.status_code == 200:
            status = "responding"
            note = "The endpoint responded successfully. Treat it as unvalidated until you confirm payload semantics in your own serving stack."
        elif response.status_code == 404:
            status = "http_reachable_endpoint_unconfirmed"
            note = "A service is reachable, but `/batch` was not confirmed at this path. This repo does not assume upstream admin endpoints exist."
        else:
            status = "http_reachable_unvalidated"
            note = "A service responded, but the control endpoint contract is still unvalidated for this repo."
        return {
            "status": status,
            "http_status": response.status_code,
            "note": note,
        }
    except Exception as exc:
        return {"status": "unreachable", "message": str(exc)}


def command_validate_env(args: argparse.Namespace) -> int:
    report = {
        "nvidia_smi": _available_nvidia_query_fields(),
        "admin_endpoint": _check_admin_endpoint(args.admin_url),
        "support_summary": {
            "simulation_mode": "supported",
            "hardware_validation": "not implied; use docs/validation_playbook.md",
            "production_backend": "experimental until validated against your serving stack",
        },
    }
    print(json.dumps(report, indent=2))
    return 0


def command_dry_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.seed is not None:
        config["seed"] = args.seed
    config["policy"]["dry_run"] = True
    result = run_simulation(config)
    print(json.dumps({"artifact_dir": result.artifact_dir, "summary": result.summary}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "simulate":
        return command_simulate(args)
    if args.command == "compare":
        return command_compare(args)
    if args.command == "validate-env":
        return command_validate_env(args)
    if args.command == "dry-run":
        return command_dry_run(args)
    parser.error(f"unknown command: {args.command}")
    return 2
