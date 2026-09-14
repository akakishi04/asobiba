from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from fold_lm.v05.sqlite_recovery_fencing import SqliteRecoveryFencingStore


def _wait_for(path: Path, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {path}")
        time.sleep(0.002)


def run_task(task_path: Path) -> dict:
    task = json.loads(task_path.read_text(encoding="utf-8"))
    ready = Path(task["ready_path"])
    go = Path(task["go_path"])
    result_path = Path(task["result_path"])

    store = SqliteRecoveryFencingStore(Path(task["db_path"]))
    ready.write_text(str(os.getpid()), encoding="utf-8")
    _wait_for(go)

    mode = task["mode"]
    if mode == "acquire":
        value = store.acquire(
            task["receipt_id"],
            task["worker_id"],
            now=int(task["now"]),
            lease_ticks=int(task["lease_ticks"]),
        )
        result = {"pid": os.getpid(), "token": value}
    elif mode == "write":
        accepted = store.apply_fenced_write(
            task["receipt_id"],
            task["worker_id"],
            int(task["token"]),
            now=int(task["now"]),
            effect_key=task["effect_key"],
        )
        result = {"pid": os.getpid(), "accepted": bool(accepted), "kind": task["kind"]}
    else:
        raise ValueError(f"unsupported task mode: {mode!r}")

    result_path.write_text(json.dumps(result), encoding="utf-8")
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: gate_e_c132_process_worker <task.json>")
    run_task(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
