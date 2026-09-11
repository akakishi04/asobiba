from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_b_reproducibility import (
    DEFAULT_SEEDS,
    TASKS,
    summarize_records,
    validate_seeds,
)


class V05GateBReproducibilityTests(unittest.TestCase):
    def test_default_seed_set_is_distinct_and_multi_seed(self):
        self.assertEqual(validate_seeds(DEFAULT_SEEDS), DEFAULT_SEEDS)
        self.assertGreaterEqual(len(DEFAULT_SEEDS), 3)
        self.assertEqual(len(DEFAULT_SEEDS), len(set(DEFAULT_SEEDS)))

    def test_all_gate_b_task_families_are_registered(self):
        self.assertEqual(
            set(TASKS),
            {"copy", "condition", "comparison", "addition", "composition", "language"},
        )

    def test_summary_requires_every_run_to_improve_and_pass(self):
        records = [
            {
                "task": "copy",
                "initial": {"nll": 2.0},
                "final": {"nll": 0.01, "exact_accuracy": 1.0},
                "reference_bar_passed": True,
            },
            {
                "task": "copy",
                "initial": {"nll": 1.5},
                "final": {"nll": 0.02, "exact_accuracy": 0.99},
                "reference_bar_passed": True,
            },
        ]
        summary = summarize_records(records)
        self.assertTrue(summary["all_runs_loss_improved"])
        self.assertTrue(summary["all_reference_bars_passed"])
        self.assertEqual(summary["tasks"]["copy"]["reference_bar_pass_count"], 2)
        self.assertAlmostEqual(summary["tasks"]["copy"]["mean_final_score"], 0.995)
        self.assertAlmostEqual(summary["tasks"]["copy"]["min_final_score"], 0.99)

    def test_summary_exposes_failed_seed_instead_of_averaging_it_away(self):
        records = [
            {
                "task": "language",
                "initial": {"nll": 5.0},
                "final": {"nll": 0.01, "accuracy": 1.0},
                "reference_bar_passed": True,
            },
            {
                "task": "language",
                "initial": {"nll": 5.0},
                "final": {"nll": 3.0, "accuracy": 0.4},
                "reference_bar_passed": False,
            },
        ]
        summary = summarize_records(records)
        self.assertTrue(summary["tasks"]["language"]["all_loss_improved"])
        self.assertFalse(summary["tasks"]["language"]["all_reference_bars_passed"])
        self.assertFalse(summary["all_reference_bars_passed"])
        self.assertEqual(summary["tasks"]["language"]["reference_bar_pass_count"], 1)
        self.assertAlmostEqual(summary["tasks"]["language"]["min_final_score"], 0.4)

    def test_invalid_seed_sets_and_records_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_seeds((1,))
        with self.assertRaises(ValueError):
            validate_seeds((1, 1))
        with self.assertRaises(ValueError):
            validate_seeds((1, -1))
        with self.assertRaises(ValueError):
            summarize_records([])
        with self.assertRaises(ValueError):
            summarize_records(
                [
                    {
                        "task": "unknown",
                        "initial": {},
                        "final": {},
                        "reference_bar_passed": False,
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
