import unittest

from fold_lm.v05.recovery_fencing import RecoveryFencingRegistry


class V05RecoveryLeaseRenewalTests(unittest.TestCase):
    def test_valid_owner_renews_before_expiry_without_changing_token(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        self.assertEqual(token, 1)
        self.assertTrue(registry.renew("r1", "worker-a", token, now=4, lease_ticks=5))
        lease = registry.lease("r1")
        self.assertEqual(lease.token, token)
        self.assertEqual(lease.expires_at, 9)

    def test_renewal_never_shortens_existing_lease(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=10)
        self.assertTrue(registry.renew("r1", "worker-a", token, now=1, lease_ticks=2))
        self.assertEqual(registry.lease("r1").expires_at, 10)

    def test_exact_expiry_cannot_renew(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        self.assertFalse(registry.renew("r1", "worker-a", token, now=5, lease_ticks=5))

    def test_wrong_owner_cannot_renew(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        self.assertFalse(registry.renew("r1", "worker-b", token, now=4, lease_ticks=5))

    def test_stale_token_cannot_renew_after_takeover(self):
        registry = RecoveryFencingRegistry()
        old = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        new = registry.acquire("r1", "worker-b", now=5, lease_ticks=5)
        self.assertEqual(new, 2)
        self.assertFalse(registry.renew("r1", "worker-a", old, now=6, lease_ticks=5))

    def test_takeover_is_blocked_at_old_expiry_after_renewal(self):
        registry = RecoveryFencingRegistry()
        token = registry.acquire("r1", "worker-a", now=0, lease_ticks=5)
        self.assertTrue(registry.renew("r1", "worker-a", token, now=4, lease_ticks=5))
        self.assertIsNone(registry.acquire("r1", "worker-b", now=5, lease_ticks=5))
        self.assertEqual(registry.acquire("r1", "worker-b", now=9, lease_ticks=5), 2)

    def test_naive_inclusive_expiry_would_disagree_at_boundary(self):
        expires_at = 5
        now = 5
        naive_active = now <= expires_at
        production_active = now < expires_at
        self.assertTrue(naive_active)
        self.assertFalse(production_active)


if __name__ == "__main__":
    unittest.main()
