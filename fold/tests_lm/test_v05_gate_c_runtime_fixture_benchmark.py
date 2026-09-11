from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_runtime_fixture_benchmark import (
    DEFAULT_VARIANTS,
    _progress_line,
    _validate_variants,
    summarize_timings,
)


class V05GateCRuntimeFixtureBenchmarkTests(unittest.TestCase):
    def test_default_variants_skip_literal_direct_path(self):
        self.assertEqual(DEFAULT_VARIANTS, ("dense", "compact"))
        self.assertNotIn("direct", DEFAULT_VARIANTS)

    def test_variant_validation_requires_distinct_dense_baseline(self):
        self.assertEqual(_validate_variants(("dense", "compact")), ("dense", "compact"))
        with self.assertRaises(ValueError):
            _validate_variants(())
        with self.assertRaises(ValueError):
            _validate_variants(("compact",))
        with self.assertRaises(ValueError):
            _validate_variants(("dense", "dense"))
        with self.assertRaises(ValueError):
            _validate_variants(("dense", "unknown"))

    def test_progress_line_shows_elapsed_percent_and_eta(self):
        line = _progress_line(1, 2, 12.0, "variant=dense timing")
        self.assertIn("1/2", line)
        self.assertIn("50.0%", line)
        self.assertIn("elapsed=12.0s", line)
        self.assertIn("eta=12.0s", line)
        self.assertIn("variant=dense timing", line)

    def test_summary_reports_runtime_ratios_and_scores(self):
        timings = {
            "dense": {
                "mean_seconds": 0.004,
                "median_seconds": 0.0039,
                "p90_seconds": 0.0044,
            },
            "compact": {
                "mean_seconds": 0.010,
                "median_seconds": 0.0098,
                "p90_seconds": 0.011,
            },
        }
        summary = summarize_timings(timings, {"dense": 1.0, "compact": 1.0})
        self.assertAlmostEqual(summary["variants"]["dense"]["runtime_ratio_vs_dense"], 1.0)
        self.assertAlmostEqual(summary["variants"]["compact"]["runtime_ratio_vs_dense"], 2.5)
        self.assertAlmostEqual(summary["variants"]["compact"]["mean_milliseconds"], 10.0)
        self.assertEqual(summary["variants"]["compact"]["score"], 1.0)

    def test_summary_rejects_missing_or_invalid_dense_timing(self):
        with self.assertRaises(ValueError):
            summarize_timings({}, {})
        with self.assertRaises(ValueError):
            summarize_timings(
                {"compact": {"mean_seconds": 0.01, "median_seconds": 0.01, "p90_seconds": 0.01}},
                {"compact": 1.0},
            )
        with self.assertRaises(ValueError):
            summarize_timings(
                {"dense": {"mean_seconds": 0.0, "median_seconds": 0.0, "p90_seconds": 0.0}},
                {"dense": 1.0},
            )


if __name__ == "__main__":
    unittest.main()
