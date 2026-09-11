from __future__ import annotations

import unittest

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class V05LearnedCoreTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(7)
        self.config = LearnedCoreConfig(width=8, slots=3, modules=3, hidden_mult=2)
        self.core = HighPrecisionFixedRoutingCore(self.config)

    def test_initial_working_state_shape_dtype_and_validation(self):
        state = self.core.initial_working_state(4)
        self.assertEqual(tuple(state.shape), (4, 3, 8))
        self.assertEqual(state.dtype, next(self.core.parameters()).dtype)
        self.assertEqual(float(state.abs().max()), 0.0)
        with self.assertRaises(ValueError):
            self.core.initial_working_state(0)

    def test_forward_is_deterministic_and_preserves_shape(self):
        working = self.core.initial_working_state(2)
        context = torch.randn_like(working)
        first = self.core(working, context, route_index=1)
        second = self.core(working, context, route_index=1)
        self.assertEqual(tuple(first.shape), tuple(working.shape))
        torch.testing.assert_close(first, second, rtol=0.0, atol=0.0)

    def test_gradients_reach_shared_selected_module_and_gate(self):
        working = self.core.initial_working_state(2)
        context = torch.randn_like(working)
        output = self.core(working, context, route_index=1)
        loss = output.square().mean()
        loss.backward()

        self.assertIsNotNone(self.core.gate_logits.grad)
        self.assertGreater(float(self.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertTrue(any(p.grad is not None and float(p.grad.abs().sum()) > 0.0 for p in self.core.shared.parameters()))
        self.assertTrue(any(p.grad is not None and float(p.grad.abs().sum()) > 0.0 for p in self.core.module_set[1].parameters()))

    def test_unselected_modules_receive_no_gradient(self):
        working = self.core.initial_working_state(2)
        context = torch.randn_like(working)
        self.core(working, context, route_index=1).square().mean().backward()
        for index in (0, 2):
            self.assertTrue(all(parameter.grad is None for parameter in self.core.module_set[index].parameters()))

    def test_rejects_invalid_route_shape_dtype_and_nonfinite(self):
        working = self.core.initial_working_state(2)
        context = torch.randn_like(working)
        with self.assertRaises(ValueError):
            self.core(working, context, route_index=9)
        with self.assertRaises(ValueError):
            self.core(working[:, :2], context[:, :2], route_index=0)
        with self.assertRaises(ValueError):
            self.core(working, context[:, :2], route_index=0)
        with self.assertRaises(TypeError):
            self.core(working.long(), context.long(), route_index=0)
        bad = context.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            self.core(working, bad, route_index=0)


if __name__ == "__main__":
    unittest.main()
