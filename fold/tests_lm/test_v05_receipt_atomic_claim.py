import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.receipt_atomic_claim import AtomicReceiptClaimRegistry


class V05ReceiptAtomicClaimTests(unittest.TestCase):
    def test_first_claim_wins(self):
        registry = AtomicReceiptClaimRegistry()
        self.assertTrue(registry.claim("r1"))
        self.assertEqual(registry.snapshot(), frozenset(("r1",)))

    def test_duplicate_claim_loses(self):
        registry = AtomicReceiptClaimRegistry()
        self.assertTrue(registry.claim("r1"))
        self.assertFalse(registry.claim("r1"))
        self.assertEqual(registry.snapshot(), frozenset(("r1",)))

    def test_distinct_receipts_are_independent(self):
        registry = AtomicReceiptClaimRegistry()
        self.assertTrue(registry.claim("r1"))
        self.assertTrue(registry.claim("r2"))
        self.assertEqual(registry.snapshot(), frozenset(("r1", "r2")))

    def test_concurrent_duplicate_claim_has_one_winner(self):
        workers = 8
        registry = AtomicReceiptClaimRegistry()
        barrier = threading.Barrier(workers)

        def attempt():
            barrier.wait()
            return registry.claim("shared")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda _: attempt(), range(workers)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(registry.snapshot(), frozenset(("shared",)))

    def test_invalid_initial_state_is_rejected(self):
        with self.assertRaises(TypeError):
            AtomicReceiptClaimRegistry(set())


if __name__ == "__main__":
    unittest.main()
