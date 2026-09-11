from __future__ import annotations

import unittest

import numpy as np
import torch
from torch import nn

from fold_lm.v05.compressed_runtime import CompressedModuleInitializations
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_task_aware_recovery import (
    TaskTunableCompressedCore,
    _freeze_except_compressed,
    _initializations_from_core,
    summarize,
)
from fold_lm.v05_benchmarks.gate_c_task_quality import CompressionProfile


class _Holder(nn.Module):
    def __init__(self, core: nn.Module) -> None:
        super().__init__()
        self.core = core
        self.extra = nn.Linear(8, 8)


class V05GateCTaskAwareRecoveryTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(31)
        self.source = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(width=8, slots=1, modules=2, hidden_mult=2)
        )
        self.profile = CompressionProfile(
            block_rows=2,
            block_cols=2,
            codebook_count=1,
            entries_per_codebook=2,
            correction_fraction=0.0,
            max_abs_correction=0.0,
            initial_tuning_steps=2,
            post_reassignment_tuning_steps=2,
            reassignment_sweeps=1,
            tuning_learning_rate=0.01,
        )
        self.initializations, self.diagnostics = _initializations_from_core(
            self.source,
            self.profile,
            device=torch.device("cpu"),
        )

    def test_only_compressed_continuous_values_remain_trainable(self):
        core = TaskTunableCompressedCore(self.source, self.initializations)
        holder = _Holder(core)
        _freeze_except_compressed(holder, core)
        trainable = {name for name, parameter in holder.named_parameters() if parameter.requires_grad}
        self.assertTrue(trainable)
        self.assertTrue(all(name.startswith("core.up.") or name.startswith("core.down.") for name in trainable))
        self.assertFalse(holder.extra.weight.requires_grad)
        self.assertFalse(holder.extra.bias.requires_grad)
        self.assertTrue(all(not parameter.requires_grad for parameter in core.shared.parameters()))
        self.assertTrue(all(not parameter.requires_grad for parameter in core.norms.parameters()))

    def test_forward_and_gradients_reach_compressed_continuous_values(self):
        core = TaskTunableCompressedCore(self.source, self.initializations)
        working = torch.randn(4, 1, 8)
        context = torch.randn(4, 1, 8)
        output = core(working, context, route_index=0)
        self.assertEqual(tuple(output.shape), (4, 1, 8))
        self.assertTrue(torch.isfinite(output).all())
        output.square().mean().backward()
        self.assertIsNotNone(core.up.base.grad)
        self.assertIsNotNone(core.down.base.grad)
        self.assertGreater(float(core.up.base.grad.abs().sum()), 0.0)
        self.assertGreater(float(core.down.base.grad.abs().sum()), 0.0)
        self.assertIsNone(core.up.codes.grad)
        self.assertIsNone(core.down.codes.grad)

    def test_export_preserves_fixed_structure_and_accounting(self):
        core = TaskTunableCompressedCore(self.source, self.initializations)
        exported = core.export_initializations()
        self.assertIsInstance(exported, CompressedModuleInitializations)
        self.assertEqual(exported.up.accounting, self.initializations.up.accounting)
        self.assertEqual(exported.down.accounting, self.initializations.down.accounting)
        for before, after in zip(
            self.initializations.up.encoded_weights,
            exported.up.encoded_weights,
        ):
            np.testing.assert_array_equal(before.codes, after.codes)
            np.testing.assert_array_equal(before.correction_indices, after.correction_indices)
        for before, after in zip(
            self.initializations.down.encoded_weights,
            exported.down.encoded_weights,
        ):
            np.testing.assert_array_equal(before.codes, after.codes)
            np.testing.assert_array_equal(before.correction_indices, after.correction_indices)

    def test_summary_separates_pre_post_capacity_and_structure_invariants(self):
        records = [
            {
                "high_precision_score": 1.0,
                "pre_task_tuning_score": 0.60,
                "post_task_tuning_score": 0.95,
                "recovered_score": 0.35,
                "post_delta": -0.05,
                "module_payload_ratio": 0.68,
                "max_observed_abs_correction": 0.14,
                "payload_unchanged": True,
                "codes_unchanged": True,
                "correction_coordinates_unchanged": True,
            },
            {
                "high_precision_score": 1.0,
                "pre_task_tuning_score": 0.70,
                "post_task_tuning_score": 0.90,
                "recovered_score": 0.20,
                "post_delta": -0.10,
                "module_payload_ratio": 0.68,
                "max_observed_abs_correction": 0.15,
                "payload_unchanged": True,
                "codes_unchanged": True,
                "correction_coordinates_unchanged": True,
            },
        ]
        result = summarize(records)
        self.assertEqual(result["runs"], 2)
        self.assertAlmostEqual(result["mean_pre_task_tuning_score"], 0.65)
        self.assertAlmostEqual(result["mean_post_task_tuning_score"], 0.925)
        self.assertAlmostEqual(result["mean_module_payload_ratio"], 0.68)
        self.assertTrue(result["all_payload_unchanged"])
        self.assertTrue(result["all_codes_unchanged"])
        self.assertTrue(result["all_correction_coordinates_unchanged"])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            TaskTunableCompressedCore(object(), self.initializations)
        with self.assertRaises(TypeError):
            TaskTunableCompressedCore(self.source, object())
        core = TaskTunableCompressedCore(self.source, self.initializations)
        working = torch.zeros(2, 1, 8)
        context = torch.zeros_like(working)
        with self.assertRaises(ValueError):
            core(working, context, route_index=2)
        with self.assertRaises(ValueError):
            core(torch.zeros(2, 2, 8), torch.zeros(2, 2, 8), route_index=0)
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
