from pathlib import Path

import pytest

from thermal_ctrl.config import load_config, validate_config
from thermal_ctrl.controllers.policy import GPUControlState, PolicyEngine
from thermal_ctrl.interfaces import TemperatureReading, WorkloadSnapshot
from thermal_ctrl.runtime import build_runtime, compare_runs, run_simulation


def make_workload(timestamp: float = 0.0, pressure_index: float = 1.0) -> WorkloadSnapshot:
    return WorkloadSnapshot(
        timestamp=timestamp,
        request_rate=8.0,
        queue_depth=4.0,
        active_batch_size=256,
        kv_pressure=0.5,
        pressure_index=pressure_index,
    )


def test_threshold_crossing_and_recovery():
    config = load_config("configs/simulated.yaml")
    engine = PolicyEngine(config["policy"])
    state = GPUControlState(current_batch=256)

    decision = engine.evaluate(
        state,
        TemperatureReading(gpu_id=0, celsius=86.0, timestamp=20.0),
        make_workload(timestamp=20.0),
    )
    assert decision is not None
    assert decision.action == "throttle"
    assert decision.requested_batch == 128

    state.current_batch = 128
    state.last_action_ts = 20.0

    decision = engine.evaluate(
        state,
        TemperatureReading(gpu_id=0, celsius=79.0, timestamp=35.0),
        make_workload(timestamp=35.0, pressure_index=0.3),
    )
    assert decision is not None
    assert decision.action == "recover"
    assert decision.requested_batch == 256


def test_anti_flap_behavior_holds_when_budget_exhausted():
    config = load_config("configs/simulated.yaml")
    engine = PolicyEngine(config["policy"])
    state = GPUControlState(current_batch=64)
    engine.register_action(0, 0.0)
    engine.register_action(0, 5.0)
    engine.register_action(0, 10.0)
    decision = engine.evaluate(
        state,
        TemperatureReading(gpu_id=0, celsius=86.0, timestamp=15.0),
        make_workload(timestamp=15.0, pressure_index=1.1),
    )
    assert decision is not None
    assert decision.reason_code == "anti_flap_hold"
    assert decision.skip_backend


def test_degraded_backend_hold_after_failures():
    config = load_config("configs/simulated.yaml")
    engine = PolicyEngine(config["policy"])
    state = GPUControlState(current_batch=64, consecutive_backend_failures=2)
    decision = engine.evaluate(
        state,
        TemperatureReading(gpu_id=0, celsius=88.0, timestamp=12.0),
        make_workload(timestamp=12.0),
    )
    assert decision is not None
    assert decision.reason_code == "degraded_backend_hold"
    assert decision.skip_backend


def test_deterministic_seeded_simulation():
    config = load_config("configs/simulated.yaml")
    config["seed"] = 11
    result_one = run_simulation(config, write_artifacts_flag=False)
    result_two = run_simulation(config, write_artifacts_flag=False)
    assert result_one.summary == result_two.summary
    assert result_one.events == result_two.events


def test_artifact_bundle_generation(tmp_path: Path):
    config = load_config("configs/simulated.yaml")
    config["artifacts_dir"] = str(tmp_path)
    result = run_simulation(config, write_artifacts_flag=True)
    artifact_dir = Path(result.artifact_dir)
    assert (artifact_dir / "config.json").exists()
    assert (artifact_dir / "events.json").exists()
    assert (artifact_dir / "summary.md").exists()
    assert (artifact_dir / "timeseries.svg").exists()


def test_config_validation_rejects_bad_thresholds():
    config = load_config("configs/simulated.yaml")
    config["policy"]["recover_temp_c"] = 90
    with pytest.raises(ValueError):
        validate_config(config)


def test_adapter_selection():
    config = load_config("configs/simulated.yaml")
    sensor, workload, batch_backend, kv_backend, metrics = build_runtime(config)
    assert sensor.kind == "simulated"
    assert workload.kind == "simulated"
    assert batch_backend.kind == "mock"
    assert kv_backend.kind == "mock"
    assert metrics[0].kind == "memory"


def test_metrics_emission_has_samples():
    config = load_config("configs/simulated.yaml")
    result = run_simulation(config, write_artifacts_flag=False)
    assert result.samples
    assert result.samples[0].active_batch_size > 0


def test_compare_runs_creates_comparison_bundle(tmp_path: Path):
    result = compare_runs("configs/baseline.yaml", "configs/simulated.yaml", seed=7)
    assert "comparison" in result
    assert "delta_latency_ms_p99" in result["comparison"]


def test_property_no_negative_batch_sizes():
    config = load_config("configs/simulated.yaml")
    result = run_simulation(config, write_artifacts_flag=False)
    assert all(sample.active_batch_size >= 0 for sample in result.samples)


def test_property_no_recovery_above_configured_max():
    config = load_config("configs/simulated.yaml")
    result = run_simulation(config, write_artifacts_flag=False)
    assert all(sample.active_batch_size <= config["policy"]["max_batch_size"] for sample in result.samples)


def test_property_no_repeated_identical_actions_during_dwell():
    config = load_config("configs/simulated.yaml")
    result = run_simulation(config, write_artifacts_flag=False)
    throttle_events = [event for event in result.events if event["action"] == "throttle"]
    for previous, current in zip(throttle_events, throttle_events[1:]):
        assert current["timestamp"] - previous["timestamp"] >= config["policy"]["min_dwell_s"]
