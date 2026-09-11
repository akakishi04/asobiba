from __future__ import annotations

import unittest

import torch

from fold_lm.v05.baselines import (
    ActiveComputeDenseCore,
    BaselineCoreStats,
    ParameterMatchedSharedCore,
    reference_core_stats,
    trainable_parameter_count,
)
from fold_lm.v05.modules import LearnedCoreConfig


class V05BaselineCoreTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = LearnedCoreConfig(width=16, slots=3, modules=2, hidden_mult=2)

    def test_dense_baseline_matches_reference_active_linear_macs(self):
        reference = reference_core_stats(self.config)
        dense = ActiveComputeDenseCore(self.config)
        stats = dense.stats()
        self.assertEqual(
            stats.active_linear_macs_per_slot_step,
            reference.active_linear_macs_per_slot_step,
        )
        self.assertEqual(stats.hidden_size, 2 * reference.hidden_size)
        self.assertGreater(stats.trainable_parameters, 0)

    def test_shared_baseline_closely_matches_reference_parameter_count(self):
        reference = reference_core_stats(self.config)
        shared = ParameterMatchedSharedCore(self.config)
        stats = shared.stats()
        gap = abs(stats.trainable_parameters - reference.trainable_parameters)
        # The hidden dimension is integer-valued, so exact equality is not
        # guaranteed.  The chosen deterministic search must get within one
        # width of the V5-B reference parameter count.
        self.assertLessEqual(gap, self.config.width)
        self.assertEqual(stats.trainable_parameters, trainable_parameter_count(shared))
        self.assertGreater(stats.active_linear_macs_per_slot_step, 0)

    def test_baselines_preserve_common_shape_and_finite_contract(self):
        working = torch.randn(4, 3, 16)
        context = torch.randn(4, 3, 16)
        for core in (
            ActiveComputeDenseCore(self.config),
            ParameterMatchedSharedCore(self.config),
        ):
            output = core(working, context, route_index=1)
            self.assertEqual(tuple(output.shape), tuple(working.shape))
            self.assertTrue(torch.isfinite(output).all())
            initial = core.initial_working_state(4)
            self.assertEqual(tuple(initial.shape), (4, 3, 16))
            self.assertEqual(initial.dtype, next(core.parameters()).dtype)

    def test_dense_unselected_route_has_no_gradient(self):
        torch.manual_seed(9)
        core = ActiveComputeDenseCore(self.config)
        working = torch.randn(2, 3, 16)
        context = torch.randn(2, 3, 16)
        core(working, context, route_index=0).square().mean().backward()
        self.assertIsNotNone(core.route_set[0].up.weight.grad)
        self.assertGreater(float(core.route_set[0].up.weight.grad.abs().sum()), 0.0)
        self.assertIsNone(core.route_set[1].up.weight.grad)
        self.assertGreater(float(core.gate_logits.grad.abs().sum()), 0.0)

    def test_shared_baseline_uses_one_transform_and_route_embedding(self):
        torch.manual_seed(10)
        core = ParameterMatchedSharedCore(self.config)
        working = torch.randn(2, 3, 16)
        context = torch.randn(2, 3, 16)
        output0 = core(working, context, route_index=0)
        output1 = core(working, context, route_index=1)
        self.assertFalse(torch.equal(output0, output1))
        output0.square().mean().backward()
        self.assertGreater(float(core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(core.route_embedding.weight.grad[0].abs().sum()), 0.0)
        self.assertEqual(float(core.route_embedding.weight.grad[1].abs().sum()), 0.0)

    def test_invalid_baseline_inputs_and_stats_are_rejected(self):
        with self.assertRaises(TypeError):
            ActiveComputeDenseCore(object())
        with self.assertRaises(ValueError):
            ParameterMatchedSharedCore(self.config, hidden_size=0)
        with self.assertRaises(ValueError):
            BaselineCoreStats(0, 1, 1)

        core = ActiveComputeDenseCore(self.config)
        working = torch.zeros(1, 3, 16)
        context = torch.zeros_like(working)
        with self.assertRaises(ValueError):
            core(working, context, route_index=2)
        with self.assertRaises(TypeError):
            core(working.to(torch.int64), context, route_index=0)
        bad = context.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            core(working, bad, route_index=0)


if __name__ == "__main__":
    unittest.main()
