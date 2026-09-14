from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.sqlite_recovery_fencing import SqliteRecoveryFencingStore

WORKERS = (2, 4, 8)
LEASE_TICKS = 5
TAKEOVER_AT = 5
WRITE_AT = 6


def evaluate_case(store: SqliteRecoveryFencingStore, receipt_id: str, workers: int, *, write_current: bool):
    old_token = store.acquire(receipt_id, "worker-old", now=0, lease_ticks=LEASE_TICKS)
    barrier = threading.Barrier(workers)

    def takeover(index: int):
        barrier.wait()
        token = store.acquire(receipt_id, f"worker-{index}", now=TAKEOVER_AT, lease_ticks=LEASE_TICKS)
        return index, token

    with ThreadPoolExecutor(max_workers=workers) as pool:
        takeover_results = list(pool.map(takeover, range(workers)))
    winners = [(index, token) for index, token in takeover_results if token is not None]
    winner_count = len(winners)
    winner_index, new_token = winners[0] if winner_count == 1 else (-1, None)

    write_barrier = threading.Barrier(workers)

    def write(index: int):
        write_barrier.wait()
        if write_current and index == winner_index:
            return "current", store.apply_fenced_write(
                receipt_id,
                f"worker-{index}",
                new_token,
                now=WRITE_AT,
                effect_key="current",
            )
        return "stale", store.apply_fenced_write(
            receipt_id,
            "worker-old",
            old_token,
            now=WRITE_AT,
            effect_key=f"stale-{index}",
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        write_results = list(pool.map(write, range(workers)))
    current_accepts = sum(kind == "current" and accepted for kind, accepted in write_results)
    stale_accepts = sum(kind == "stale" and accepted for kind, accepted in write_results)
    effect = store.read_effect(receipt_id)
    stored_current = bool(effect is not None and effect.effect_key == "current" and effect.fencing_token == new_token)
    stored_none = effect is None
    return {
        "winner_count": winner_count,
        "old_token": old_token,
        "new_token": new_token,
        "higher_token": bool(old_token == 1 and new_token == 2),
        "current_accepts": current_accepts,
        "stale_accepts": stale_accepts,
        "stored_current": stored_current,
        "stored_none": stored_none,
    }
