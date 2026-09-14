"""Small runtime primitives for reconciliation receipts."""
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
