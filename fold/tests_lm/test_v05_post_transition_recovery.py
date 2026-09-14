import unittest

from fold_lm.v05.post_transition_recovery import (
    APPLIED,
    NOT_APPLIED,
    STILL_UNKNOWN,
    plan_post_transition_recovery,
)


class V05PostTransitionRecoveryTests(unittest.TestCase):
    def test_applied_completes_without_replay(self):
        plan = plan_post_transition_recovery(APPLIED)
        self.assertFalse(plan.replay_required)
        self.assertTrue(plan.complete_now)
        self.assertFalse(plan.hold_pending)

    def test_not_applied_requires_replay_before_completion(self):
        plan = plan_post_transition_recovery(NOT_APPLIED)
        self.assertTrue(plan.replay_required)
        self.assertFalse(plan.complete_now)
        self.assertFalse(plan.hold_pending)

    def test_still_unknown_holds_pending(self):
        plan = plan_post_transition_recovery(STILL_UNKNOWN)
        self.assertFalse(plan.replay_required)
        self.assertFalse(plan.complete_now)
        self.assertTrue(plan.hold_pending)

    def test_unknown_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_post_transition_recovery("OTHER")


if __name__ == "__main__":
    unittest.main()
