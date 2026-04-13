from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List

from thermal_ctrl.interfaces import TemperatureReading, WorkloadSnapshot


@dataclass
class SimulatedThermalState:
    celsius: float
    kv_pressure: float = 0.15
    last_timestamp: float = 0.0


class SimulatedWorkloadSignal:
    kind = "simulated"

    def __init__(self, config: dict, seed: int):
        self.config = config
        self.random = random.Random(seed)

    def sample(self, timestamp: float, active_batch_size: int) -> WorkloadSnapshot:
        cfg = self.config
        burst_start = cfg["burst_start_s"]
        burst_end = burst_start + cfg["burst_duration_s"]
        request_rate = cfg["burst_request_rate"] if burst_start <= timestamp <= burst_end else cfg["base_request_rate"]
        jitter = self.random.uniform(-0.3, 0.3)
        queue_depth = max(0.0, (request_rate - active_batch_size * cfg["throughput_per_batch"] / 32.0) * 1.1 + jitter)
        kv_pressure = min(1.0, max(0.0, 0.22 + queue_depth * 0.03 + request_rate / 20.0))
        pressure_index = min(1.6, (request_rate / 10.0) + (active_batch_size / 256.0) * 0.55 + kv_pressure * 0.55)
        return WorkloadSnapshot(
            timestamp=timestamp,
            request_rate=request_rate,
            queue_depth=queue_depth,
            active_batch_size=active_batch_size,
            kv_pressure=kv_pressure,
            pressure_index=pressure_index,
        )


class SimulatedTemperatureSensor:
    kind = "simulated"
    support_level = "mock-only"

    def __init__(self, config: dict, gpu_count: int, seed: int):
        self.config = config
        self.random = random.Random(seed)
        self.state: Dict[int, SimulatedThermalState] = {
            gpu_id: SimulatedThermalState(celsius=config["initial_temp_c"]) for gpu_id in range(gpu_count)
        }
        self.latest_pressure = 0.0
        self.latest_kv_relief = 0.0

    def apply_simulation_inputs(self, workload_pressure: float, kv_relief_active: bool) -> None:
        self.latest_pressure = workload_pressure
        self.latest_kv_relief = 1.0 if kv_relief_active else 0.0

    def read(self, timestamp: float) -> List[TemperatureReading]:
        cfg = self.config
        readings: List[TemperatureReading] = []
        for gpu_id, state in self.state.items():
            noise = self.random.uniform(-cfg["noise_c"], cfg["noise_c"])
            target = max(
                cfg["ambient_temp_c"],
                cfg["ambient_temp_c"]
                + self.latest_pressure * cfg["rise_per_pressure"] * 24.0
                - cfg["cooling_per_step"]
                - self.latest_kv_relief * cfg["kv_relief_cooling"],
            )
            state.celsius = (state.celsius * cfg["thermal_inertia"]) + (target * (1 - cfg["thermal_inertia"])) + noise
            state.last_timestamp = timestamp
            readings.append(TemperatureReading(gpu_id=gpu_id, celsius=round(state.celsius, 2), timestamp=timestamp))
        return readings
