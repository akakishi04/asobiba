import unittest

from fold_lm.v05.recovery_fencing import RecoveryFencingRegistry


class V05RecoveryFencingTests(unittest.TestCase):
    def test_first_owner_gets_first_token(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        self.assertEqual(token, 1)
        self.assertTrue(registry.allows("r1", "worker-a", token, now=1))

    def test_active_lease_blocks_takeover(self):
        registry = RecoveryFencingRegistry()
        self.assertEqual(registry.acquire("r1", "worker-a", now=0, lease_ticks=5), 1)
        self.assertIsNone(registry.acquire("r1", "worker-b", now=4, lease_ticks=5))

    def test_expired_lease_allows_higher_token_takeover(self):
        registry = RecoveryFencingRegistry()
        old = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        new = registry.acquire("r1", "worker-b", now=5, lease_ticks=5)
        self.assertEqual(old, 1)
        self.assertEqual(new, 2)

    def test_stale_owner_is_fenced_after_takeover(self):
        registry = RecoveryFencingRegistry()
        old = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        new = registry.acquire("r1", "worker-b", now=5, lease_ticks=5)
        self.assertFalse(registry.allows("r1", "worker-a", old, now=6))
        self.assertTrue(registry.allows("r1", "worker-b", new, now=6))

    def test_stale_owner_cannot_release_new_owner(self):
        registry = RecoveryFencingRegistry()
        old = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        new = registry.acquire("r1", "worker-b", now=5, lease_ticks=5)
        self.assertFalse(registry.release("r1", "worker-a", old))
        self.assertTrue(registry.release("r1", "worker-b", new))

    def test_invalid_lease_duration_is_rejected(self):
        registry = RecoveryFencingRegistry()
        with self.assertRaises(ValueError):
            registry.acquire("r1", "worker-a", now=0, lease_ticks=0)


if __name__ == "__main__":
    unittest.main()
