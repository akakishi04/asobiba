from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_compile_fixture_benchmark import (
    VARIANTS,
    _progress_line,
    summarize_timings,
)


class V05GateCCompileFixtureBenchmarkTests(unittest.TestCase):
    def test_variants_are_explicit_and_complete(self):
        self.assertEqual(
            VARIANTS,
            (
                "eager_dense",
                "eager_compact",
                "compiled_dense",
                "compiled_compact",
            ),
        )

    def test_progress_line_reports_elapsed_and_eta(self):
        line = _progress_line(2, 6, 12.0, "compiled_dense")
        self.assertIn("2/6", line)
        self.assertIn("33.3%", line)
        self.assertIn("elapsed=12.0s", line)
        self.assertIn("eta=24.0s", line)
        self.assertIn("compiled_dense", line)

    def test_progress_line_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            _progress_line(-1, 6, 1.0, "x")
        with self.assertRaises(ValueError):
            _progress_line(0, 0, 1.0, "x")
        with self.assertRaises(ValueError):
            _progress_line(0, 6, -1.0, "x")
        with self.assertRaises(ValueError):
            _progress_line(0, 6, 1.0, "")

    def test_summary_separates_compile_and_runtime_comparisons(self):
        def timing(seconds: float) -> dict:
            return {
                "mean_seconds": seconds,
                "median_seconds": seconds,
                "p90_seconds": seconds,
            }

        summary = summarize_timings(
            {
                "eager_dense": timing(0.004),
                "eager_compact": timing(0.012),
                "compiled_dense": timing(0.003),
                "compiled_compact": timing(0.006),
            },
            {
                "compiled_dense": 2.0,
                "compiled_compact": 4.0,
            },
        )
        self.assertAlmostEqual(summary["compiled_compact_ratio_vs_compiled_dense"], 2.0)
        self.assertAlmostEqual(summary["dense_compile_speedup"], 4.0 / 3.0)
        self.assertAlmostEqual(summary["compact_compile_speedup"], 2.0)
        self.assertEqual(
            summary["variants"]["compiled_compact"]["compile_first_forward_seconds"],
            4.0,
        )

    def test_summary_requires_all_variants_and_compile_latency(self):
        timing = {
            "mean_seconds": 0.01,
            "median_seconds": 0.01,
            "p90_seconds": 0.01,
        }
        with self.assertRaises(ValueError):
            summarize_timings({"eager_dense": timing}, {})
        with self.assertRaises(ValueError):
            summarize_timings(
                {name: dict(timing) for name in VARIANTS},
                {"compiled_dense": 1.0},
            )


if __name__ == "__main__":
    unittest.main()
