import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from fold_lm.v05.recovery_ownership import RecoveryOwnershipRegistry


class V05RecoveryOwnershipTests(unittest.TestCase):
    def test_first_owner_wins(self):
        registry = RecoveryOwnershipRegistry()
        self.assertTrue(registry.acquire("r1", "w1"))
        self.assertEqual(registry.owner("r1"), "w1")

    def test_second_owner_loses(self):
        registry = RecoveryOwnershipRegistry()
        self.assertTrue(registry.acquire("r1", "w1"))
        self.assertFalse(registry.acquire("r1", "w2"))
        self.assertEqual(registry.owner("r1"), "w1")

    def test_only_owner_can_release(self):
        registry = RecoveryOwnershipRegistry()
        self.assertTrue(registry.acquire("r1", "w1"))
        self.assertFalse(registry.release("r1", "w2"))
        self.assertTrue(registry.release("r1", "w1"))
        self.assertIsNone(registry.owner("r1"))

    def test_distinct_receipts_are_independent(self):
        registry = RecoveryOwnershipRegistry()
        self.assertTrue(registry.acquire("r1", "w1"))
        self.assertTrue(registry.acquire("r2", "w2"))
        self.assertEqual(registry.owner("r1"), "w1")
        self.assertEqual(registry.owner("r2"), "w2")

    def test_concurrent_acquire_has_one_owner(self):
        workers = 8
        registry = RecoveryOwnershipRegistry()
        barrier = threading.Barrier(workers)

        def attempt(index):
            worker = f"w{index}"
            barrier.wait()
            return worker, registry.acquire("r1", worker)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(attempt, range(workers)))
        winners = [worker for worker, won in results if won]
        self.assertEqual(len(winners), 1)
        self.assertEqual(registry.owner("r1"), winners[0])


if __name__ == "__main__":
    unittest.main()
