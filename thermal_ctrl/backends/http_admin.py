from __future__ import annotations

from dataclasses import dataclass

import requests

from thermal_ctrl.interfaces import ControlAction


@dataclass
class _HTTPConfig:
    base_url: str
    timeout_s: float


class HTTPAdminBatchBackend:
    kind = "http-admin"
    support_level = "experimental"

    def __init__(self, base_url: str, timeout_s: float):
        self.config = _HTTPConfig(base_url=base_url.rstrip("/"), timeout_s=timeout_s)
        self._current_batch_size = 0

    def set_batch_size(self, max_batch: int, reason_code: str, dry_run: bool = False) -> ControlAction:
        if dry_run:
            return ControlAction(
                action="set_batch",
                gpu_id=0,
                requested_batch=max_batch,
                applied_batch=self._current_batch_size or max_batch,
                kv_migration_pct=0.0,
                reason_code=reason_code,
                dry_run=True,
                backend_status="dry-run",
                backend_message="skipped http admin request",
            )
        try:
            response = requests.post(
                f"{self.config.base_url}/batch",
                json={"max_num_seqs": max_batch},
                timeout=self.config.timeout_s,
            )
            response.raise_for_status()
            self._current_batch_size = max_batch
            return ControlAction(
                action="set_batch",
                gpu_id=0,
                requested_batch=max_batch,
                applied_batch=max_batch,
                kv_migration_pct=0.0,
                reason_code=reason_code,
                backend_status="ok",
                backend_message="http admin batch update applied",
            )
        except Exception as exc:
            return ControlAction(
                action="set_batch",
                gpu_id=0,
                requested_batch=max_batch,
                applied_batch=self._current_batch_size,
                kv_migration_pct=0.0,
                reason_code=reason_code,
                backend_status="error",
                backend_message=str(exc),
            )

    def current_batch_size(self) -> int:
        return self._current_batch_size


class HTTPAdminKVMigrationBackend:
    kind = "http-admin"
    support_level = "experimental"

    def __init__(self, base_url: str, timeout_s: float):
        self.config = _HTTPConfig(base_url=base_url.rstrip("/"), timeout_s=timeout_s)

    def migrate(self, pct: float, reason_code: str, dry_run: bool = False) -> str:
        if dry_run:
            return f"dry-run kv migrate pct={pct:.3f} reason={reason_code}"
        response = requests.post(
            f"{self.config.base_url}/kv_migrate",
            json={"pct": pct},
            timeout=self.config.timeout_s,
        )
        response.raise_for_status()
        return f"http admin kv migrate pct={pct:.3f} reason={reason_code}"
