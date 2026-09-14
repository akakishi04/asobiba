from __future__ import annotations

from dataclasses import dataclass

APPLIED = "APPLIED"
NOT_APPLIED = "NOT_APPLIED"
STILL_UNKNOWN = "STILL_UNKNOWN"


@dataclass(frozen=True)
class PostTransitionRecoveryPlan:
    replay_required: bool
    complete_now: bool
    hold_pending: bool


def plan_post_transition_recovery(outcome: str) -> PostTransitionRecoveryPlan:
    if outcome == APPLIED:
        return PostTransitionRecoveryPlan(False, True, False)
    if outcome == NOT_APPLIED:
        return PostTransitionRecoveryPlan(True, False, False)
    if outcome == STILL_UNKNOWN:
        return PostTransitionRecoveryPlan(False, False, True)
    raise ValueError(f"unsupported reconciliation outcome: {outcome!r}")
