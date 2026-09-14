import unittest

from fold_lm.v05.reconciliation import receipt_matches_request


class V05ReconciliationTests(unittest.TestCase):
    def test_exact_binding_matches(self):
        self.assertTrue(
            receipt_matches_request(
                request_key="req-1", mechanism=2, epoch=7,
                receipt_key="req-1", receipt_mechanism=2, receipt_epoch=7,
            )
        )

    def test_wrong_key_does_not_match(self):
        self.assertFalse(
            receipt_matches_request(
                request_key="req-1", mechanism=2, epoch=7,
                receipt_key="req-2", receipt_mechanism=2, receipt_epoch=7,
            )
        )

    def test_wrong_mechanism_does_not_match(self):
        self.assertFalse(
            receipt_matches_request(
                request_key="req-1", mechanism=2, epoch=7,
                receipt_key="req-1", receipt_mechanism=3, receipt_epoch=7,
            )
        )

    def test_stale_epoch_does_not_match(self):
        self.assertFalse(
            receipt_matches_request(
                request_key="req-1", mechanism=2, epoch=7,
                receipt_key="req-1", receipt_mechanism=2, receipt_epoch=6,
            )
        )


if __name__ == "__main__":
    unittest.main()
