from __future__ import annotations

import threading


class AtomicReceiptClaimRegistry:
    def __init__(self, processed_receipt_ids: frozenset[str] = frozenset()):
        if type(processed_receipt_ids) is not frozenset:
            raise TypeError("processed_receipt_ids must be frozenset")
        if any(not isinstance(item, str) or not item for item in processed_receipt_ids):
            raise ValueError("processed receipt ids must be non-empty strings")
        self._processed = set(processed_receipt_ids)
        self._lock = threading.Lock()

    def claim(self, receipt_id: str) -> bool:
        if not isinstance(receipt_id, str) or not receipt_id:
            raise ValueError("receipt_id must be a non-empty string")
        with self._lock:
            if receipt_id in self._processed:
                return False
            self._processed.add(receipt_id)
            return True

    def snapshot(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._processed)
