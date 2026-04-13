from __future__ import annotations

from thermal_ctrl.interfaces import ControlAction


class MockBatchBackend:
    kind = "mock"
    support_level = "mock-only"

    def __init__(self, initial_batch_size: int):
        self._current_batch_size = initial_batch_size

    def set_batch_size(self, max_batch: int, reason_code: str, dry_run: bool = False) -> ControlAction:
        applied = self._current_batch_size if dry_run else max_batch
        if not dry_run:
            self._current_batch_size = max_batch
        return ControlAction(
            action="set_batch",
            gpu_id=0,
            requested_batch=max_batch,
            applied_batch=applied,
            kv_migration_pct=0.0,
            reason_code=reason_code,
            dry_run=dry_run,
            backend_status="ok",
            backend_message="mock backend accepted batch update",
        )

    def current_batch_size(self) -> int:
        return self._current_batch_size


class MockKVMigrationBackend:
    kind = "mock"
    support_level = "mock-only"

    def __init__(self) -> None:
        self.last_pct = 0.0

    def migrate(self, pct: float, reason_code: str, dry_run: bool = False) -> str:
        if not dry_run:
            self.last_pct = pct
        return f"mock kv migration pct={pct:.3f} reason={reason_code} dry_run={dry_run}"
