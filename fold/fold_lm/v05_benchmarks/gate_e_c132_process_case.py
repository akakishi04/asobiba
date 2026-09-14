from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fold_lm.v05.sqlite_recovery_fencing import SqliteRecoveryFencingStore

WORKERS = (2, 4, 8)
MODES = ("RESOLVED", "UNKNOWN")
REPETITIONS = 3
LEASE_TICKS = 5
TAKEOVER_AT = 5
WRITE_AT = 6


def _run_group(tasks: list[dict], group_dir: Path) -> tuple[list[dict], bool]:
    group_dir.mkdir(parents=True, exist_ok=False)
    go_path = (group_dir / "go.signal").resolve()
    processes: list[subprocess.Popen] = []
    result_paths: list[Path] = []
    ready_paths: list[Path] = []

    for index, task in enumerate(tasks):
        ready = (group_dir / f"ready-{index}.txt").resolve()
        result = (group_dir / f"result-{index}.json").resolve()
        task_path = (group_dir / f"task-{index}.json").resolve()
        payload = dict(task)
        payload.update({
            "ready_path": str(ready),
            "go_path": str(go_path),
            "result_path": str(result),
        })
        task_path.write_text(json.dumps(payload), encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-m", "fold_lm.v05_benchmarks.gate_e_c132_process_worker", str(task_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(proc)
        result_paths.append(result)
        ready_paths.append(ready)

    deadline = time.monotonic() + 30.0
    while not all(path.exists() for path in ready_paths):
        if time.monotonic() >= deadline:
            for proc in processes:
                proc.kill()
            raise TimeoutError("C132 worker readiness timeout")
        if any(proc.poll() not in (None, 0) for proc in processes):
            details = []
            for proc in processes:
                out, err = proc.communicate(timeout=1) if proc.poll() is not None else ("", "")
                details.append((proc.returncode, out, err))
            raise RuntimeError(f"C132 worker exited before barrier: {details!r}")
        time.sleep(0.005)

    go_path.write_text("go", encoding="utf-8")
    clean = True
    diagnostics = []
    for proc in processes:
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            clean = False
        if proc.returncode != 0:
            clean = False
        diagnostics.append((proc.returncode, out, err))
    if not clean:
        raise RuntimeError(f"C132 worker failure: {diagnostics!r}")

    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    pids = [int(result["pid"]) for result in results]
    identity_ok = len(set(pids)) == len(pids) and os.getpid() not in pids
    return results, identity_ok


def evaluate_case(db_path: Path, case_dir: Path, receipt_id: str, workers: int, mode: str) -> dict:
    if mode not in MODES:
        raise ValueError(mode)
    store = SqliteRecoveryFencingStore(db_path)
    old_token = store.acquire(receipt_id, "worker-old", now=0, lease_ticks=LEASE_TICKS)

    takeover_tasks = [
        {
            "mode": "acquire",
            "db_path": str(db_path.resolve()),
            "receipt_id": receipt_id,
            "worker_id": f"worker-{index}",
            "now": TAKEOVER_AT,
            "lease_ticks": LEASE_TICKS,
        }
        for index in range(workers)
    ]
    takeover_results, takeover_process_identity = _run_group(takeover_tasks, case_dir / "takeover")
    winners = [(index, row["token"]) for index, row in enumerate(takeover_results) if row.get("token") is not None]
    winner_count = len(winners)
    winner_index, new_token = winners[0] if winner_count == 1 else (-1, None)

    if winner_count != 1:
        return {
            "workers": workers,
            "mode": mode,
            "winner_count": winner_count,
            "higher_token": False,
            "takeover_process_identity": takeover_process_identity,
            "write_process_identity": False,
            "current_accepts": 0,
            "stale_accepts": 0,
            "stored_current": False,
            "stored_none": store.read_effect(receipt_id) is None,
            "passed": False,
        }

    write_tasks = []
    for index in range(workers):
        if mode == "RESOLVED" and index == winner_index:
            write_tasks.append({
                "mode": "write",
                "kind": "current",
                "db_path": str(db_path.resolve()),
                "receipt_id": receipt_id,
                "worker_id": f"worker-{index}",
                "token": new_token,
                "now": WRITE_AT,
                "effect_key": "current",
            })
        else:
            write_tasks.append({
                "mode": "write",
                "kind": "stale",
                "db_path": str(db_path.resolve()),
                "receipt_id": receipt_id,
                "worker_id": "worker-old",
                "token": old_token,
                "now": WRITE_AT,
                "effect_key": f"stale-{index}",
            })

    write_results, write_process_identity = _run_group(write_tasks, case_dir / "write")
    current_accepts = sum(row["kind"] == "current" and row["accepted"] for row in write_results)
    stale_accepts = sum(row["kind"] == "stale" and row["accepted"] for row in write_results)
    effect = store.read_effect(receipt_id)
    stored_current = bool(effect is not None and effect.effect_key == "current" and effect.fencing_token == new_token)
    stored_none = effect is None

    if mode == "RESOLVED":
        storage_ok = current_accepts == 1 and stale_accepts == 0 and stored_current
    else:
        storage_ok = current_accepts == 0 and stale_accepts == 0 and stored_none

    passed = bool(
        old_token == 1
        and new_token == 2
        and winner_count == 1
        and takeover_process_identity
        and write_process_identity
        and storage_ok
    )
    return {
        "workers": workers,
        "mode": mode,
        "winner_count": winner_count,
        "higher_token": bool(old_token == 1 and new_token == 2),
        "takeover_process_identity": takeover_process_identity,
        "write_process_identity": write_process_identity,
        "current_accepts": current_accepts,
        "stale_accepts": stale_accepts,
        "stored_current": stored_current,
        "stored_none": stored_none,
        "passed": passed,
    }
