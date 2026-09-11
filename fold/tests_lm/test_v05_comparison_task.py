from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.comparison_task import (
    EQUAL,
    GREATER,
    LESS,
    ComparisonModel,
    ComparisonTaskConfig,
    authoritative_comparison,
    make_comparison_splits,
    train_comparison_task,
)


class V05ComparisonTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = ComparisonTaskConfig(
            value_vocab_size=16,
            width=24,
            modules=2,
            hidden_mult=2,
            route_index=0,
            internal_steps=1,
        )

    def test_authoritative_targets_cover_less_equal_and_greater(self):
        left = torch.tensor([1, 4, 7], dtype=torch.int64)
        right = torch.tensor([3, 4, 2], dtype=torch.int64)
        targets = authoritative_comparison(left, right)
        torch.testing.assert_close(
            targets,
            torch.tensor([LESS, EQUAL, GREATER], dtype=torch.int64),
            rtol=0.0,
            atol=0.0,
        )

    def test_splits_are_deterministic_disjoint_and_class_stratified(self):
        train_a, val_a = make_comparison_splits(self.config, seed=17)
        train_b, val_b = make_comparison_splits(self.config, seed=17)
        for first, second in (
            (train_a.left, train_b.left),
            (train_a.right, train_b.right),
            (train_a.targets, train_b.targets),
            (val_a.left, val_b.left),
            (val_a.right, val_b.right),
            (val_a.targets, val_b.targets),
        ):
            torch.testing.assert_close(first, second, rtol=0.0, atol=0.0)

        train_pairs = set(zip(train_a.left.tolist(), train_a.right.tolist()))
        validation_pairs = set(zip(val_a.left.tolist(), val_a.right.tolist()))
        self.assertFalse(train_pairs & validation_pairs)
        self.assertEqual(len(train_pairs) + len(validation_pairs), 16 * 16)
        self.assertEqual(set(train_a.targets.tolist()), {LESS, EQUAL, GREATER})
        self.assertEqual(set(val_a.targets.tolist()), {LESS, EQUAL, GREATER})

    def test_forward_validation_and_gradients_reach_core_and_decoder(self):
        torch.manual_seed(11)
        model = ComparisonModel(self.config)
        left = torch.tensor([1, 4, 7, 10], dtype=torch.int64)
        right = torch.tensor([3, 4, 2, 12], dtype=torch.int64)
        targets = authoritative_comparison(left, right)
        logits = model(left, right)
        self.assertEqual(tuple(logits.shape), (4, 3))
        self.assertTrue(torch.isfinite(logits).all())
        loss = F.cross_entropy(logits, targets)
        loss.backward()
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[0].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.decoder.weight.grad.abs().sum()), 0.0)
        self.assertIsNone(model.core.module_set[1].up.weight.grad)

        with self.assertRaises(TypeError):
            model(left.float(), right)
        with self.assertRaises(ValueError):
            model(left[:2], right)
        bad = left.clone()
        bad[0] = self.config.value_vocab_size
        with self.assertRaises(ValueError):
            model(bad, right)

    def test_training_improves_held_out_comparison_all_classes(self):
        result = train_comparison_task(
            config=self.config,
            seed=20260911,
            steps=300,
            learning_rate=0.01,
            batch_size=64,
            device="cpu",
        )
        self.assertGreater(result["initial"]["nll"], result["final"]["nll"])
        self.assertLess(result["final"]["nll"], 0.02)
        self.assertGreaterEqual(result["final"]["accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["less_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["equal_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["greater_accuracy"], 0.99)

    def test_invalid_config_split_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            ComparisonTaskConfig(value_vocab_size=2)
        with self.assertRaises(ValueError):
            ComparisonTaskConfig(width=1)
        with self.assertRaises(ValueError):
            ComparisonTaskConfig(modules=2, route_index=2)
        with self.assertRaises(ValueError):
            make_comparison_splits(self.config, train_equal=16)
        with self.assertRaises(ValueError):
            train_comparison_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_comparison_task(config=self.config, learning_rate=0.0)


if __name__ == "__main__":
    unittest.main()
