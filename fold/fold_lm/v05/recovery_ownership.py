from __future__ import annotations

import threading


class RecoveryOwnershipRegistry:
    def __init__(self):
        self._owners: dict[str, str] = {}
        self._lock = threading.Lock()

    def acquire(self, receipt_id: str, worker_id: str) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        with self._lock:
            if receipt_id in self._owners:
                return False
            self._owners[receipt_id] = worker_id
            return True

    def owner(self, receipt_id: str) -> str | None:
        _validate_id(receipt_id, "receipt_id")
        with self._lock:
            return self._owners.get(receipt_id)

    def release(self, receipt_id: str, worker_id: str) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        with self._lock:
            if self._owners.get(receipt_id) != worker_id:
                return False
            del self._owners[receipt_id]
            return True


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
