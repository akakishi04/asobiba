import unittest

from fold_lm.v05_benchmarks.gate_e_c127_transition_recovery_helper import (
    naive_pending_replay_failure_detected,
)


class V05C127NegativeControlTests(unittest.TestCase):
    def test_naive_pending_replay_duplicates_applied_effect(self):
        self.assertTrue(naive_pending_replay_failure_detected())


if __name__ == "__main__":
    unittest.main()
