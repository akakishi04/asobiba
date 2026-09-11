from __future__ import annotations

import unittest

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_task_quality import (
    CompressionProfile,
    DEFAULT_PROFILE,
    TASKS,
    compress_trained_core,
    run_benchmark,
    summarize,
)


class V05GateCTaskQualityTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)

    def _small_profile(self) -> CompressionProfile:
        return CompressionProfile(
            block_rows=4,
            block_cols=4,
            codebook_count=2,
            entries_per_codebook=4,
            correction_fraction=0.0,
            max_abs_correction=0.0,
            initial_tuning_steps=2,
            post_reassignment_tuning_steps=2,
            reassignment_sweeps=1,
            tuning_learning_rate=0.01,
        )

    def test_default_profile_is_explicit_and_bounded(self):
        self.assertEqual(TASKS, ("condition", "composition", "language"))
        self.assertEqual(DEFAULT_PROFILE.block_rows, 4)
        self.assertEqual(DEFAULT_PROFILE.block_cols, 4)
        self.assertEqual(DEFAULT_PROFILE.codebook_count, 2)
        self.assertEqual(DEFAULT_PROFILE.entries_per_codebook, 4)
        self.assertLessEqual(DEFAULT_PROFILE.correction_fraction, 0.05)
        self.assertLessEqual(DEFAULT_PROFILE.max_abs_correction, 0.25)
        self.assertGreater(DEFAULT_PROFILE.initial_tuning_steps, 0)
        self.assertGreater(DEFAULT_PROFILE.post_reassignment_tuning_steps, 0)

    def test_invalid_profiles_are_rejected(self):
        with self.assertRaises(ValueError):
            CompressionProfile(correction_fraction=0.051)
        with self.assertRaises(ValueError):
            CompressionProfile(max_abs_correction=0.251)
        with self.assertRaises(ValueError):
            CompressionProfile(initial_tuning_steps=0)
        with self.assertRaises(ValueError):
            CompressionProfile(tuning_learning_rate=0.0)

    def test_compress_trained_core_reports_module_payload_separately(self):
        torch.manual_seed(9)
        core = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(width=16, slots=1, modules=2, hidden_mult=2)
        )
        compressed, info = compress_trained_core(
            core,
            self._small_profile(),
            device="cpu",
        )
        self.assertEqual(compressed.config, core.config)
        self.assertGreater(info["module_dense_float32_bytes"], 0)
        self.assertGreater(info["module_estimated_encoded_payload_bytes"], 0)
        self.assertAlmostEqual(
            info["module_payload_ratio"],
            info["module_estimated_encoded_payload_bytes"]
            / info["module_dense_float32_bytes"],
        )
        self.assertLess(info["module_payload_ratio"], 1.0)
        self.assertEqual(info["correction_nnz"], 0)
        self.assertEqual(info["max_observed_abs_correction"], 0.0)

    def test_summary_keeps_quality_capacity_and_runtime_axes_separate(self):
        records = [
            {
                "task": "condition",
                "high_precision_score": 1.0,
                "compressed_score": 0.98,
                "score_delta": -0.02,
                "runtime_ratio": 1.5,
                "compression": {
                    "module_payload_ratio": 0.7,
                    "max_observed_abs_correction": 0.08,
                },
            },
            {
                "task": "condition",
                "high_precision_score": 0.99,
                "compressed_score": 0.97,
                "score_delta": -0.02,
                "runtime_ratio": 1.7,
                "compression": {
                    "module_payload_ratio": 0.72,
                    "max_observed_abs_correction": 0.09,
                },
            },
        ]
        result = summarize(records)["tasks"]["condition"]
        self.assertEqual(result["runs"], 2)
        self.assertAlmostEqual(result["mean_high_precision_score"], 0.995)
        self.assertAlmostEqual(result["mean_compressed_score"], 0.975)
        self.assertAlmostEqual(result["mean_module_payload_ratio"], 0.71)
        self.assertAlmostEqual(result["mean_runtime_ratio"], 1.6)
        self.assertAlmostEqual(result["max_observed_abs_correction"], 0.09)

    def test_invalid_benchmark_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1,), task_names=("condition",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1, 2), task_names=("unknown",))
        with self.assertRaises(TypeError):
            run_benchmark(seeds=(1, 2), task_names=("condition",), profile=object())
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
