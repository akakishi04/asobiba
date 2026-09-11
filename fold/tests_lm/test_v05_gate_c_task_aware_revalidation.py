from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_task_aware_revalidation import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
    TUNING_SPECS,
    run_benchmark,
    run_one,
    summarize,
)
from fold_lm.v05_benchmarks.gate_c_task_quality import TASKS


class V05GateCTaskAwareRevalidationTests(unittest.TestCase):
    def test_fresh_seed_set_is_explicit_and_disjoint_from_exploration(self):
        self.assertEqual(FRESH_SEEDS, (20260921, 20260922, 20260923))
        self.assertEqual(EXPLORATORY_SEEDS, (20260911, 20260912, 20260913))
        self.assertTrue(set(FRESH_SEEDS).isdisjoint(EXPLORATORY_SEEDS))

    def test_all_three_gate_b_representative_tasks_have_fixed_tuning_specs(self):
        self.assertEqual(tuple(TUNING_SPECS), TASKS)
        self.assertEqual(TUNING_SPECS["condition"], {"steps": 260, "learning_rate": 0.002, "batch_size": 32})
        self.assertEqual(TUNING_SPECS["composition"], {"steps": 300, "learning_rate": 0.002, "batch_size": 64})
        self.assertEqual(TUNING_SPECS["language"], {"steps": 600, "learning_rate": 0.002, "batch_size": 24})

    def test_exploratory_seed_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_one("composition", EXPLORATORY_SEEDS[0])
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(EXPLORATORY_SEEDS[0],), task_names=("composition",))

    def test_invalid_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_one("unknown", FRESH_SEEDS[0])
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(FRESH_SEEDS[0], FRESH_SEEDS[0]), task_names=("condition",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(FRESH_SEEDS[0],), task_names=("condition", "condition"))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(FRESH_SEEDS[0],), task_names=("unknown",))

    def test_summary_keeps_quality_capacity_structure_and_direct_parity_separate(self):
        records = []
        for task, high, pre, post, ratio, max_e, direct_gap in (
            ("condition", 1.0, 0.9, 0.99, 0.75, 0.15, 0.0),
            ("composition", 1.0, 0.6, 1.0, 0.6875, 0.15, 0.0),
            ("language", 1.0, 0.95, 1.0, 0.6875, 0.15, 0.0),
        ):
            records.append(
                {
                    "task": task,
                    "high_precision_score": high,
                    "pre_task_tuning_score": pre,
                    "post_task_tuning_score": post,
                    "post_delta": post - high,
                    "recovered_score": post - pre,
                    "module_payload_ratio": ratio,
                    "max_observed_abs_correction": max_e,
                    "direct_export_score_gap": direct_gap,
                    "payload_unchanged": True,
                    "codes_unchanged": True,
                    "correction_coordinates_unchanged": True,
                }
            )
        summary = summarize(records)["tasks"]
        self.assertEqual(set(summary), set(TASKS))
        self.assertEqual(summary["composition"]["mean_post_task_tuning_score"], 1.0)
        self.assertEqual(summary["composition"]["mean_module_payload_ratio"], 0.6875)
        self.assertEqual(summary["composition"]["max_abs_direct_export_score_gap"], 0.0)
        self.assertTrue(summary["composition"]["all_payload_unchanged"])
        self.assertTrue(summary["composition"]["all_codes_unchanged"])
        self.assertTrue(summary["composition"]["all_correction_coordinates_unchanged"])


if __name__ == "__main__":
    unittest.main()
