from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class TemperatureReading:
    gpu_id: int
    celsius: float
    timestamp: float
    stale: bool = False


@dataclass(frozen=True)
class WorkloadSnapshot:
    timestamp: float
    request_rate: float
    queue_depth: float
    active_batch_size: int
    kv_pressure: float
    pressure_index: float


@dataclass(frozen=True)
class ControlAction:
    action: str
    gpu_id: int
    requested_batch: int
    applied_batch: int
    kv_migration_pct: float
    reason_code: str
    dry_run: bool = False
    backend_status: str = "ok"
    backend_message: str = ""


@dataclass(frozen=True)
class MetricsSnapshot:
    timestamp: float
    gpu_temps: Dict[int, float]
    workload_pressure: float
    queue_depth: float
    active_batch_size: int
    requested_batch_size: int
    thermal_throttle_active: bool
    kv_pressure: float
    kv_relief_active: bool
    latency_ms_p50: float
    latency_ms_p95: float
    latency_ms_p99: float
    throughput_toks_per_s: float
    backend_failures: int
    sensor_stale: bool


class TemperatureSensor(Protocol):
    kind: str
    support_level: str

    def read(self, timestamp: float) -> List[TemperatureReading]:
        ...


class WorkloadSignal(Protocol):
    kind: str

    def sample(self, timestamp: float, active_batch_size: int) -> WorkloadSnapshot:
        ...


class BatchControllerBackend(Protocol):
    kind: str
    support_level: str

    def set_batch_size(self, max_batch: int, reason_code: str, dry_run: bool = False) -> ControlAction:
        ...

    def current_batch_size(self) -> int:
        ...


class KVMigrationBackend(Protocol):
    kind: str
    support_level: str

    def migrate(self, pct: float, reason_code: str, dry_run: bool = False) -> str:
        ...


class MetricsSink(Protocol):
    kind: str

    def emit(self, snapshot: MetricsSnapshot) -> None:
        ...


class ArtifactWriter(Protocol):
    def write(
        self,
        artifact_dir: str,
        config: dict,
        samples: Iterable[MetricsSnapshot],
        events: Iterable[dict],
        summary: dict,
        comparison: Optional[dict] = None,
    ) -> None:
        ...
