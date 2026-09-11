from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_runtime_benchmark import (
    DEFAULT_RUNTIME_SEEDS,
    VARIANTS,
    _format_duration,
    format_progress_line,
    run_benchmark,
    summarize,
)
from fold_lm.v05_benchmarks.gate_c_task_aware_revalidation import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
)


class V05GateCRuntimeBenchmarkTests(unittest.TestCase):
    def test_variants_and_runtime_seed_are_explicit(self):
        self.assertEqual(VARIANTS, ("dense", "direct", "compact"))
        self.assertEqual(DEFAULT_RUNTIME_SEEDS, (FRESH_SEEDS[0],))
        self.assertTrue(set(DEFAULT_RUNTIME_SEEDS).isdisjoint(EXPLORATORY_SEEDS))

    def test_duration_and_progress_line_show_elapsed_and_eta(self):
        self.assertEqual(_format_duration(12.34), "12.3s")
        self.assertEqual(_format_duration(65.0), "1m05.0s")
        line = format_progress_line(3, 9, 30.0, "task=composition variant=compact")
        self.assertIn("3/9", line)
        self.assertIn("33.3%", line)
        self.assertIn("elapsed=30.0s", line)
        self.assertIn("eta=1m00.0s", line)
        self.assertIn("task=composition", line)

    def test_progress_validation_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            _format_duration(-1.0)
        with self.assertRaises(ValueError):
            format_progress_line(-1, 5, 0.0, "x")
        with self.assertRaises(ValueError):
            format_progress_line(6, 5, 0.0, "x")
        with self.assertRaises(ValueError):
            format_progress_line(0, 0, 0.0, "x")
        with self.assertRaises(ValueError):
            format_progress_line(0, 5, 0.0, "")

    def test_summary_keeps_variants_and_dense_ratios_separate(self):
        records = [
            {
                "task": "composition",
                "seed": 1,
                "scores": {"dense": 1.0, "direct": 1.0, "compact": 1.0},
                "timings": {
                    "dense": {"mean_seconds": 0.010},
                    "direct": {"mean_seconds": 0.050},
                    "compact": {"mean_seconds": 0.020},
                },
            },
            {
                "task": "composition",
                "seed": 2,
                "scores": {"dense": 1.0, "direct": 1.0, "compact": 1.0},
                "timings": {
                    "dense": {"mean_seconds": 0.020},
                    "direct": {"mean_seconds": 0.100},
                    "compact": {"mean_seconds": 0.030},
                },
            },
        ]
        summary = summarize(records)["tasks"]["composition"]
        self.assertEqual(summary["runs"], 2)
        self.assertAlmostEqual(summary["variants"]["dense"]["runtime_ratio_vs_dense"], 1.0)
        self.assertAlmostEqual(summary["variants"]["direct"]["runtime_ratio_vs_dense"], 5.0)
        self.assertAlmostEqual(summary["variants"]["compact"]["runtime_ratio_vs_dense"], 5.0 / 3.0)
        self.assertEqual(summary["max_abs_direct_compact_score_gap"], 0.0)

    def test_invalid_benchmark_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=())
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(EXPLORATORY_SEEDS[0],))
        with self.assertRaises(ValueError):
            run_benchmark(task_names=())
        with self.assertRaises(ValueError):
            run_benchmark(task_names=("unknown",))
        with self.assertRaises(ValueError):
            run_benchmark(warmup=-1)
        with self.assertRaises(ValueError):
            run_benchmark(repeats=0)


if __name__ == "__main__":
    unittest.main()
