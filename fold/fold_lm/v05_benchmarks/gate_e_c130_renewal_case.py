from __future__ import annotations

from fold_lm.v05.recovery_fencing import RecoveryFencingRegistry

INITIAL_LEASE_TICKS = 5
RENEW_LEASE_TICKS = 5
RENEW_AT = (1, 3, 4)


def evaluate_lease(receipt_id: str, renew_at: int) -> dict:
    registry = RecoveryFencingRegistry()
    token = registry.acquire(receipt_id, "worker-a", now=0, lease_ticks=INITIAL_LEASE_TICKS)
    wrong_owner_rejected = not registry.renew(
        receipt_id, "worker-b", token, now=renew_at, lease_ticks=RENEW_LEASE_TICKS
    )
    valid_renewal = registry.renew(
        receipt_id, "worker-a", token, now=renew_at, lease_ticks=RENEW_LEASE_TICKS
    )
    renewed = registry.lease(receipt_id)
    expected_expiry = max(INITIAL_LEASE_TICKS, renew_at + RENEW_LEASE_TICKS)
    token_preserved = bool(renewed is not None and renewed.token == token)
    expiry_extended = bool(
        renewed is not None
        and renewed.expires_at == expected_expiry
        and renewed.expires_at > INITIAL_LEASE_TICKS
    )
    old_expiry_takeover_blocked = registry.acquire(
        receipt_id, "worker-b", now=INITIAL_LEASE_TICKS, lease_ticks=INITIAL_LEASE_TICKS
    ) is None
    exact_expiry_renew_rejected = not registry.renew(
        receipt_id, "worker-a", token, now=expected_expiry, lease_ticks=RENEW_LEASE_TICKS
    )
    new_token = registry.acquire(
        receipt_id, "worker-b", now=expected_expiry, lease_ticks=INITIAL_LEASE_TICKS
    )
    action_at = expected_expiry + 1
    return {
        "wrong_owner_renew_rejected": wrong_owner_rejected,
        "valid_renewal": valid_renewal,
        "token_preserved": token_preserved,
        "expiry_extended": expiry_extended,
        "old_expiry_takeover_blocked": old_expiry_takeover_blocked,
        "exact_expiry_renew_rejected": exact_expiry_renew_rejected,
        "exact_expiry_takeover_accepted": new_token is not None,
        "higher_token": bool(new_token is not None and new_token > token),
        "stale_token_rejected": not registry.allows(receipt_id, "worker-a", token, now=action_at),
        "new_token_allowed": bool(
            new_token is not None and registry.allows(receipt_id, "worker-b", new_token, now=action_at)
        ),
    }
