from __future__ import annotations

import math
import unittest

from fold_lm.v05_benchmarks.gate_c_triton_fixture_benchmark import (
    VARIANTS,
    summarize_timings,
)


class V05GateCTritonFixtureBenchmarkTests(unittest.TestCase):
    def _timing(self, mean: float) -> dict:
        return {
            "mean_seconds": mean,
            "median_seconds": mean * 0.95,
            "p90_seconds": mean * 1.10,
        }

    def test_variants_are_explicit_and_complete(self) -> None:
        self.assertEqual(VARIANTS, ("dense", "compact", "triton"))

    def test_summary_reports_full_model_ratios(self) -> None:
        timings = {
            "dense": self._timing(0.004),
            "compact": self._timing(0.012),
            "triton": self._timing(0.006),
        }
        scores = {"dense": 1.0, "compact": 1.0, "triton": 1.0}
        summary = summarize_timings(timings, scores)
        self.assertAlmostEqual(summary["triton_ratio_vs_dense"], 1.5)
        self.assertAlmostEqual(summary["compact_to_triton_speedup"], 2.0)
        self.assertAlmostEqual(
            summary["variants"]["compact"]["runtime_ratio_vs_dense"], 3.0
        )

    def test_summary_preserves_scores(self) -> None:
        timings = {name: self._timing(0.004 + index * 0.001) for index, name in enumerate(VARIANTS)}
        scores = {"dense": 0.99, "compact": 1.0, "triton": 1.0}
        summary = summarize_timings(timings, scores)
        self.assertEqual(summary["variants"]["dense"]["score"], 0.99)
        self.assertEqual(summary["variants"]["triton"]["score"], 1.0)

    def test_summary_requires_all_variants(self) -> None:
        timings = {"dense": self._timing(0.004), "compact": self._timing(0.010)}
        scores = {"dense": 1.0, "compact": 1.0, "triton": 1.0}
        with self.assertRaises(ValueError):
            summarize_timings(timings, scores)

    def test_summary_rejects_invalid_means(self) -> None:
        timings = {
            "dense": self._timing(0.004),
            "compact": self._timing(math.inf),
            "triton": self._timing(0.006),
        }
        scores = {"dense": 1.0, "compact": 1.0, "triton": 1.0}
        with self.assertRaises(ValueError):
            summarize_timings(timings, scores)


if __name__ == "__main__":
    unittest.main()
