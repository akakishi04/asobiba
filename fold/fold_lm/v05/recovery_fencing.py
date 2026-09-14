from __future__ import annotations

from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class RecoveryLease:
    owner_id: str
    token: int
    expires_at: int


class RecoveryFencingRegistry:
    def __init__(self):
        self._leases: dict[str, RecoveryLease] = {}
        self._last_tokens: dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(self, receipt_id: str, worker_id: str, *, now: int, lease_ticks: int) -> int | None:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_time(now, "now")
        if type(lease_ticks) is not int or lease_ticks <= 0:
            raise ValueError("lease_ticks must be a positive integer")
        with self._lock:
            current = self._leases.get(receipt_id)
            if current is not None and now < current.expires_at:
                return None
            token = self._last_tokens.get(receipt_id, 0) + 1
            self._last_tokens[receipt_id] = token
            self._leases[receipt_id] = RecoveryLease(worker_id, token, now + lease_ticks)
            return token

    def renew(self, receipt_id: str, worker_id: str, token: int, *, now: int, lease_ticks: int) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_token(token)
        _validate_time(now, "now")
        if type(lease_ticks) is not int or lease_ticks <= 0:
            raise ValueError("lease_ticks must be a positive integer")
        with self._lock:
            current = self._leases.get(receipt_id)
            if (
                current is None
                or current.owner_id != worker_id
                or current.token != token
                or now >= current.expires_at
            ):
                return False
            expires_at = max(current.expires_at, now + lease_ticks)
            self._leases[receipt_id] = RecoveryLease(worker_id, token, expires_at)
            return True

    def allows(self, receipt_id: str, worker_id: str, token: int, *, now: int) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_token(token)
        _validate_time(now, "now")
        with self._lock:
            current = self._leases.get(receipt_id)
            return bool(
                current is not None
                and current.owner_id == worker_id
                and current.token == token
                and now < current.expires_at
            )

    def release(self, receipt_id: str, worker_id: str, token: int) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_token(token)
        with self._lock:
            current = self._leases.get(receipt_id)
            if current is None or current.owner_id != worker_id or current.token != token:
                return False
            del self._leases[receipt_id]
            return True

    def lease(self, receipt_id: str) -> RecoveryLease | None:
        _validate_id(receipt_id, "receipt_id")
        with self._lock:
            return self._leases.get(receipt_id)


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_time(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_token(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("token must be a positive integer")
