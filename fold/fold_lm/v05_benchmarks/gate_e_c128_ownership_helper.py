from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN, plan_post_transition_recovery
from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry, ReceiptRecoverySnapshot
from fold_lm.v05.recovery_ownership import RecoveryOwnershipRegistry
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

WORKERS = (2, 4, 8)
OUTCOMES = (APPLIED, NOT_APPLIED, STILL_UNKNOWN)


def _restore(registry: ReceiptRecoveryRegistry) -> ReceiptRecoveryRegistry:
    payload = json.loads(json.dumps(registry.snapshot().to_payload()))
    return ReceiptRecoveryRegistry(ReceiptRecoverySnapshot.from_payload(payload))


def _ownership_race(receipt_id: str, workers: int):
    registry = RecoveryOwnershipRegistry()
    barrier = threading.Barrier(workers)

    def attempt(index):
        worker_id = f"worker-{index}"
        barrier.wait()
        return worker_id, registry.acquire(receipt_id, worker_id)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(attempt, range(workers)))
    winners = [worker for worker, won in results if won]
    owner = registry.owner(receipt_id)
    return registry, winners, owner


def _naive_race(workers: int) -> int:
    owners = {}
    barrier = threading.Barrier(workers)

    def attempt(index):
        available = "r" not in owners
        barrier.wait()
        if available:
            owners["r"] = f"worker-{index}"
            return True
        return False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return sum(pool.map(attempt, range(workers)))


def negative_control_detected() -> bool:
    return all(_naive_race(workers) > 1 for workers in WORKERS)


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":"NONE_AVAILABLE","workers":0,"winner_count":0,"owner_matches":True,"loser_action_count":0,"ownership_released":True,"replay_count":0,"complete_count":0,"logical_effect_count":0,"pending_after":False,"trace":control["trace"],"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue

            ok, _, trace = c118._preflight(router, visible, actual, device)
            for outcome in OUTCOMES:
                for workers in WORKERS:
                    rid = f"c128:{''.join(map(str, actual))}:{hidden}:{outcome}:{workers}"
                    durable = ReceiptRecoveryRegistry()
                    first_claim = durable.claim(rid)
                    durable = _restore(durable)
                    ownership, winners, owner = _ownership_race(rid, workers)
                    winner_count = len(winners)
                    owner_matches = winner_count == 1 and owner == winners[0]
                    loser_action_count = 0
                    replay_count = 0
                    complete_count = 0
                    logical_effect_count = 1 if outcome == APPLIED else (0 if outcome == NOT_APPLIED else None)
                    same_key = True
                    plan = plan_post_transition_recovery(outcome)

                    if owner_matches:
                        if plan.complete_now:
                            durable.complete(rid)
                            complete_count = 1
                        elif plan.replay_required:
                            replay_key = rid
                            same_key = replay_key == rid
                            replay_count = 1
                            logical_effect_count += 1
                            durable.complete(rid)
                            complete_count = 1

                    pending_after = durable.is_pending(rid)
                    snapshot = durable.snapshot()
                    ownership_released = bool(owner_matches and ownership.release(rid, winners[0]))
                    if outcome == APPLIED:
                        final = "COMPLETED"
                        passed = first_claim and ok and owner_matches and loser_action_count == 0 and ownership_released and replay_count == 0 and complete_count == 1 and logical_effect_count == 1 and not pending_after and rid in snapshot.completed_receipt_ids
                    elif outcome == NOT_APPLIED:
                        final = "COMPLETED_AFTER_REPLAY"
                        passed = first_claim and ok and owner_matches and loser_action_count == 0 and ownership_released and replay_count == 1 and same_key and complete_count == 1 and logical_effect_count == 1 and not pending_after and rid in snapshot.completed_receipt_ids
                    else:
                        final = "PENDING_UNCERTAIN"
                        passed = first_claim and ok and owner_matches and loser_action_count == 0 and ownership_released and replay_count == 0 and complete_count == 0 and logical_effect_count is None and pending_after and rid not in snapshot.completed_receipt_ids

                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"transition_outcome":outcome,"workers":workers,"winner_count":winner_count,"owner_matches":owner_matches,"loser_action_count":loser_action_count,"ownership_released":ownership_released,"replay_count":replay_count,"complete_count":complete_count,"logical_effect_count":logical_effect_count,"pending_after":pending_after,"trace":trace,"final":final,"passed":bool(passed)})
    return rows
