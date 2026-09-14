from __future__ import annotations

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN, plan_post_transition_recovery
from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c130_renewal_case as case

OUTCOMES = (APPLIED, NOT_APPLIED, STILL_UNKNOWN)


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                ok, action, trace = c118._preflight(router, visible, actual, device)
                rows.append({
                    "visible": list(visible), "actual": list(actual), "hidden": hidden,
                    "transition_outcome": "NONE_AVAILABLE", "renew_at": 0, "trace": trace,
                    "passed": bool(ok and action == 5), "final": "UNRESOLVED",
                })
                continue
            ok, _, trace = c118._preflight(router, visible, actual, device)
            for outcome in OUTCOMES:
                for renew_at in case.RENEW_AT:
                    rid = f"c130:{''.join(map(str, actual))}:{hidden}:{outcome}:{renew_at}"
                    recovery = ReceiptRecoveryRegistry()
                    first_claim = recovery.claim(rid)
                    lease = case.evaluate_lease(rid, renew_at)
                    replay_count = complete_count = 0
                    logical_effect_count = None
                    final = "INVALID"
                    if lease["new_token_allowed"]:
                        plan = plan_post_transition_recovery(outcome)
                        if plan.complete_now:
                            recovery.complete(rid)
                            complete_count = 1
                            logical_effect_count = 1
                            final = "COMPLETED"
                        elif plan.replay_required:
                            replay_count = 1
                            logical_effect_count = 1
                            recovery.complete(rid)
                            complete_count = 1
                            final = "COMPLETED_AFTER_REPLAY"
                        else:
                            final = "PENDING_UNCERTAIN"
                    snapshot = recovery.snapshot()
                    pending_after = recovery.is_pending(rid)
                    if outcome == APPLIED:
                        outcome_ok = replay_count == 0 and complete_count == 1 and logical_effect_count == 1 and not pending_after
                    elif outcome == NOT_APPLIED:
                        outcome_ok = replay_count == 1 and complete_count == 1 and logical_effect_count == 1 and not pending_after
                    else:
                        outcome_ok = replay_count == 0 and complete_count == 0 and logical_effect_count is None and pending_after and rid not in snapshot.completed_receipt_ids
                    passed = bool(first_claim and ok and all(lease.values()) and outcome_ok)
                    rows.append({
                        "visible": list(visible), "actual": list(actual), "hidden": hidden,
                        "transition_outcome": outcome, "renew_at": renew_at, "trace": trace,
                        **lease, "replay_count": replay_count, "complete_count": complete_count,
                        "logical_effect_count": logical_effect_count, "pending_after": pending_after,
                        "final": final, "passed": passed,
                    })
    return rows
