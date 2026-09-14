from __future__ import annotations

from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class ReceiptRecoverySnapshot:
    pending_receipt_ids: frozenset[str] = frozenset()
    completed_receipt_ids: frozenset[str] = frozenset()

    def __post_init__(self):
        if type(self.pending_receipt_ids) is not frozenset or type(self.completed_receipt_ids) is not frozenset:
            raise TypeError("receipt id collections must be frozenset")
        values = self.pending_receipt_ids | self.completed_receipt_ids
        if any(not isinstance(item, str) or not item for item in values):
            raise ValueError("receipt ids must be non-empty strings")
        if self.pending_receipt_ids & self.completed_receipt_ids:
            raise ValueError("pending and completed receipt ids must be disjoint")


class ReceiptRecoveryRegistry:
    def __init__(self, snapshot: ReceiptRecoverySnapshot = ReceiptRecoverySnapshot()):
        if type(snapshot) is not ReceiptRecoverySnapshot:
            raise TypeError("snapshot must be ReceiptRecoverySnapshot")
        self._pending = set(snapshot.pending_receipt_ids)
        self._completed = set(snapshot.completed_receipt_ids)
        self._lock = threading.Lock()

    def claim(self, receipt_id: str) -> bool:
        _validate_id(receipt_id)
        with self._lock:
            if receipt_id in self._pending or receipt_id in self._completed:
                return False
            self._pending.add(receipt_id)
            return True

    def is_pending(self, receipt_id: str) -> bool:
        _validate_id(receipt_id)
        with self._lock:
            return receipt_id in self._pending

    def complete(self, receipt_id: str) -> None:
        _validate_id(receipt_id)
        with self._lock:
            if receipt_id not in self._pending:
                raise ValueError("receipt is not pending")
            self._pending.remove(receipt_id)
            self._completed.add(receipt_id)

    def snapshot(self) -> ReceiptRecoverySnapshot:
        with self._lock:
            return ReceiptRecoverySnapshot(
                pending_receipt_ids=frozenset(self._pending),
                completed_receipt_ids=frozenset(self._completed),
            )


def _validate_id(receipt_id: str) -> None:
    if not isinstance(receipt_id, str) or not receipt_id:
        raise ValueError("receipt_id must be a non-empty string")
