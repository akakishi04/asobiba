from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.receipt_atomic_claim import AtomicReceiptClaimRegistry
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

WORKERS = (2, 4, 8)


def _atomic_race(receipt_id: str, workers: int):
    registry = AtomicReceiptClaimRegistry()
    barrier = threading.Barrier(workers)

    def attempt(_):
        barrier.wait()
        return registry.claim(receipt_id)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(attempt, range(workers)))
    duplicate_after = registry.claim(receipt_id)
    return sum(results), duplicate_after, registry.snapshot()


def _naive_race(workers: int) -> int:
    seen = set()
    barrier = threading.Barrier(workers)

    def attempt(_):
        missing = "shared" not in seen
        barrier.wait()
        if missing:
            seen.add("shared")
            return True
        return False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return sum(pool.map(attempt, range(workers)))


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"outcome":"NONE_AVAILABLE","workers":0,"claims":0,"commit":0,"retry":0,"fallback":0,"final":"UNRESOLVED","trace":control["trace"],"passed":bool(control["passed"])})
                continue
            for outcome in c119h.OUTCOMES:
                for workers in WORKERS:
                    rid = f"c125:{''.join(map(str, actual))}:{hidden}:{outcome}:{workers}"
                    claims, duplicate_after, snapshot = _atomic_race(rid, workers)
                    control = c119h.scenario(router, visible, actual, hidden, outcome, device)
                    passed = bool(
                        claims == 1
                        and not duplicate_after
                        and snapshot == frozenset((rid,))
                        and control["passed"]
                    )
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"outcome":outcome,"workers":workers,"claims":claims,"commit":control["commit"] if claims == 1 else 0,"retry":control["retry"] if claims == 1 else 0,"fallback":control["fallback"] if claims == 1 else 0,"final":control["final"],"trace":control["trace"],"passed":passed})
    return rows


def negative_control_detected() -> bool:
    return all(_naive_race(workers) > 1 for workers in WORKERS)
