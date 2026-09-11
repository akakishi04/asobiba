from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.arithmetic_task import (
    AdditionModel,
    ArithmeticTaskConfig,
    authoritative_sum,
    make_arithmetic_splits,
    train_addition_task,
)


class V05ArithmeticTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = ArithmeticTaskConfig(
            max_operand=7,
            width=24,
            modules=2,
            hidden_mult=2,
            route_index=0,
            internal_steps=2,
        )

    def test_authoritative_sum_is_exact(self):
        left = torch.tensor([0, 1, 3, 7], dtype=torch.int64)
        right = torch.tensor([0, 6, 4, 7], dtype=torch.int64)
        expected = torch.tensor([0, 7, 7, 14], dtype=torch.int64)
        torch.testing.assert_close(authoritative_sum(left, right), expected, rtol=0.0, atol=0.0)

    def test_splits_are_deterministic_disjoint_and_cover_operand_values(self):
        train_a, val_a = make_arithmetic_splits(self.config)
        train_b, val_b = make_arithmetic_splits(self.config)
        torch.testing.assert_close(train_a.left, train_b.left, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.right, train_b.right, rtol=0.0, atol=0.0)
        torch.testing.assert_close(val_a.left, val_b.left, rtol=0.0, atol=0.0)
        torch.testing.assert_close(val_a.right, val_b.right, rtol=0.0, atol=0.0)

        train_pairs = set(zip(train_a.left.tolist(), train_a.right.tolist(), strict=True))
        val_pairs = set(zip(val_a.left.tolist(), val_a.right.tolist(), strict=True))
        self.assertFalse(train_pairs & val_pairs)
        self.assertEqual(len(train_pairs) + len(val_pairs), (self.config.max_operand + 1) ** 2)
        expected_values = set(range(self.config.max_operand + 1))
        self.assertEqual(set(train_a.left.tolist()), expected_values)
        self.assertEqual(set(train_a.right.tolist()), expected_values)
        self.assertEqual(set(val_a.left.tolist()), expected_values)
        self.assertEqual(set(val_a.right.tolist()), expected_values)

    def test_forward_validation_and_gradients_reach_core_and_decoder(self):
        torch.manual_seed(11)
        model = AdditionModel(self.config)
        left = torch.tensor([0, 2, 5, 7], dtype=torch.int64)
        right = torch.tensor([7, 4, 1, 3], dtype=torch.int64)
        predicted = model(left, right)
        self.assertEqual(tuple(predicted.shape), (4,))
        self.assertTrue(torch.isfinite(predicted).all())

        targets = authoritative_sum(left, right).float() / float(2 * self.config.max_operand)
        loss = F.mse_loss(predicted, targets)
        loss.backward()
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[0].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.decoder.weight.grad.abs().sum()), 0.0)
        self.assertIsNone(model.core.module_set[1].up.weight.grad)

        with self.assertRaises(TypeError):
            model(left.float(), right)
        with self.assertRaises(ValueError):
            model(left[:-1], right)
        bad = left.clone()
        bad[0] = self.config.max_operand + 1
        with self.assertRaises(ValueError):
            model(bad, right)

    def test_training_improves_held_out_exact_addition(self):
        result = train_addition_task(
            config=self.config,
            seed=20260911,
            steps=300,
            learning_rate=0.005,
            batch_size=32,
            device="cpu",
        )
        self.assertGreater(result["initial"]["mse"], result["final"]["mse"])
        self.assertLess(result["final"]["mae"], 0.20)
        self.assertLess(result["final"]["max_abs_error"], 0.50)
        self.assertEqual(result["final"]["exact_accuracy"], 1.0)

    def test_invalid_config_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            ArithmeticTaskConfig(max_operand=0)
        with self.assertRaises(ValueError):
            ArithmeticTaskConfig(width=2)
        with self.assertRaises(ValueError):
            ArithmeticTaskConfig(modules=2, route_index=2)
        with self.assertRaises(ValueError):
            train_addition_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_addition_task(config=self.config, learning_rate=0.0)
        with self.assertRaises(ValueError):
            train_addition_task(config=self.config, batch_size=0)


if __name__ == "__main__":
    unittest.main()
