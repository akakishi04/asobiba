from __future__ import annotations

from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

RESTARTS = (1, 2, 3)


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({
                    "visible": list(visible), "actual": list(actual), "hidden": hidden,
                    "outcome": "NONE_AVAILABLE", "restarts": 0, "first_claim": False,
                    "pending_survived": True, "restart_duplicate_rejected": True,
                    "resume_count": 0, "completion_persisted": True,
                    "post_completion_duplicate_rejected": True,
                    "commit": 0, "retry": 0, "fallback": 0,
                    "final": "UNRESOLVED", "trace": control["trace"],
                    "passed": bool(control["passed"]),
                })
                continue

            for outcome in c119h.OUTCOMES:
                for restart_count in RESTARTS:
                    rid = f"c126:{''.join(map(str, actual))}:{hidden}:{outcome}:{restart_count}"
                    registry = ReceiptRecoveryRegistry()
                    first_claim = registry.claim(rid)
                    initial_snapshot = registry.snapshot()
                    pending_survived = (
                        initial_snapshot.pending_receipt_ids == frozenset((rid,))
                        and not initial_snapshot.completed_receipt_ids
                    )
                    restart_duplicate_rejected = True
                    for _ in range(restart_count):
                        registry = ReceiptRecoveryRegistry(registry.snapshot())
                        pending_survived = pending_survived and registry.is_pending(rid)
                        restart_duplicate_rejected = restart_duplicate_rejected and (not registry.claim(rid))

                    control = c119h.scenario(router, visible, actual, hidden, outcome, device)
                    resume_count = 1
                    registry.complete(rid)
                    completed_snapshot = registry.snapshot()
                    completion_persisted = (
                        rid not in completed_snapshot.pending_receipt_ids
                        and completed_snapshot.completed_receipt_ids == frozenset((rid,))
                    )
                    restored = ReceiptRecoveryRegistry(completed_snapshot)
                    post_completion_duplicate_rejected = not restored.claim(rid)
                    passed = bool(
                        first_claim
                        and pending_survived
                        and restart_duplicate_rejected
                        and resume_count == 1
                        and completion_persisted
                        and post_completion_duplicate_rejected
                        and control["passed"]
                    )
                    rows.append({
                        "visible": list(visible), "actual": list(actual), "hidden": hidden,
                        "outcome": outcome, "restarts": restart_count,
                        "first_claim": first_claim,
                        "pending_survived": pending_survived,
                        "restart_duplicate_rejected": restart_duplicate_rejected,
                        "resume_count": resume_count,
                        "completion_persisted": completion_persisted,
                        "post_completion_duplicate_rejected": post_completion_duplicate_rejected,
                        "commit": control["commit"], "retry": control["retry"],
                        "fallback": control["fallback"], "final": control["final"],
                        "trace": control["trace"], "passed": passed,
                    })
    return rows


def naive_processed_set_loses_pending_work() -> bool:
    processed = set()
    rid = "naive"
    processed.add(rid)
    restored = set(frozenset(processed))
    return rid in restored
