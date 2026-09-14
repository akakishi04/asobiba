import unittest

from fold_lm.v05.reconciliation import receipt_is_authoritative, receipt_matches_request


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

    def test_authoritative_receipt_is_accepted(self):
        self.assertTrue(
            receipt_is_authoritative(
                expected_provider="provider-a",
                receipt_provider="provider-a",
                verification_passed=True,
                binding_matches=True,
            )
        )

    def test_wrong_provider_is_rejected(self):
        self.assertFalse(
            receipt_is_authoritative(
                expected_provider="provider-a",
                receipt_provider="provider-b",
                verification_passed=True,
                binding_matches=True,
            )
        )

    def test_failed_verification_is_rejected(self):
        self.assertFalse(
            receipt_is_authoritative(
                expected_provider="provider-a",
                receipt_provider="provider-a",
                verification_passed=False,
                binding_matches=True,
            )
        )

    def test_binding_failure_is_rejected_by_authority_gate(self):
        self.assertFalse(
            receipt_is_authoritative(
                expected_provider="provider-a",
                receipt_provider="provider-a",
                verification_passed=True,
                binding_matches=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
