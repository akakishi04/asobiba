import tempfile
import unittest
from pathlib import Path

from fold_lm.v05.sqlite_recovery_fencing import SqliteRecoveryFencingStore


class V05SqliteRecoveryFencingTests(unittest.TestCase):
    def test_first_acquire_gets_token_one(self):
        with tempfile.TemporaryDirectory() as root:
            store = SqliteRecoveryFencingStore(Path(root) / "f.sqlite")
            self.assertEqual(store.acquire("r1", "worker-a", now=0, lease_ticks=5), 1)

    def test_expired_takeover_gets_higher_token_across_connections(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "f.sqlite"
            first = SqliteRecoveryFencingStore(path)
            second = SqliteRecoveryFencingStore(path)
            self.assertEqual(first.acquire("r1", "worker-a", now=0, lease_ticks=5), 1)
            self.assertEqual(second.acquire("r1", "worker-b", now=5, lease_ticks=5), 2)

    def test_stale_write_is_rejected_and_current_write_is_stored(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "f.sqlite"
            old = SqliteRecoveryFencingStore(path)
            new = SqliteRecoveryFencingStore(path)
            old_token = old.acquire("r1", "worker-a", now=0, lease_ticks=5)
            new_token = new.acquire("r1", "worker-b", now=5, lease_ticks=5)
            self.assertFalse(old.apply_fenced_write("r1", "worker-a", old_token, now=6, effect_key="stale"))
            self.assertTrue(new.apply_fenced_write("r1", "worker-b", new_token, now=6, effect_key="current"))
            effect = old.read_effect("r1")
            self.assertEqual(effect.effect_key, "current")
            self.assertEqual(effect.fencing_token, new_token)

    def test_same_worker_id_old_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "f.sqlite"
            store = SqliteRecoveryFencingStore(path)
            old_token = store.acquire("r1", "worker-a", now=0, lease_ticks=5)
            new_token = store.acquire("r1", "worker-a", now=5, lease_ticks=5)
            self.assertEqual((old_token, new_token), (1, 2))
            self.assertFalse(store.apply_fenced_write("r1", "worker-a", old_token, now=6, effect_key="old"))
            self.assertTrue(store.apply_fenced_write("r1", "worker-a", new_token, now=6, effect_key="new"))


if __name__ == "__main__":
    unittest.main()
