from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_compile_triton_fixture_benchmark import (
    VARIANTS,
    summarize_timings,
)


class V05GateCCompileTritonFixtureBenchmarkTests(unittest.TestCase):
    def _timings(self):
        return {
            "eager_dense": {
                "mean_seconds": 0.0040,
                "median_seconds": 0.0039,
                "p90_seconds": 0.0048,
            },
            "compiled_dense": {
                "mean_seconds": 0.0035,
                "median_seconds": 0.0034,
                "p90_seconds": 0.0041,
            },
            "eager_triton": {
                "mean_seconds": 0.0060,
                "median_seconds": 0.0058,
                "p90_seconds": 0.0070,
            },
            "compiled_triton": {
                "mean_seconds": 0.0050,
                "median_seconds": 0.0049,
                "p90_seconds": 0.0058,
            },
        }

    def test_variants_are_explicit_and_complete(self):
        self.assertEqual(
            VARIANTS,
            ("eager_dense", "compiled_dense", "eager_triton", "compiled_triton"),
        )

    def test_summary_reports_compile_speedups_and_ratios(self):
        summary = summarize_timings(
            self._timings(),
            {"compiled_dense": 2.0, "compiled_triton": 3.0},
        )
        self.assertAlmostEqual(summary["dense_compile_speedup"], 0.0040 / 0.0035)
        self.assertAlmostEqual(summary["triton_compile_speedup"], 0.0060 / 0.0050)
        self.assertAlmostEqual(
            summary["compiled_triton_ratio_vs_compiled_dense"],
            0.0050 / 0.0035,
        )
        self.assertAlmostEqual(
            summary["compiled_triton_ratio_vs_eager_dense"],
            0.0050 / 0.0040,
        )

    def test_summary_keeps_compile_latency_separate(self):
        summary = summarize_timings(
            self._timings(),
            {"compiled_dense": 2.5, "compiled_triton": 4.5},
        )
        self.assertEqual(
            summary["variants"]["compiled_dense"]["compile_first_forward_seconds"],
            2.5,
        )
        self.assertEqual(
            summary["variants"]["compiled_triton"]["compile_first_forward_seconds"],
            4.5,
        )
        self.assertNotIn(
            "compile_first_forward_seconds",
            summary["variants"]["eager_triton"],
        )

    def test_summary_requires_all_variants(self):
        timings = self._timings()
        timings.pop("compiled_triton")
        with self.assertRaisesRegex(ValueError, "all four"):
            summarize_timings(
                timings,
                {"compiled_dense": 2.0, "compiled_triton": 3.0},
            )

    def test_summary_requires_compile_latencies(self):
        with self.assertRaisesRegex(ValueError, "compile first-forward latency"):
            summarize_timings(
                self._timings(),
                {"compiled_dense": 2.0},
            )


if __name__ == "__main__":
    unittest.main()
