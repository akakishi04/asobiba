from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class StoredRecoveryEffect:
    receipt_id: str
    effect_key: str
    fencing_token: int


class SqliteRecoveryFencingStore:
    """SQLite-backed lease/fencing authority using independent transactions."""

    def __init__(self, path: Path):
        if not isinstance(path, Path):
            raise TypeError("path must be pathlib.Path")
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_fence (
                    receipt_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    token INTEGER NOT NULL CHECK(token > 0),
                    expires_at INTEGER NOT NULL CHECK(expires_at >= 0)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_effect (
                    receipt_id TEXT PRIMARY KEY,
                    effect_key TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL CHECK(fencing_token > 0)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def acquire(self, receipt_id: str, worker_id: str, *, now: int, lease_ticks: int) -> int | None:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_time(now, "now")
        if type(lease_ticks) is not int or lease_ticks <= 0:
            raise ValueError("lease_ticks must be a positive integer")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT token, expires_at FROM recovery_fence WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is not None and now < row[1]:
                conn.rollback()
                return None
            token = (row[0] if row is not None else 0) + 1
            conn.execute(
                """
                INSERT INTO recovery_fence(receipt_id, owner_id, token, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(receipt_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    token = excluded.token,
                    expires_at = excluded.expires_at
                """,
                (receipt_id, worker_id, token, now + lease_ticks),
            )
            conn.commit()
            return token
        finally:
            conn.close()

    def apply_fenced_write(
        self,
        receipt_id: str,
        worker_id: str,
        token: int,
        *,
        now: int,
        effect_key: str,
    ) -> bool:
        _validate_id(receipt_id, "receipt_id")
        _validate_id(worker_id, "worker_id")
        _validate_id(effect_key, "effect_key")
        _validate_token(token)
        _validate_time(now, "now")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                INSERT INTO recovery_effect(receipt_id, effect_key, fencing_token)
                SELECT ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM recovery_fence
                    WHERE receipt_id = ?
                      AND owner_id = ?
                      AND token = ?
                      AND ? < expires_at
                )
                ON CONFLICT(receipt_id) DO UPDATE SET
                    effect_key = excluded.effect_key,
                    fencing_token = excluded.fencing_token
                WHERE excluded.fencing_token >= recovery_effect.fencing_token
                """,
                (receipt_id, effect_key, token, receipt_id, worker_id, token, now),
            )
            conn.commit()
            return cur.rowcount == 1
        finally:
            conn.close()

    def read_effect(self, receipt_id: str) -> StoredRecoveryEffect | None:
        _validate_id(receipt_id, "receipt_id")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT effect_key, fencing_token FROM recovery_effect WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is None:
                return None
            return StoredRecoveryEffect(receipt_id, row[0], row[1])
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_time(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_token(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("token must be a positive integer")
