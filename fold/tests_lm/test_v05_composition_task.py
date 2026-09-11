from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.composition_task import (
    ADD,
    SUB,
    CompositionModel,
    CompositionTaskConfig,
    authoritative_trajectory,
    make_composition_splits,
    train_composition_task,
)


class V05CompositionTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = CompositionTaskConfig(
            max_initial=4,
            max_operand=2,
            operation_steps=3,
            width=32,
            modules=2,
            hidden_mult=2,
            add_route=0,
            sub_route=1,
        )

    def test_authoritative_trajectory_composes_operations_exactly(self):
        initial = torch.tensor([3, 1], dtype=torch.int64)
        operations = torch.tensor(
            [[ADD, SUB, ADD], [SUB, SUB, ADD]], dtype=torch.int64
        )
        operands = torch.tensor(
            [[2, 1, 2], [1, 2, 1]], dtype=torch.int64
        )
        targets = authoritative_trajectory(initial, operations, operands)
        expected = torch.tensor(
            [[3, 5, 4, 6], [1, 0, -2, -1]], dtype=torch.int64
        )
        torch.testing.assert_close(targets, expected, rtol=0.0, atol=0.0)

    def test_splits_are_deterministic_disjoint_and_exhaustive(self):
        train_a, validation_a = make_composition_splits(self.config)
        train_b, validation_b = make_composition_splits(self.config)
        torch.testing.assert_close(train_a.initial_values, train_b.initial_values, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.operations, train_b.operations, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.operands, train_b.operands, rtol=0.0, atol=0.0)
        torch.testing.assert_close(validation_a.initial_values, validation_b.initial_values, rtol=0.0, atol=0.0)
        torch.testing.assert_close(validation_a.operations, validation_b.operations, rtol=0.0, atol=0.0)
        torch.testing.assert_close(validation_a.operands, validation_b.operands, rtol=0.0, atol=0.0)

        expected_total = (
            (self.config.max_initial + 1)
            * (2 ** self.config.operation_steps)
            * ((self.config.max_operand + 1) ** self.config.operation_steps)
        )
        self.assertEqual(train_a.size + validation_a.size, expected_total)

        def signatures(examples):
            return {
                (
                    int(examples.initial_values[index]),
                    *examples.operations[index].tolist(),
                    *examples.operands[index].tolist(),
                )
                for index in range(examples.size)
            }

        self.assertFalse(signatures(train_a) & signatures(validation_a))
        self.assertEqual(set(train_a.operations.flatten().tolist()), {ADD, SUB})
        self.assertEqual(set(validation_a.operations.flatten().tolist()), {ADD, SUB})
        self.assertEqual(
            set(validation_a.operands.flatten().tolist()),
            set(range(self.config.max_operand + 1)),
        )

    def test_forward_validation_and_gradients_reach_both_routes(self):
        torch.manual_seed(7)
        model = CompositionModel(self.config)
        initial = torch.tensor([0, 4], dtype=torch.int64)
        operations = torch.tensor(
            [[ADD, SUB, ADD], [SUB, ADD, SUB]], dtype=torch.int64
        )
        operands = torch.tensor(
            [[2, 1, 2], [1, 2, 1]], dtype=torch.int64
        )
        targets = authoritative_trajectory(initial, operations, operands)
        predicted = model(initial, operations, operands)
        self.assertEqual(tuple(predicted.shape), (2, 4))
        self.assertTrue(torch.isfinite(predicted).all())

        loss = F.mse_loss(
            predicted,
            targets.to(dtype=predicted.dtype) / float(self.config.state_scale),
        )
        loss.backward()
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[self.config.add_route].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[self.config.sub_route].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)

        with self.assertRaises(TypeError):
            model(initial.float(), operations, operands)
        with self.assertRaises(ValueError):
            model(initial, operations[:, :2], operands[:, :2])
        bad_ops = operations.clone()
        bad_ops[0, 0] = 9
        with self.assertRaises(ValueError):
            model(initial, bad_ops, operands)

    def test_training_improves_held_out_multi_step_exact_trajectory(self):
        result = train_composition_task(
            config=self.config,
            seed=20260911,
            steps=300,
            learning_rate=0.005,
            batch_size=64,
            device="cpu",
        )
        self.assertGreater(result["initial"]["mse"], result["final"]["mse"])
        self.assertLess(result["final"]["mse"], 1e-4)
        self.assertLess(result["final"]["max_abs_error"], 0.5)
        self.assertGreaterEqual(result["final"]["point_accuracy"], 0.999)
        self.assertGreaterEqual(result["final"]["trajectory_exact_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["final_accuracy"], 0.99)

    def test_invalid_config_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            CompositionTaskConfig(width=2)
        with self.assertRaises(ValueError):
            CompositionTaskConfig(add_route=0, sub_route=0)
        with self.assertRaises(ValueError):
            CompositionTaskConfig(modules=2, sub_route=2)
        with self.assertRaises(ValueError):
            train_composition_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_composition_task(config=self.config, learning_rate=0.0)
        with self.assertRaises(ValueError):
            train_composition_task(config=self.config, batch_size=0)


if __name__ == "__main__":
    unittest.main()
