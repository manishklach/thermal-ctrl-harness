from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Optional

from thermal_ctrl.controllers.policy import count_oscillations
from thermal_ctrl.interfaces import MetricsSnapshot


def create_artifact_dir(root: str | Path, scenario_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = Path(root) / f"{timestamp}-{scenario_name}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_bundle(
    artifact_dir: str | Path,
    config: dict,
    samples: Iterable[MetricsSnapshot],
    events: Iterable[dict],
    summary: dict,
    comparison: Optional[dict] = None,
) -> Path:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    samples = list(samples)
    events = list(events)

    (artifact_path / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (artifact_path / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    (artifact_path / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if comparison is not None:
        (artifact_path / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    with (artifact_path / "timeseries.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp",
                "gpu_0_temp_c",
                "pressure",
                "queue_depth",
                "active_batch_size",
                "requested_batch_size",
                "thermal_throttle_active",
                "latency_p50_ms",
                "latency_p95_ms",
                "latency_p99_ms",
                "throughput_toks_per_s",
            ]
        )
        for sample in samples:
            writer.writerow(
                [
                    sample.timestamp,
                    sample.gpu_temps.get(0, 0.0),
                    sample.workload_pressure,
                    sample.queue_depth,
                    sample.active_batch_size,
                    sample.requested_batch_size,
                    int(sample.thermal_throttle_active),
                    sample.latency_ms_p50,
                    sample.latency_ms_p95,
                    sample.latency_ms_p99,
                    sample.throughput_toks_per_s,
                ]
            )

    (artifact_path / "timeseries.svg").write_text(build_chart_svg(samples), encoding="utf-8")
    (artifact_path / "summary.md").write_text(build_summary_markdown(summary, comparison), encoding="utf-8")
    return artifact_path


def summarize_run(samples: Iterable[MetricsSnapshot], events: Iterable[dict], config: dict) -> dict:
    samples = list(samples)
    events = list(events)
    if not samples:
        raise ValueError("cannot summarize an empty run")
    p50 = mean(sample.latency_ms_p50 for sample in samples)
    p95 = mean(sample.latency_ms_p95 for sample in samples)
    p99 = mean(sample.latency_ms_p99 for sample in samples)
    avg_batch = mean(sample.active_batch_size for sample in samples)
    time_above = sum(1 for sample in samples if max(sample.gpu_temps.values()) >= config["policy"]["throttle_temp_c"]) * config["step_s"]
    return {
        "scenario_name": config["scenario_name"],
        "seed": config["seed"],
        "peak_temp_c": round(max(max(sample.gpu_temps.values()) for sample in samples), 2),
        "time_above_threshold_s": round(time_above, 2),
        "control_actions": len([event for event in events if event.get("action") in {"throttle", "recover"}]),
        "average_batch_size": round(avg_batch, 2),
        "latency_ms_p50": round(p50, 2),
        "latency_ms_p95": round(p95, 2),
        "latency_ms_p99": round(p99, 2),
        "throughput_toks_per_s": round(mean(sample.throughput_toks_per_s for sample in samples), 2),
        "throttle_duty_cycle": round(mean(1.0 if sample.thermal_throttle_active else 0.0 for sample in samples), 3),
        "oscillation_count": count_oscillations(events),
        "backend_failures": max(sample.backend_failures for sample in samples),
    }


def compare_summaries(baseline: dict, controlled: dict) -> dict:
    def delta(key: str) -> float:
        return round(controlled[key] - baseline[key], 2)

    return {
        "baseline_scenario": baseline["scenario_name"],
        "controlled_scenario": controlled["scenario_name"],
        "delta_peak_temp_c": delta("peak_temp_c"),
        "delta_time_above_threshold_s": delta("time_above_threshold_s"),
        "delta_latency_ms_p99": delta("latency_ms_p99"),
        "delta_average_batch_size": delta("average_batch_size"),
        "delta_throughput_toks_per_s": delta("throughput_toks_per_s"),
        "delta_control_actions": controlled["control_actions"] - baseline["control_actions"],
    }


def build_summary_markdown(summary: dict, comparison: Optional[dict]) -> str:
    lines = [
        f"# Run Summary: {summary['scenario_name']}",
        "",
        f"- Seed: `{summary['seed']}`",
        f"- Peak temp: `{summary['peak_temp_c']} C`",
        f"- Time above threshold: `{summary['time_above_threshold_s']} s`",
        f"- Control actions: `{summary['control_actions']}`",
        f"- Average batch size: `{summary['average_batch_size']}`",
        f"- Simulated latency p50/p95/p99: `{summary['latency_ms_p50']} / {summary['latency_ms_p95']} / {summary['latency_ms_p99']} ms`",
        f"- Throughput: `{summary['throughput_toks_per_s']} toks/s`",
        f"- Throttle duty cycle: `{summary['throttle_duty_cycle']}`",
        f"- Oscillation count: `{summary['oscillation_count']}`",
        f"- Backend failures observed: `{summary['backend_failures']}`",
    ]
    if comparison:
        lines.extend(
            [
                "",
                "## Comparison",
                "",
                f"- Delta peak temp: `{comparison['delta_peak_temp_c']} C`",
                f"- Delta time above threshold: `{comparison['delta_time_above_threshold_s']} s`",
                f"- Delta p99 latency: `{comparison['delta_latency_ms_p99']} ms`",
                f"- Delta throughput: `{comparison['delta_throughput_toks_per_s']} toks/s`",
            ]
        )
    return "\n".join(lines) + "\n"


def build_chart_svg(samples: Iterable[MetricsSnapshot]) -> str:
    samples = list(samples)
    width = 960
    height = 420
    margin = 48
    chart_w = width - margin * 2
    chart_h = height - margin * 2

    temps = [sample.gpu_temps.get(0, 0.0) for sample in samples]
    batches = [sample.active_batch_size for sample in samples]
    p99s = [sample.latency_ms_p99 for sample in samples]

    def scale_x(index: int) -> float:
        return margin + (index / max(1, len(samples) - 1)) * chart_w

    def scale_y(value: float, low: float, high: float) -> float:
        span = max(1e-6, high - low)
        return margin + chart_h - ((value - low) / span) * chart_h

    temp_low = min(temps) - 1.0
    temp_high = max(temps) + 1.0
    batch_low, batch_high = 0.0, max(batches) + 16
    latency_low = min(p99s) * 0.9
    latency_high = max(p99s) * 1.1

    def polyline(values: list[float], low: float, high: float) -> str:
        return " ".join(f"{scale_x(i):.1f},{scale_y(v, low, high):.1f}" for i, v in enumerate(values))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="#111827" rx="8"/>
  <text x="{margin}" y="28" fill="#f3f4f6" font-family="Arial, sans-serif" font-size="20">Simulation time series</text>
  <text x="{margin}" y="{height - 12}" fill="#9ca3af" font-family="Arial, sans-serif" font-size="12">green=temp, blue=batch, amber=p99</text>
  <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#374151" />
  <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#374151" />
  <polyline fill="none" stroke="#34d399" stroke-width="3" points="{polyline(temps, temp_low, temp_high)}"/>
  <polyline fill="none" stroke="#60a5fa" stroke-width="3" points="{polyline(batches, batch_low, batch_high)}"/>
  <polyline fill="none" stroke="#f59e0b" stroke-width="3" points="{polyline(p99s, latency_low, latency_high)}"/>
</svg>
"""
