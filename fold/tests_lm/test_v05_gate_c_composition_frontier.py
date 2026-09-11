from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_composition_frontier import (
    PROFILE_ORDER,
    PROFILES,
    run_benchmark,
    summarize,
)


class V05GateCCompositionFrontierTests(unittest.TestCase):
    def test_profile_ladder_is_explicit_and_ordered(self):
        self.assertEqual(
            PROFILE_ORDER,
            ("balanced", "finer_blocks", "richer_codebooks", "high_fidelity"),
        )
        self.assertEqual(tuple(PROFILES), PROFILE_ORDER)

    def test_profiles_stay_within_bounded_correction_contract(self):
        for profile in PROFILES.values():
            self.assertLessEqual(profile.correction_fraction, 0.05)
            self.assertLessEqual(profile.max_abs_correction, 0.25)
            self.assertGreater(profile.block_rows, 0)
            self.assertGreater(profile.block_cols, 0)
            self.assertGreater(profile.codebook_count, 0)
            self.assertGreater(profile.entries_per_codebook, 0)

    def test_frontier_increases_representation_capacity_axes(self):
        balanced = PROFILES["balanced"]
        finer = PROFILES["finer_blocks"]
        richer = PROFILES["richer_codebooks"]
        high = PROFILES["high_fidelity"]
        self.assertLess(finer.block_rows * finer.block_cols, balanced.block_rows * balanced.block_cols)
        self.assertGreater(richer.codebook_count * richer.entries_per_codebook,
                           balanced.codebook_count * balanced.entries_per_codebook)
        self.assertLessEqual(high.block_rows * high.block_cols, finer.block_rows * finer.block_cols)
        self.assertGreaterEqual(high.codebook_count, richer.codebook_count)
        self.assertGreater(high.correction_fraction, balanced.correction_fraction)

    def test_summary_keeps_quality_capacity_and_reconstruction_separate(self):
        records = []
        for seed, score, payload, up_mse, down_mse in (
            (1, 0.75, 0.60, 0.01, 0.02),
            (2, 1.00, 0.62, 0.005, 0.01),
        ):
            records.append(
                {
                    "seed": seed,
                    "profile": "balanced",
                    "high_precision_score": 1.0,
                    "compressed_score": score,
                    "score_delta": score - 1.0,
                    "module_payload_ratio": payload,
                    "up_final_reconstruction_mse": up_mse,
                    "down_final_reconstruction_mse": down_mse,
                    "max_observed_abs_correction": 0.1,
                }
            )
        summary = summarize(records)["profiles"]["balanced"]
        self.assertEqual(summary["runs"], 2)
        self.assertAlmostEqual(summary["mean_compressed_score"], 0.875)
        self.assertAlmostEqual(summary["min_compressed_score"], 0.75)
        self.assertAlmostEqual(summary["mean_module_payload_ratio"], 0.61)
        self.assertAlmostEqual(summary["mean_up_final_reconstruction_mse"], 0.0075)
        self.assertAlmostEqual(summary["mean_down_final_reconstruction_mse"], 0.015)

    def test_invalid_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=())
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1, 1))
        with self.assertRaises(ValueError):
            run_benchmark(profile_names=())
        with self.assertRaises(ValueError):
            run_benchmark(profile_names=("unknown",))


if __name__ == "__main__":
    unittest.main()
