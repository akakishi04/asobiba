"""Bounded, local cache for validated prompt plans, never generated media."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
import sqlite3
import time
from threading import Lock
from pathlib import Path

CACHE_ERRORS = (OSError, ValueError, TypeError, sqlite3.Error)
CACHE_LIMIT = 256
CACHE_TTL = 30 * 24 * 3600


def content_sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_cache_key(request, settings, workflows, hints, sources, character_traits):
    # Invalidate old plans when the interpreter, schema or profile policy changes.
    policy = Path(__file__).parent
    version = {name: content_sha256(policy / name) for name in (
        "core.py", "lmstudio.py", "prompt_profiles.py", "parameters.py", "prompt_cache.py",
        "h3_prompt.py",
    )}
    identity = {
        "version": version, "request": request, "settings": settings,
        "workflows": workflows, "hints": hints, "character_traits": character_traits,
        "sources": {role: content_sha256(path) if path is not None else None
                    for role, path in sources.items()},
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PromptCache:
    def __init__(self, database: Path):
        self.database = Path(database)
        self._lock = Lock()
        self._counts = {"hits": 0, "misses": 0, "writes": 0, "clears": 0}

    def _count(self, key):
        with self._lock:
            self._counts[key] += 1

    def stats(self):
        with self._connection() as con:
            count, size = con.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(plan AS BLOB))), 0) FROM plans").fetchone()
        with self._lock:
            return {**self._counts, "entries": count, "payload_bytes": size, "limit": CACHE_LIMIT}

    @contextmanager
    def _connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=5)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS plans (
                key TEXT PRIMARY KEY, plan TEXT NOT NULL,
                created REAL NOT NULL, accessed REAL NOT NULL
            )""")
            con.execute("DELETE FROM plans WHERE created < ?", (time.time() - CACHE_TTL,))
            yield con

    def get(self, key: str) -> dict | None:
        with self._connection() as con:
            row = con.execute("SELECT plan FROM plans WHERE key = ?", (key,)).fetchone()
            if row is None:
                self._count("misses")
                return None
            try:
                plan = json.loads(row[0])
            except ValueError:
                con.execute("DELETE FROM plans WHERE key = ?", (key,))
                self._count("misses")
                return None
            if not isinstance(plan, dict):
                con.execute("DELETE FROM plans WHERE key = ?", (key,))
                self._count("misses")
                return None
            con.execute("UPDATE plans SET accessed = ? WHERE key = ?", (time.time(), key))
            self._count("hits")
            return plan

    def put(self, key: str, plan: dict) -> None:
        payload = json.dumps(plan, ensure_ascii=False)
        if len(payload.encode("utf-8")) > 65536:
            return
        now = time.time()
        with self._connection() as con:
            con.execute("INSERT OR REPLACE INTO plans VALUES (?, ?, ?, ?)",
                        (key, payload, now, now))
            con.execute("""DELETE FROM plans WHERE key IN (
                SELECT key FROM plans ORDER BY accessed DESC, key LIMIT -1 OFFSET ?
            )""", (CACHE_LIMIT,))
        self._count("writes")

    def clear(self) -> int:
        with self._connection() as con:
            count = con.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
            con.execute("PRAGMA secure_delete=ON")
            con.execute("DELETE FROM plans")
        self._count("clears")
        return count
