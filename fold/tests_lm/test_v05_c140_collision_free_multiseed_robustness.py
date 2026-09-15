from __future__ import annotations

import unittest

import torch

from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
from fold_lm.v05_benchmarks import gate_e_c140_collision_free_multiseed_robustness as c140


class V05C140CollisionFreeMultiseedRobustnessTests(unittest.TestCase):
    def test_seed_set_is_fresh_and_disjoint_from_c139(self):
        self.assertEqual(len(c140.SEEDS), 12)
        self.assertEqual(len(set(c140.SEEDS)), 12)
        self.assertTrue(set(c140.SEEDS).isdisjoint(set(c139.SEEDS)))

    def test_positive_expected_margin_marks_correct_prediction(self):
        result = c140._expected_margin_from_scores(
            torch.tensor([0.9, 0.2, 0.1], dtype=torch.float32),
            0,
        )
        self.assertEqual(result["predicted_address"], 0)
        self.assertTrue(result["correct"])
        self.assertGreater(result["expected_margin"], 0.0)
        self.assertEqual(result["best_other_address"], 1)

    def test_negative_expected_margin_marks_competing_prediction(self):
        result = c140._expected_margin_from_scores(
            torch.tensor([0.3, 0.5, 0.2], dtype=torch.float32),
            0,
        )
        self.assertEqual(result["predicted_address"], 1)
        self.assertFalse(result["correct"])
        self.assertLess(result["expected_margin"], 0.0)
        self.assertEqual(result["best_other_address"], 1)


if __name__ == "__main__":
    unittest.main()
