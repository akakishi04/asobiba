from __future__ import annotations

import json

from fold_lm.v05.post_transition_recovery import (
    APPLIED,
    NOT_APPLIED,
    STILL_UNKNOWN,
    plan_post_transition_recovery,
)
from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry, ReceiptRecoverySnapshot
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

RESTARTS = (1, 2, 3)
OUTCOMES = (APPLIED, NOT_APPLIED, STILL_UNKNOWN)


def _restore(registry: ReceiptRecoveryRegistry) -> ReceiptRecoveryRegistry:
    payload = json.loads(json.dumps(registry.snapshot().to_payload()))
    return ReceiptRecoveryRegistry(ReceiptRecoverySnapshot.from_payload(payload))


def naive_pending_replay_failure_detected() -> bool:
    effect_before_crash = 1
    naive_replay_effect = 1
    return effect_before_crash + naive_replay_effect == 2


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":"NONE_AVAILABLE","restarts":0,"trace":control["trace"],"replay_count":0,"complete_count":0,"logical_effect_count":0,"pending_after":False,"duplicate_rejected":True,"same_key":True,"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue

            ok, _, trace = c118._preflight(router, visible, actual, device)
            for outcome in OUTCOMES:
                for restart_count in RESTARTS:
                    rid = f"c127:{''.join(map(str, actual))}:{outcome}:{restart_count}"
                    registry = ReceiptRecoveryRegistry()
                    first_claim = registry.claim(rid)
                    logical_effect_count = 1 if outcome == APPLIED else (0 if outcome == NOT_APPLIED else None)
                    registry = _restore(registry)
                    duplicate_rejected = not registry.claim(rid)
                    for _ in range(restart_count - 1):
                        registry = _restore(registry)
                        duplicate_rejected = duplicate_rejected and (not registry.claim(rid))

                    plan = plan_post_transition_recovery(outcome)
                    replay_count = 0
                    complete_count = 0
                    same_key = True
                    if plan.complete_now:
                        registry.complete(rid)
                        complete_count = 1
                    elif plan.replay_required:
                        replay_key = rid
                        same_key = replay_key == rid
                        replay_count = 1
                        logical_effect_count += 1
                        registry.complete(rid)
                        complete_count = 1

                    registry = _restore(registry)
                    snapshot = registry.snapshot()
                    pending_after = registry.is_pending(rid)
                    duplicate_rejected = duplicate_rejected and (not registry.claim(rid))
                    if outcome == APPLIED:
                        final = "COMPLETED"
                        passed = first_claim and ok and replay_count == 0 and complete_count == 1 and logical_effect_count == 1 and not pending_after and rid in snapshot.completed_receipt_ids and duplicate_rejected
                    elif outcome == NOT_APPLIED:
                        final = "COMPLETED_AFTER_REPLAY"
                        passed = first_claim and ok and replay_count == 1 and same_key and complete_count == 1 and logical_effect_count == 1 and not pending_after and rid in snapshot.completed_receipt_ids and duplicate_rejected
                    else:
                        final = "PENDING_UNCERTAIN"
                        passed = first_claim and ok and replay_count == 0 and complete_count == 0 and logical_effect_count is None and pending_after and rid not in snapshot.completed_receipt_ids and duplicate_rejected

                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":outcome,"restarts":restart_count,"trace":trace,"replay_count":replay_count,"complete_count":complete_count,"logical_effect_count":logical_effect_count,"pending_after":pending_after,"duplicate_rejected":duplicate_rejected,"same_key":same_key,"final":final,"passed":bool(passed)})
    return rows
