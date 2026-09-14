from __future__ import annotations


def receipt_scope_matches(
    *,
    receipt_id: str,
    scope_receipt_id: str,
    expected_source: str,
    scope_source: str,
    current_epoch: int,
    scope_epoch: int,
) -> bool:
    if not receipt_id or not scope_receipt_id:
        raise ValueError("receipt ids must be non-empty")
    if not expected_source or not scope_source:
        raise ValueError("source ids must be non-empty")
    if type(current_epoch) is not int or type(scope_epoch) is not int:
        raise TypeError("epochs must be integers")
    return (
        receipt_id == scope_receipt_id
        and expected_source == scope_source
        and current_epoch == scope_epoch
    )
