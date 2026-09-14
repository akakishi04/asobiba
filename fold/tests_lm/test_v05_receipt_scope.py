import unittest

from fold_lm.v05.receipt_scope import receipt_scope_matches


class V05ReceiptScopeTests(unittest.TestCase):
    def test_exact_scope_matches(self):
        self.assertTrue(
            receipt_scope_matches(
                receipt_id="receipt-1",
                scope_receipt_id="receipt-1",
                expected_source="verifier-a",
                scope_source="verifier-a",
                current_epoch=9,
                scope_epoch=9,
            )
        )

    def test_other_receipt_is_rejected(self):
        self.assertFalse(
            receipt_scope_matches(
                receipt_id="receipt-1",
                scope_receipt_id="receipt-2",
                expected_source="verifier-a",
                scope_source="verifier-a",
                current_epoch=9,
                scope_epoch=9,
            )
        )

    def test_other_source_is_rejected(self):
        self.assertFalse(
            receipt_scope_matches(
                receipt_id="receipt-1",
                scope_receipt_id="receipt-1",
                expected_source="verifier-a",
                scope_source="verifier-b",
                current_epoch=9,
                scope_epoch=9,
            )
        )

    def test_stale_scope_epoch_is_rejected(self):
        self.assertFalse(
            receipt_scope_matches(
                receipt_id="receipt-1",
                scope_receipt_id="receipt-1",
                expected_source="verifier-a",
                scope_source="verifier-a",
                current_epoch=9,
                scope_epoch=8,
            )
        )


if __name__ == "__main__":
    unittest.main()
