from __future__ import annotations

from typing import List

from prometheus_client import Gauge, start_http_server

from thermal_ctrl.interfaces import MetricsSink, MetricsSnapshot


class InMemoryMetricsSink(MetricsSink):
    kind = "memory"

    def __init__(self) -> None:
        self.samples: List[MetricsSnapshot] = []

    def emit(self, snapshot: MetricsSnapshot) -> None:
        self.samples.append(snapshot)


class PrometheusMetricsSink(MetricsSink):
    kind = "prometheus"

    def __init__(self, port: int):
        self.port = port
        self.started = False
        self.temp_gauge = Gauge("gpu_hbm_temp_celsius", "HBM temperature per GPU", ["gpu"])
        self.batch_gauge = Gauge("thermal_ctrl_active_batch_size", "Current active batch size")
        self.legacy_batch_gauge = Gauge("vllm_max_batch_size", "Legacy batch size gauge for existing dashboards")
        self.requested_batch_gauge = Gauge("thermal_ctrl_requested_batch_size", "Requested batch size")
        self.throttle_gauge = Gauge("thermal_ctrl_throttle_active", "1 when throttling")
        self.legacy_throttle_gauge = Gauge("thermal_throttle_active", "Legacy throttle gauge for existing dashboards")
        self.p99_gauge = Gauge("thermal_ctrl_latency_p99_ms", "Simulated or observed p99 latency")
        self.queue_gauge = Gauge("thermal_ctrl_queue_depth", "Queue depth")
        self.throughput_gauge = Gauge("thermal_ctrl_throughput_tokens_per_s", "Throughput")
        self.backend_failures_gauge = Gauge("thermal_ctrl_backend_failures_total", "Backend failures")

    def emit(self, snapshot: MetricsSnapshot) -> None:
        if not self.started:
            start_http_server(self.port)
            self.started = True
        for gpu_id, temp in snapshot.gpu_temps.items():
            self.temp_gauge.labels(gpu=str(gpu_id)).set(temp)
        self.batch_gauge.set(snapshot.active_batch_size)
        self.legacy_batch_gauge.set(snapshot.active_batch_size)
        self.requested_batch_gauge.set(snapshot.requested_batch_size)
        self.throttle_gauge.set(1 if snapshot.thermal_throttle_active else 0)
        self.legacy_throttle_gauge.set(1 if snapshot.thermal_throttle_active else 0)
        self.p99_gauge.set(snapshot.latency_ms_p99)
        self.queue_gauge.set(snapshot.queue_depth)
        self.throughput_gauge.set(snapshot.throughput_toks_per_s)
        self.backend_failures_gauge.set(snapshot.backend_failures)
