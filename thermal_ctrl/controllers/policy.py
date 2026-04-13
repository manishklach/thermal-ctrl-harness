from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional

from thermal_ctrl.interfaces import TemperatureReading, WorkloadSnapshot


@dataclass
class GPUControlState:
    current_batch: int
    throttle_active: bool = False
    last_action_ts: float = -1e9
    last_reason: str = "init"
    last_temp_c: float = 0.0
    consecutive_backend_failures: int = 0
    sensor_stale: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason_code: str
    requested_batch: int
    kv_migration_pct: float
    skip_backend: bool = False


class PolicyEngine:
    """Small policy engine for hysteresis, dwell time, and anti-flap protection."""

    def __init__(self, config: dict):
        self.config = config
        self.window_actions: Dict[int, Deque[float]] = defaultdict(deque)

    def evaluate(
        self,
        state: GPUControlState,
        reading: TemperatureReading,
        workload: WorkloadSnapshot,
    ) -> Optional[PolicyDecision]:
        cfg = self.config
        now = reading.timestamp
        self._prune_window(reading.gpu_id, now)
        state.last_temp_c = reading.celsius
        state.sensor_stale = reading.stale

        if reading.stale:
            return PolicyDecision(
                action="hold",
                reason_code="stale_sensor_reading",
                requested_batch=state.current_batch,
                kv_migration_pct=0.0,
                skip_backend=True,
            )

        if state.consecutive_backend_failures >= cfg["degraded_retries_before_hold"]:
            return PolicyDecision(
                action="hold",
                reason_code="degraded_backend_hold",
                requested_batch=state.current_batch,
                kv_migration_pct=0.0,
                skip_backend=True,
            )

        dwell_remaining = now - state.last_action_ts < cfg["min_dwell_s"]
        cooldown_remaining = now - state.last_action_ts < cfg["cooldown_s"]
        action_budget_exhausted = len(self.window_actions[reading.gpu_id]) >= cfg["max_actions_per_window"]

        if reading.celsius >= cfg["throttle_temp_c"] and not action_budget_exhausted and not dwell_remaining:
            target = max(
                cfg["min_batch_size"],
                int(max(cfg["min_batch_size"], state.current_batch * cfg["throttle_step_ratio"])),
            )
            if target < state.current_batch:
                return PolicyDecision(
                    action="throttle",
                    reason_code="threshold_crossed",
                    requested_batch=target,
                    kv_migration_pct=cfg["kv_migration_pct"] if cfg["enable_kv_migration"] else 0.0,
                )
            return PolicyDecision(
                action="hold",
                reason_code="already_min_batch",
                requested_batch=state.current_batch,
                kv_migration_pct=0.0,
                skip_backend=True,
            )

        if (
            reading.celsius <= cfg["recover_temp_c"]
            and state.current_batch < cfg["max_batch_size"]
            and not cooldown_remaining
            and not action_budget_exhausted
        ):
            target = min(
                cfg["max_batch_size"],
                int(max(state.current_batch + 1, state.current_batch * cfg["recover_step_ratio"])),
            )
            if target > state.current_batch:
                return PolicyDecision(
                    action="recover",
                    reason_code="hysteresis_recovery",
                    requested_batch=target,
                    kv_migration_pct=0.0,
                )

        if action_budget_exhausted and workload.pressure_index > 0.7:
            return PolicyDecision(
                action="hold",
                reason_code="anti_flap_hold",
                requested_batch=state.current_batch,
                kv_migration_pct=0.0,
                skip_backend=True,
            )

        return None

    def register_action(self, gpu_id: int, timestamp: float) -> None:
        self.window_actions[gpu_id].append(timestamp)

    def _prune_window(self, gpu_id: int, now: float) -> None:
        window = self.window_actions[gpu_id]
        while window and now - window[0] > self.config["anti_flap_window_s"]:
            window.popleft()


def count_oscillations(events: Iterable[dict]) -> int:
    actions: List[str] = [event["action"] for event in events if event.get("action") in {"throttle", "recover"}]
    oscillations = 0
    for previous, current in zip(actions, actions[1:]):
        if previous != current:
            oscillations += 1
    return oscillations
