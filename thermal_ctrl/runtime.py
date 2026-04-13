from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from thermal_ctrl.artifacts import compare_summaries, create_artifact_dir, summarize_run, write_bundle
from thermal_ctrl.backends import HTTPAdminBatchBackend, HTTPAdminKVMigrationBackend, MockBatchBackend, MockKVMigrationBackend
from thermal_ctrl.config import load_config
from thermal_ctrl.controllers.policy import GPUControlState, PolicyEngine
from thermal_ctrl.interfaces import MetricsSnapshot
from thermal_ctrl.metrics import InMemoryMetricsSink, PrometheusMetricsSink
from thermal_ctrl.sensors import NvidiaSmiTemperatureSensor, SimulatedTemperatureSensor, SimulatedWorkloadSignal


@dataclass
class RunResult:
    config: dict
    samples: List[MetricsSnapshot]
    events: List[dict]
    summary: dict
    artifact_dir: Optional[str] = None


class EventRecorder:
    def __init__(self) -> None:
        self.events: List[dict] = []

    def emit(self, event: dict) -> None:
        self.events.append(event)


def build_runtime(config: dict):
    """Construct sensor, workload model, backends, and sinks from validated config."""
    sensor_cfg = config["sensor"]
    policy_cfg = config["policy"]
    backend_cfg = config["backends"]
    workload_cfg = config["workload"]

    if sensor_cfg["kind"] == "simulated":
        sensor = SimulatedTemperatureSensor(sensor_cfg, sensor_cfg["gpu_count"], config["seed"])
        workload = SimulatedWorkloadSignal(workload_cfg, config["seed"] + 101)
    elif sensor_cfg["kind"] == "nvidia-smi":
        sensor = NvidiaSmiTemperatureSensor(stale_after_s=sensor_cfg.get("stale_after_s", 3))
        workload = SimulatedWorkloadSignal(workload_cfg, config["seed"] + 101)
    else:
        raise ValueError(f"unsupported sensor kind: {sensor_cfg['kind']}")

    if backend_cfg["batch"]["kind"] == "mock":
        batch_backend = MockBatchBackend(policy_cfg["initial_batch_size"])
    elif backend_cfg["batch"]["kind"] == "http-admin":
        batch_backend = HTTPAdminBatchBackend(backend_cfg["batch"]["base_url"], backend_cfg["batch"]["timeout_s"])
    else:
        raise ValueError(f"unsupported batch backend kind: {backend_cfg['batch']['kind']}")

    if backend_cfg["kv_migration"]["kind"] == "mock":
        kv_backend = MockKVMigrationBackend()
    elif backend_cfg["kv_migration"]["kind"] == "http-admin":
        kv_backend = HTTPAdminKVMigrationBackend(
            backend_cfg["kv_migration"]["base_url"],
            backend_cfg["kv_migration"]["timeout_s"],
        )
    else:
        raise ValueError(f"unsupported kv backend kind: {backend_cfg['kv_migration']['kind']}")

    metrics = [InMemoryMetricsSink()]
    if config["metrics"].get("prometheus"):
        metrics.append(PrometheusMetricsSink(config["metrics"]["port"]))
    return sensor, workload, batch_backend, kv_backend, metrics


