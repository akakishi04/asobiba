"""Measured ComfyUI submission/wait timings; estimates never drive execution."""
from __future__ import annotations

import contextvars
import json
import math
import sqlite3
import statistics
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, sqlite3.Error)
_observer = contextvars.ContextVar("generation_timing_observer", default=None)


@dataclass(frozen=True)
class Estimate:
    seconds: float
    samples: int
    scaled: bool = False


@contextmanager
def observe(emit):
    token = _observer.set(emit)
    try:
        yield
    finally:
        _observer.reset(token)


def report_estimate(estimate, *, label="生成待ち"):
    sink = _observer.get()
    if sink:
        sink(("timing", {"estimate": estimate, "label": label, "at": time.monotonic()}))


def profile_key(backend, workflow_id, parameters):
    # Frame count is kept separately for bounded interpolation. Prompt and seed
    # changes alone do not define a new performance class.
    fixed = {k: v for k, v in parameters.items()
             if k not in ("seed", "positive_prompt", "negative_prompt", "frames")
             and not k.startswith("long_")}
    frames = parameters.get("frames", 0)
    if type(frames) is not int or frames < 0:
        raise ValueError("invalid frame count")
    return json.dumps([backend.rstrip("/"), workflow_id, fixed], sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")), frames


class TimingStore:
    def __init__(self, database):
        self.database = Path(database)

    @contextmanager
    def connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=3)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS samples (
                job_id TEXT PRIMARY KEY, profile TEXT NOT NULL,
                frames INTEGER NOT NULL, seconds REAL NOT NULL, measured REAL NOT NULL
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS timing_profile ON samples(profile, frames, measured DESC)")
            con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY)")
            yield con

    @staticmethod
    def _row(job_id, backend, workflow_id, parameters, seconds, measured):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            return None
        profile, frames = profile_key(backend, workflow_id, parameters)
        return job_id, profile, frames, float(seconds), float(measured)

    def bootstrap(self, job_root):
        """Import pre-existing unambiguous success records once; optional cache."""
        with self.connection() as con:
            if con.execute("SELECT 1 FROM meta WHERE key='imported_v1'").fetchone():
                return
            for path in Path(job_root).glob("*/record.json"):
                try:
                    r = json.loads(path.read_text(encoding="utf-8"))
                    if r.get("state") not in ("completed", "collected") or r.get("error") or r.get("failure_kind"):
                        continue
                    row = self._row(r["job_id"], r["backend"], r["workflow_id"], r["parameters"],
                                    r.get("elapsed_seconds"), path.stat().st_mtime)
                    if row:
                        con.execute("INSERT OR IGNORE INTO samples VALUES (?, ?, ?, ?, ?)", row)
                except ERRORS:
                    continue
            self._prune(con)
            con.execute("INSERT OR IGNORE INTO meta VALUES ('imported_v1')")

    @staticmethod
    def _prune(con):
        con.execute("""DELETE FROM samples WHERE job_id IN (
            SELECT job_id FROM samples ORDER BY measured DESC, job_id LIMIT -1 OFFSET 5000
        )""")

    def record(self, job_id, backend, workflow_id, parameters, seconds):
        row = self._row(job_id, backend, workflow_id, parameters, seconds, time.time())
        if row is None:
            return
        with self.connection() as con:
            con.execute("INSERT OR REPLACE INTO samples VALUES (?, ?, ?, ?, ?)", row)
            self._prune(con)

    def _estimate(self, con, backend, workflow_id, parameters):
        key, frames = profile_key(backend, workflow_id, parameters)
        exact = con.execute("SELECT seconds FROM samples WHERE profile=? AND frames=? ORDER BY measured DESC LIMIT 12",
                            (key, frames)).fetchall()
        if exact:
            return Estimate(statistics.median(row[0] for row in exact), len(exact))
        if frames:
            rows = con.execute("""SELECT frames, seconds FROM samples
                WHERE profile=? AND frames>0 AND frames>=? AND frames<=?
                ORDER BY measured DESC LIMIT 12""", (key, frames / 2, frames * 2)).fetchall()
            if rows:
                return Estimate(statistics.median(seconds * frames / observed for observed, seconds in rows),
                                len(rows), True)
        return None

    def estimate(self, backend, workflow_id, parameters):
        with self.connection() as con:
            return self._estimate(con, backend, workflow_id, parameters)

    def sequence(self, backend, workflow_id, parameters):
        cache = {}
        estimates = []
        with self.connection() as con:
            for p in parameters:
                key = profile_key(backend, workflow_id, p)
                if key not in cache:
                    cache[key] = self._estimate(con, backend, workflow_id, p)
                estimates.append(cache[key])
        if not estimates or any(e is None for e in estimates):
            return None
        return Estimate(sum(e.seconds for e in estimates), min(e.samples for e in estimates),
                        any(e.scaled for e in estimates))


def format_elapsed(seconds):
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
