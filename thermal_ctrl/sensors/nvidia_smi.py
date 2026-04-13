from __future__ import annotations

import shutil
import subprocess
from typing import List

from thermal_ctrl.interfaces import TemperatureReading


class NvidiaSmiTemperatureSensor:
    kind = "nvidia-smi"
    support_level = "production-possible"

    def __init__(self, stale_after_s: float = 3.0):
        self.stale_after_s = stale_after_s
        self._last_success: float | None = None
        self._last_values: List[TemperatureReading] = []

    def read(self, timestamp: float) -> List[TemperatureReading]:
        if shutil.which("nvidia-smi") is None:
            return self._stale(timestamp)
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=index,memory.temp", "--format=csv,noheader,nounits"],
                stderr=subprocess.STDOUT,
                timeout=2,
            ).decode("utf-8", errors="replace")
            readings = []
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                gpu_id, temp = [part.strip() for part in line.split(",", 1)]
                readings.append(TemperatureReading(gpu_id=int(gpu_id), celsius=float(temp), timestamp=timestamp))
            if readings:
                self._last_success = timestamp
                self._last_values = readings
                return readings
        except Exception:
            return self._stale(timestamp)
        return self._stale(timestamp)

    def _stale(self, timestamp: float) -> List[TemperatureReading]:
        if not self._last_values:
            return [TemperatureReading(gpu_id=0, celsius=0.0, timestamp=timestamp, stale=True)]
        stale = self._last_success is None or timestamp - self._last_success > self.stale_after_s
        return [
            TemperatureReading(
                gpu_id=reading.gpu_id,
                celsius=reading.celsius,
                timestamp=timestamp,
                stale=stale,
            )
            for reading in self._last_values
        ]
