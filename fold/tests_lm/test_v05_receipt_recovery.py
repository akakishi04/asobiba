import unittest

from fold_lm.v05.receipt_recovery import ReceiptRecoveryRegistry, ReceiptRecoverySnapshot


class V05ReceiptRecoveryTests(unittest.TestCase):
    def test_claim_survives_snapshot_restore(self):
        registry = ReceiptRecoveryRegistry()
        self.assertTrue(registry.claim("r1"))
        restored = ReceiptRecoveryRegistry(registry.snapshot())
        self.assertTrue(restored.is_pending("r1"))
        self.assertFalse(restored.claim("r1"))

    def test_completion_survives_snapshot_restore(self):
        registry = ReceiptRecoveryRegistry()
        self.assertTrue(registry.claim("r1"))
        registry.complete("r1")
        restored = ReceiptRecoveryRegistry(registry.snapshot())
        self.assertFalse(restored.is_pending("r1"))
        self.assertFalse(restored.claim("r1"))
        self.assertIn("r1", restored.snapshot().completed_receipt_ids)

    def test_multiple_restarts_preserve_pending_state(self):
        registry = ReceiptRecoveryRegistry()
        self.assertTrue(registry.claim("r1"))
        for _ in range(3):
            registry = ReceiptRecoveryRegistry(registry.snapshot())
            self.assertTrue(registry.is_pending("r1"))
            self.assertFalse(registry.claim("r1"))

    def test_complete_requires_pending_receipt(self):
        registry = ReceiptRecoveryRegistry()
        with self.assertRaises(ValueError):
            registry.complete("r1")

    def test_overlapping_snapshot_state_is_rejected(self):
        with self.assertRaises(ValueError):
            ReceiptRecoverySnapshot(
                pending_receipt_ids=frozenset(("r1",)),
                completed_receipt_ids=frozenset(("r1",)),
            )


if __name__ == "__main__":
    unittest.main()
