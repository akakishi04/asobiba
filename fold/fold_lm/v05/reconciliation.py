from __future__ import annotations


def receipt_matches_request(
    *,
    request_key: str,
    mechanism: int,
    epoch: int,
    receipt_key: str,
    receipt_mechanism: int,
    receipt_epoch: int,
) -> bool:
    if not request_key or not receipt_key:
        raise ValueError("request and receipt keys must be non-empty")
    if type(mechanism) is not int or type(receipt_mechanism) is not int:
        raise TypeError("mechanism ids must be integers")
    if type(epoch) is not int or type(receipt_epoch) is not int:
        raise TypeError("epochs must be integers")
    return (
        request_key == receipt_key
        and mechanism == receipt_mechanism
        and epoch == receipt_epoch
    )


def receipt_is_authoritative(
    *,
    expected_provider: str,
    receipt_provider: str,
    verification_passed: bool,
    binding_matches: bool,
) -> bool:
    if not isinstance(expected_provider, str) or not expected_provider:
        raise ValueError("expected_provider must be a non-empty string")
    if not isinstance(receipt_provider, str) or not receipt_provider:
        raise ValueError("receipt_provider must be a non-empty string")
    if type(verification_passed) is not bool:
        raise TypeError("verification_passed must be bool")
    if type(binding_matches) is not bool:
        raise TypeError("binding_matches must be bool")
    return (
        expected_provider == receipt_provider
        and verification_passed
        and binding_matches
    )
