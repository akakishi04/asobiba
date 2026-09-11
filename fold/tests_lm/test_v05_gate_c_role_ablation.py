from __future__ import annotations

import unittest

import torch

from fold_lm.v05.condition_task import ConditionHoldUpdateModel, ConditionTaskConfig
from fold_lm.v05_benchmarks.gate_c_role_ablation import (
    VARIANTS,
    _materialized_variant,
    run_benchmark,
    summarize,
)
from fold_lm.v05_benchmarks.gate_c_task_quality import compress_trained_core


class V05GateCRoleAblationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(19)
        self.model = ConditionHoldUpdateModel(ConditionTaskConfig())
        self.compressed_core, _ = compress_trained_core(self.model.core, device="cpu")

    def test_variants_are_explicit(self):
        self.assertEqual(
            VARIANTS,
            ("high_precision", "up_only", "down_only", "both_materialized", "both_direct"),
        )

    def test_up_only_replaces_only_up_weights(self):
        variant = _materialized_variant(
            self.model,
            self.compressed_core,
            use_up=True,
            use_down=False,
        )
        for index, (before, after) in enumerate(zip(self.model.core.module_set, variant.core.module_set)):
            expected_up = self.compressed_core.up_bank.materialized_weight(index)
            torch.testing.assert_close(after.up.weight, expected_up)
            torch.testing.assert_close(after.down.weight, before.down.weight)

    def test_down_only_replaces_only_down_weights(self):
        variant = _materialized_variant(
            self.model,
            self.compressed_core,
            use_up=False,
            use_down=True,
        )
        for index, (before, after) in enumerate(zip(self.model.core.module_set, variant.core.module_set)):
            expected_down = self.compressed_core.down_bank.materialized_weight(index)
            torch.testing.assert_close(after.down.weight, expected_down)
            torch.testing.assert_close(after.up.weight, before.up.weight)

    def test_summary_keeps_roles_and_direct_parity_separate(self):
        records = [
            {
                "task": "composition",
                "scores": {
                    "high_precision": 1.0,
                    "up_only": 0.8,
                    "down_only": 0.6,
                    "both_materialized": 0.4,
                    "both_direct": 0.4,
                },
                "score_deltas": {
                    "high_precision": 0.0,
                    "up_only": -0.2,
                    "down_only": -0.4,
                    "both_materialized": -0.6,
                    "both_direct": -0.6,
                },
                "up_final_reconstruction_mse": 0.01,
                "down_final_reconstruction_mse": 0.02,
                "module_payload_ratio": 0.5,
                "max_observed_abs_correction": 0.1,
                "materialized_direct_score_gap": 0.0,
            },
            {
                "task": "composition",
                "scores": {
                    "high_precision": 1.0,
                    "up_only": 0.9,
                    "down_only": 0.7,
                    "both_materialized": 0.5,
                    "both_direct": 0.5,
                },
                "score_deltas": {
                    "high_precision": 0.0,
                    "up_only": -0.1,
                    "down_only": -0.3,
                    "both_materialized": -0.5,
                    "both_direct": -0.5,
                },
                "up_final_reconstruction_mse": 0.03,
                "down_final_reconstruction_mse": 0.04,
                "module_payload_ratio": 0.6,
                "max_observed_abs_correction": 0.09,
                "materialized_direct_score_gap": 0.0,
            },
        ]
        result = summarize(records)["tasks"]["composition"]
        self.assertAlmostEqual(result["variants"]["up_only"]["mean_score"], 0.85)
        self.assertAlmostEqual(result["variants"]["down_only"]["mean_score"], 0.65)
        self.assertAlmostEqual(result["mean_up_final_reconstruction_mse"], 0.02)
        self.assertAlmostEqual(result["mean_down_final_reconstruction_mse"], 0.03)
        self.assertEqual(result["max_abs_materialized_direct_score_gap"], 0.0)

    def test_invalid_scope_is_rejected_before_training(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=())
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1, 1))
        with self.assertRaises(ValueError):
            run_benchmark(task_names=())
        with self.assertRaises(ValueError):
            run_benchmark(task_names=("not-a-task",))


if __name__ == "__main__":
    unittest.main()