def run_simulation(config: dict, write_artifacts_flag: bool = True) -> RunResult:
    """Run one deterministic simulation or dry-run scenario."""
    sensor, workload_signal, batch_backend, kv_backend, metrics_sinks = build_runtime(config)
    policy = PolicyEngine(config["policy"])
    recorder = EventRecorder()
    state = GPUControlState(current_batch=config["policy"]["initial_batch_size"])
    active_batch = state.current_batch
    kv_relief_remaining = 0
    backend_failures = 0

    for step in range(0, int(config["duration_s"]), int(config["step_s"])):
        timestamp = float(step)
        workload = workload_signal.sample(timestamp, active_batch)
        if hasattr(sensor, "apply_simulation_inputs"):
            sensor.apply_simulation_inputs(workload.pressure_index, kv_relief_remaining > 0)
        readings = sensor.read(timestamp)
        reading = readings[0]
        decision = policy.evaluate(state, reading, workload)
        requested_batch = state.current_batch

        if decision is not None:
            requested_batch = decision.requested_batch
            if not decision.skip_backend:
                action = batch_backend.set_batch_size(
                    decision.requested_batch,
                    reason_code=decision.reason_code,
                    dry_run=config["policy"]["dry_run"],
                )
                backend_failures += 1 if action.backend_status == "error" else 0
                state.consecutive_backend_failures = (
                    state.consecutive_backend_failures + 1 if action.backend_status == "error" else 0
                )
                if action.backend_status != "error":
                    state.current_batch = max(
                        config["policy"]["min_batch_size"],
                        min(config["policy"]["max_batch_size"], action.applied_batch),
                    )
                    state.last_action_ts = timestamp
                    state.last_reason = decision.reason_code
                    policy.register_action(reading.gpu_id, timestamp)
                    if decision.kv_migration_pct > 0:
                        kv_backend.migrate(decision.kv_migration_pct, reason_code=decision.reason_code, dry_run=config["policy"]["dry_run"])
                        kv_relief_remaining = 4
                    recorder.emit(
                        {
                            "timestamp": timestamp,
                            "gpu_id": reading.gpu_id,
                            "action": decision.action,
                            "reason_code": decision.reason_code,
                            "requested_batch": decision.requested_batch,
                            "applied_batch": state.current_batch,
                            "backend_status": action.backend_status,
                            "backend_message": action.backend_message,
                        }
                    )
            else:
                recorder.emit(
                    {
                        "timestamp": timestamp,
                        "gpu_id": reading.gpu_id,
                        "action": decision.action,
                        "reason_code": decision.reason_code,
                        "requested_batch": decision.requested_batch,
                        "applied_batch": state.current_batch,
                        "backend_status": "skipped",
                        "backend_message": "policy hold",
                    }
                )

        active_batch = state.current_batch
        throttle_active = active_batch < config["policy"]["max_batch_size"]
        kv_relief_active = kv_relief_remaining > 0
        thermal_penalty = max(0.0, reading.celsius - config["policy"]["recover_temp_c"]) * config["workload"]["thermal_latency_gain"]
        queue_penalty = workload.queue_depth * config["workload"]["queue_sensitivity"]
        oscillation_penalty = 0.0
        if recorder.events and recorder.events[-1]["timestamp"] == timestamp and recorder.events[-1]["action"] in {"throttle", "recover"}:
            oscillation_penalty = config["workload"]["oscillation_penalty_ms"]

        latency_p50 = config["workload"]["base_latency_ms"] + queue_penalty * 0.35 + thermal_penalty * 0.08
        latency_p95 = latency_p50 + queue_penalty * 0.65 + thermal_penalty * 0.22 + oscillation_penalty
        latency_p99 = latency_p95 + queue_penalty * 0.5 + thermal_penalty * 0.45
        throughput = max(
            1.0,
            active_batch * config["workload"]["throughput_per_batch"] * max(0.35, 1 - max(0.0, reading.celsius - 86.0) * 0.06),
        )

        snapshot = MetricsSnapshot(
            timestamp=timestamp,
            gpu_temps={r.gpu_id: r.celsius for r in readings},
            workload_pressure=workload.pressure_index,
            queue_depth=round(workload.queue_depth, 3),
            active_batch_size=active_batch,
            requested_batch_size=requested_batch,
            thermal_throttle_active=throttle_active,
            kv_pressure=round(workload.kv_pressure, 3),
            kv_relief_active=kv_relief_active,
            latency_ms_p50=round(latency_p50, 2),
            latency_ms_p95=round(latency_p95, 2),
            latency_ms_p99=round(latency_p99, 2),
            throughput_toks_per_s=round(throughput, 2),
            backend_failures=backend_failures,
            sensor_stale=reading.stale,
        )
        for sink in metrics_sinks:
            sink.emit(snapshot)
        if kv_relief_remaining > 0:
            kv_relief_remaining -= 1

    memory_sink = next(sink for sink in metrics_sinks if isinstance(sink, InMemoryMetricsSink))
    summary = summarize_run(memory_sink.samples, recorder.events, config)
    artifact_dir = None
    if write_artifacts_flag:
        artifact_path = create_artifact_dir(config["artifacts_dir"], config["scenario_name"])
        write_bundle(artifact_path, config, memory_sink.samples, recorder.events, summary)
        artifact_dir = str(artifact_path)
    return RunResult(config=config, samples=memory_sink.samples, events=recorder.events, summary=summary, artifact_dir=artifact_dir)


def compare_runs(baseline_config_path: str, controlled_config_path: str, seed: Optional[int] = None) -> dict:
    """Run baseline and controlled scenarios and write a comparison bundle."""
    baseline_cfg = load_config(baseline_config_path)
    controlled_cfg = load_config(controlled_config_path)
    if seed is not None:
        baseline_cfg["seed"] = seed
        controlled_cfg["seed"] = seed
    baseline = run_simulation(baseline_cfg, write_artifacts_flag=False)
    controlled = run_simulation(controlled_cfg, write_artifacts_flag=False)
    comparison = compare_summaries(baseline.summary, controlled.summary)

    artifact_path = create_artifact_dir(controlled_cfg["artifacts_dir"], "compare")
    write_bundle(artifact_path / "baseline", baseline_cfg, baseline.samples, baseline.events, baseline.summary)
    write_bundle(
        artifact_path / "controlled",
        controlled_cfg,
        controlled.samples,
        controlled.events,
        controlled.summary,
        comparison=comparison,
    )
    (artifact_path / "comparison.md").write_text(
        "# Baseline vs controlled\n\n"
        f"- Bundle root: `{artifact_path}`\n"
        f"- Baseline bundle: `baseline/`\n"
        f"- Controlled bundle: `controlled/`\n"
        "- Inspect `baseline/summary.md`, `controlled/summary.md`, and `controlled/comparison.json` first.\n\n"
        f"- Baseline p99: `{baseline.summary['latency_ms_p99']} ms`\n"
        f"- Controlled p99: `{controlled.summary['latency_ms_p99']} ms`\n"
        f"- Delta p99: `{comparison['delta_latency_ms_p99']} ms`\n"
        f"- Delta time above threshold: `{comparison['delta_time_above_threshold_s']} s`\n"
        f"- Delta throughput: `{comparison['delta_throughput_toks_per_s']} toks/s`\n",
        encoding="utf-8",
    )
    return {
        "artifact_dir": str(artifact_path),
        "baseline": baseline.summary,
        "controlled": controlled.summary,
        "comparison": comparison,
    }
