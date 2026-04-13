from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "0.2.0",
    "mode": "simulation",
    "scenario_name": "controlled",
    "seed": 7,
    "artifacts_dir": "artifacts",
    "duration_s": 180,
    "step_s": 1,
    "sensor": {
        "kind": "simulated",
        "support_level": "mock-only",
        "gpu_count": 1,
        "noise_c": 0.4,
        "initial_temp_c": 72.0,
        "ambient_temp_c": 32.0,
        "rise_per_pressure": 1.7,
        "cooling_per_step": 0.35,
        "kv_relief_cooling": 0.6,
        "thermal_inertia": 0.82,
        "stale_after_s": 3,
    },
    "workload": {
        "kind": "simulated",
        "base_request_rate": 6.0,
        "burst_request_rate": 10.5,
        "burst_start_s": 35,
        "burst_duration_s": 80,
        "prompt_length_tokens": 131072,
        "decode_tokens": 768,
        "base_latency_ms": 1450.0,
        "queue_sensitivity": 110.0,
        "thermal_latency_gain": 320.0,
        "throughput_per_batch": 2.2,
        "kv_growth_rate": 0.018,
        "kv_relief_factor": 0.22,
        "oscillation_penalty_ms": 75.0,
    },
    "policy": {
        "throttle_temp_c": 85.0,
        "recover_temp_c": 80.0,
        "min_batch_size": 16,
        "max_batch_size": 256,
        "initial_batch_size": 256,
        "throttle_step_ratio": 0.5,
        "recover_step_ratio": 2.0,
        "min_dwell_s": 8,
        "cooldown_s": 10,
        "anti_flap_window_s": 30,
        "max_actions_per_window": 3,
        "kv_migration_pct": 0.12,
        "degraded_retries_before_hold": 2,
        "dry_run": False,
        "enable_kv_migration": True,
    },
    "backends": {
        "batch": {
            "kind": "mock",
            "support_level": "mock-only",
            "base_url": "http://localhost:8000/v1/admin",
            "timeout_s": 1.0,
            "experimental_note": "HTTP admin endpoints are assumed adapter targets, not hardware-validated upstream contracts.",
        },
        "kv_migration": {
            "kind": "mock",
            "support_level": "mock-only",
            "base_url": "http://localhost:8000/v1/admin",
            "timeout_s": 1.0,
            "experimental_note": "KV migration is modeled as a pressure-relief hook; real implementations will vary.",
        },
    },
    "metrics": {
        "prometheus": False,
        "port": 9091,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None) -> Dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if path is None:
        return validate_config(config)
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return validate_config(_deep_merge(config, raw))


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    policy = config["policy"]
    sensor = config["sensor"]
    workload = config["workload"]

    if policy["min_batch_size"] <= 0:
        raise ValueError("policy.min_batch_size must be positive")
    if policy["max_batch_size"] < policy["min_batch_size"]:
        raise ValueError("policy.max_batch_size must be >= min_batch_size")
    if policy["initial_batch_size"] < policy["min_batch_size"] or policy["initial_batch_size"] > policy["max_batch_size"]:
        raise ValueError("policy.initial_batch_size must be within [min_batch_size, max_batch_size]")
    if policy["recover_temp_c"] >= policy["throttle_temp_c"]:
        raise ValueError("policy.recover_temp_c must be below policy.throttle_temp_c")
    if config["duration_s"] <= 0 or config["step_s"] <= 0:
        raise ValueError("duration_s and step_s must be positive")
    if sensor["gpu_count"] <= 0:
        raise ValueError("sensor.gpu_count must be positive")
    if workload["throughput_per_batch"] <= 0:
        raise ValueError("workload.throughput_per_batch must be positive")
    return config
