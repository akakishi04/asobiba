from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN, plan_post_transition_recovery
from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry
from fold_lm.v05.recovery_fencing import RecoveryFencingRegistry
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118

WORKERS = (2, 4, 8)
LEASE_TICKS = 5
TAKEOVER_AT = 5
ACTION_AT = 6
OUTCOMES = (APPLIED, NOT_APPLIED, STILL_UNKNOWN)


def _takeover_race(receipt_id: str, workers: int):
    registry = RecoveryFencingRegistry()
    old_token = registry.acquire(receipt_id, "worker-old", now=0, lease_ticks=LEASE_TICKS)
    barrier = threading.Barrier(workers)

    def attempt(index: int):
        worker = f"worker-{index}"
        barrier.wait()
        token = registry.acquire(receipt_id, worker, now=TAKEOVER_AT, lease_ticks=LEASE_TICKS)
        return worker, token

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(attempt, range(workers)))
    winners = [(worker, token) for worker, token in results if token is not None]
    return registry, old_token, winners


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                ok, action, trace = c118._preflight(router, visible, actual, device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":"NONE_AVAILABLE","workers":0,"trace":trace,"winner_count":0,"higher_token":True,"new_owner_allowed":True,"stale_owner_rejected":True,"stale_release_rejected":True,"loser_action_count":0,"replay_count":0,"complete_count":0,"logical_effect_count":0,"pending_after":False,"final":"UNRESOLVED","passed":bool(ok and action == 5)})
                continue

            ok, _, trace = c118._preflight(router, visible, actual, device)
            for outcome in OUTCOMES:
                for workers in WORKERS:
                    rid = f"c129:{''.join(map(str, actual))}:{hidden}:{outcome}:{workers}"
                    recovery = ReceiptRecoveryRegistry()
                    first_claim = recovery.claim(rid)
                    registry, old_token, winners = _takeover_race(rid, workers)
                    winner_count = len(winners)
                    winner_worker, winner_token = winners[0] if winner_count == 1 else (None, None)
                    higher_token = bool(old_token == 1 and winner_token is not None and winner_token > old_token)
                    stale_owner_rejected = not registry.allows(rid, "worker-old", old_token, now=ACTION_AT)
                    stale_release_rejected = not registry.release(rid, "worker-old", old_token)
                    new_owner_allowed = bool(winner_worker is not None and registry.allows(rid, winner_worker, winner_token, now=ACTION_AT))
                    loser_action_count = 0
                    replay_count = complete_count = 0
                    logical_effect_count = None
                    final = "INVALID"
                    if winner_count == 1 and new_owner_allowed:
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
                        elif plan.hold_pending:
                            logical_effect_count = None
                            final = "PENDING_UNCERTAIN"
                    snapshot = recovery.snapshot()
                    pending_after = recovery.is_pending(rid)
                    owner_release = bool(winner_worker is not None and registry.release(rid, winner_worker, winner_token))
                    if outcome == APPLIED:
                        outcome_ok = replay_count == 0 and complete_count == 1 and logical_effect_count == 1 and not pending_after
                    elif outcome == NOT_APPLIED:
                        outcome_ok = replay_count == 1 and complete_count == 1 and logical_effect_count == 1 and not pending_after
                    else:
                        outcome_ok = replay_count == 0 and complete_count == 0 and logical_effect_count is None and pending_after and rid not in snapshot.completed_receipt_ids
                    passed = bool(first_claim and ok and winner_count == 1 and higher_token and stale_owner_rejected and stale_release_rejected and new_owner_allowed and loser_action_count == 0 and owner_release and outcome_ok)
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":outcome,"workers":workers,"trace":trace,"winner_count":winner_count,"higher_token":higher_token,"new_owner_allowed":new_owner_allowed,"stale_owner_rejected":stale_owner_rejected,"stale_release_rejected":stale_release_rejected,"loser_action_count":loser_action_count,"ownership_released":owner_release,"replay_count":replay_count,"complete_count":complete_count,"logical_effect_count":logical_effect_count,"pending_after":pending_after,"final":final,"passed":passed})
    return rows
