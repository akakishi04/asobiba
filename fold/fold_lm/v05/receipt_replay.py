from __future__ import annotations


def claim_receipt_once(
    *,
    receipt_id: str,
    processed_receipt_ids: frozenset[str],
) -> tuple[bool, frozenset[str]]:
    if not isinstance(receipt_id, str) or not receipt_id:
        raise ValueError("receipt_id must be a non-empty string")
    if type(processed_receipt_ids) is not frozenset:
        raise TypeError("processed_receipt_ids must be frozenset")
    if any(not isinstance(item, str) or not item for item in processed_receipt_ids):
        raise ValueError("processed receipt ids must be non-empty strings")
    if receipt_id in processed_receipt_ids:
        return False, processed_receipt_ids
    return True, processed_receipt_ids | frozenset((receipt_id,))
