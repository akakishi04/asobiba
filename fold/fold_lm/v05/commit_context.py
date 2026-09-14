from __future__ import annotations


def commit_context_matches(
    *,
    verified_request_epoch: int,
    current_request_epoch: int,
    verified_provider_generation: int,
    current_provider_generation: int,
) -> bool:
    values = (
        verified_request_epoch,
        current_request_epoch,
        verified_provider_generation,
        current_provider_generation,
    )
    if any(type(value) is not int for value in values):
        raise TypeError("epochs and generations must be integers")
    if any(value < 0 for value in values):
        raise ValueError("epochs and generations must be non-negative")
    return (
        verified_request_epoch == current_request_epoch
        and verified_provider_generation == current_provider_generation
    )
