from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_serialized_storage import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
    TASKS,
    run_benchmark,
    run_one,
    summarize,
)


class V05GateCSerializedStorageTests(unittest.TestCase):
    def test_fresh_storage_seed_set_is_disjoint_from_exploration(self):
        self.assertEqual(FRESH_SEEDS, (20260921, 20260922, 20260923))
        self.assertTrue(set(FRESH_SEEDS).isdisjoint(EXPLORATORY_SEEDS))
        self.assertEqual(TASKS, ("condition", "composition", "language"))

    def test_invalid_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(20260911,), task_names=("condition",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(20260921, 20260921), task_names=("condition",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(20260921,), task_names=("unknown",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(), task_names=("condition",))

    def test_run_one_rejects_invalid_task_seed_without_training(self):
        with self.assertRaises(ValueError):
            run_one("unknown", 20260921)
        with self.assertRaises(ValueError):
            run_one("condition", -1)
        with self.assertRaises(ValueError):
            run_one("condition", 20260912)

    def test_summary_keeps_serialized_and_resident_axes_separate(self):
        records = [
            {
                "task": "condition",
                "seed": 1,
                "direct_export_score": 1.0,
                "dense_module_float32_bytes": 1000,
                "serialized_bytes": 700,
                "serialized_ratio": 0.7,
                "compact_resident_tensor_bytes": 760,
                "compact_resident_ratio": 0.76,
                "reference_runtime_tensor_bytes": 880,
                "reference_runtime_resident_ratio": 0.88,
                "blob_length_matches_accounting": True,
                "byte_stable_round_trip": True,
            },
            {
                "task": "condition",
                "seed": 2,
                "direct_export_score": 0.98,
                "dense_module_float32_bytes": 1000,
                "serialized_bytes": 700,
                "serialized_ratio": 0.7,
                "compact_resident_tensor_bytes": 760,
                "compact_resident_ratio": 0.76,
                "reference_runtime_tensor_bytes": 880,
                "reference_runtime_resident_ratio": 0.88,
                "blob_length_matches_accounting": True,
                "byte_stable_round_trip": True,
            },
        ]
        result = summarize(records)["tasks"]["condition"]
        self.assertAlmostEqual(result["mean_direct_export_score"], 0.99)
        self.assertEqual(result["min_direct_export_score"], 0.98)
        self.assertEqual(result["serialized_bytes"], 700)
        self.assertEqual(result["compact_resident_tensor_bytes"], 760)
        self.assertEqual(result["reference_runtime_tensor_bytes"], 880)
        self.assertEqual(result["serialized_ratio"], 0.7)
        self.assertEqual(result["compact_resident_ratio"], 0.76)
        self.assertEqual(result["reference_runtime_resident_ratio"], 0.88)
        self.assertTrue(result["all_blob_lengths_match_accounting"])
        self.assertTrue(result["all_round_trips_byte_stable"])

    def test_summary_rejects_empty_records(self):
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
