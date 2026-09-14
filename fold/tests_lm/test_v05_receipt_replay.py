import unittest

from fold_lm.v05.receipt_replay import claim_receipt_once


class V05ReceiptReplayTests(unittest.TestCase):
    def test_first_delivery_is_claimed(self):
        claimed, state = claim_receipt_once(
            receipt_id="receipt-1",
            processed_receipt_ids=frozenset(),
        )
        self.assertTrue(claimed)
        self.assertEqual(state, frozenset(("receipt-1",)))

    def test_duplicate_delivery_is_rejected_without_state_change(self):
        initial = frozenset(("receipt-1",))
        claimed, state = claim_receipt_once(
            receipt_id="receipt-1",
            processed_receipt_ids=initial,
        )
        self.assertFalse(claimed)
        self.assertIs(state, initial)

    def test_distinct_receipt_is_independent(self):
        claimed, state = claim_receipt_once(
            receipt_id="receipt-2",
            processed_receipt_ids=frozenset(("receipt-1",)),
        )
        self.assertTrue(claimed)
        self.assertEqual(state, frozenset(("receipt-1", "receipt-2")))

    def test_invalid_state_type_is_rejected(self):
        with self.assertRaises(TypeError):
            claim_receipt_once(
                receipt_id="receipt-1",
                processed_receipt_ids={"receipt-0"},
            )


if __name__ == "__main__":
    unittest.main()
