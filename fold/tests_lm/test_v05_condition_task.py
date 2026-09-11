from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.condition_task import (
    HOLD,
    UPDATE,
    ConditionHoldUpdateModel,
    ConditionTaskConfig,
    authoritative_targets,
    make_condition_splits,
    train_condition_task,
)


class V05ConditionTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = ConditionTaskConfig(
            value_vocab_size=8,
            operation_steps=3,
            width=16,
            modules=2,
            hidden_mult=2,
            hold_route=0,
            update_route=1,
        )

    @staticmethod
    def _signatures(examples):
        result = set()
        for index in range(examples.size):
            result.add(
                (
                    int(examples.initial_values[index]),
                    *[int(value) for value in examples.operations[index]],
                    *[int(value) for value in examples.candidates[index]],
                )
            )
        return result

    def test_authoritative_targets_hold_and_update_exactly(self):
        initial = torch.tensor([2, 1], dtype=torch.int64)
        operations = torch.tensor(
            [[HOLD, UPDATE, HOLD], [UPDATE, HOLD, UPDATE]], dtype=torch.int64
        )
        candidates = torch.tensor([[7, 5, 6], [3, 4, 2]], dtype=torch.int64)
        expected = torch.tensor([[2, 2, 5, 5], [1, 3, 3, 2]], dtype=torch.int64)
        actual = authoritative_targets(initial, operations, candidates)
        torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)

    def test_splits_are_deterministic_unique_disjoint_and_contain_both_operations(self):
        train_a, val_a = make_condition_splits(
            self.config, train_examples=64, validation_examples=32, seed=23
        )
        train_b, val_b = make_condition_splits(
            self.config, train_examples=64, validation_examples=32, seed=23
        )
        torch.testing.assert_close(train_a.initial_values, train_b.initial_values, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.operations, train_b.operations, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.candidates, train_b.candidates, rtol=0.0, atol=0.0)
        torch.testing.assert_close(train_a.targets, train_b.targets, rtol=0.0, atol=0.0)
        self.assertEqual(len(self._signatures(train_a)), 64)
        self.assertEqual(len(self._signatures(val_a)), 32)
        self.assertFalse(self._signatures(train_a) & self._signatures(val_a))
        self.assertTrue(torch.any(train_a.operations == HOLD))
        self.assertTrue(torch.any(train_a.operations == UPDATE))

    def test_forward_shape_validation_and_gradients_reach_both_teacher_routes(self):
        torch.manual_seed(19)
        model = ConditionHoldUpdateModel(self.config)
        initial = torch.tensor([0, 1, 2, 3], dtype=torch.int64)
        operations = torch.tensor(
            [
                [HOLD, UPDATE, HOLD],
                [UPDATE, HOLD, UPDATE],
                [HOLD, HOLD, UPDATE],
                [UPDATE, UPDATE, HOLD],
            ],
            dtype=torch.int64,
        )
        candidates = torch.tensor(
            [[4, 5, 6], [7, 0, 1], [2, 3, 4], [5, 6, 7]], dtype=torch.int64
        )
        targets = authoritative_targets(initial, operations, candidates)
        logits = model(initial, operations, candidates)
        self.assertEqual(tuple(logits.shape), (4, 4, 8))
        self.assertTrue(torch.isfinite(logits).all())

        loss = F.cross_entropy(logits.flatten(0, 1), targets.flatten())
        loss.backward()
        self.assertGreater(float(model.state_embedding.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.event_embedding.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[0].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[1].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.decoder.weight.grad.abs().sum()), 0.0)

        with self.assertRaises(TypeError):
            model(initial.float(), operations, candidates)
        with self.assertRaises(ValueError):
            model(initial, operations[:, :2], candidates[:, :2])
        bad_operations = operations.clone()
        bad_operations[0, 0] = 2
        with self.assertRaises(ValueError):
            model(initial, bad_operations, candidates)
        bad_candidates = candidates.clone()
        bad_candidates[0, 0] = self.config.value_vocab_size
        with self.assertRaises(ValueError):
            model(initial, operations, bad_candidates)

    def test_training_improves_held_out_hold_update_trajectory(self):
        result = train_condition_task(
            config=self.config,
            seed=20260911,
            steps=260,
            learning_rate=0.01,
            batch_size=32,
            train_examples=256,
            validation_examples=128,
            device="cpu",
        )
        self.assertGreater(result["initial"]["nll"], result["final"]["nll"])
        self.assertLess(result["final"]["nll"], 0.15)
        self.assertGreaterEqual(result["final"]["trajectory_accuracy"], 0.97)
        self.assertGreaterEqual(result["final"]["trajectory_exact_accuracy"], 0.90)
        self.assertGreaterEqual(result["final"]["final_accuracy"], 0.97)

    def test_invalid_config_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            ConditionTaskConfig(value_vocab_size=1)
        with self.assertRaises(ValueError):
            ConditionTaskConfig(modules=2, hold_route=0, update_route=0)
        with self.assertRaises(ValueError):
            ConditionTaskConfig(modules=2, hold_route=0, update_route=2)
        with self.assertRaises(ValueError):
            train_condition_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_condition_task(config=self.config, learning_rate=0.0)


if __name__ == "__main__":
    unittest.main()
