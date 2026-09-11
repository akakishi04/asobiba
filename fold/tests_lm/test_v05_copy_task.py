from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.copy_task import (
    CopyTaskConfig,
    ExactCopyModel,
    make_copy_splits,
    train_copy_task,
)


class V05CopyTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = CopyTaskConfig(
            vocab_size=8,
            sequence_length=4,
            width=16,
            modules=2,
            hidden_mult=2,
            route_index=0,
            internal_steps=1,
        )

    def test_splits_are_deterministic_unique_and_disjoint(self):
        train_a, val_a = make_copy_splits(
            self.config, train_examples=64, validation_examples=32, seed=17
        )
        train_b, val_b = make_copy_splits(
            self.config, train_examples=64, validation_examples=32, seed=17
        )
        torch.testing.assert_close(train_a, train_b, rtol=0.0, atol=0.0)
        torch.testing.assert_close(val_a, val_b, rtol=0.0, atol=0.0)
        train_rows = {tuple(row.tolist()) for row in train_a}
        val_rows = {tuple(row.tolist()) for row in val_a}
        self.assertEqual(len(train_rows), 64)
        self.assertEqual(len(val_rows), 32)
        self.assertFalse(train_rows & val_rows)

    def test_forward_shape_and_input_validation(self):
        model = ExactCopyModel(self.config)
        tokens = torch.tensor([[0, 1, 2, 3], [4, 5, 6, 7]], dtype=torch.int64)
        logits = model(tokens)
        self.assertEqual(tuple(logits.shape), (2, 4, 8))
        self.assertTrue(torch.isfinite(logits).all())
        with self.assertRaises(TypeError):
            model(tokens.float())
        with self.assertRaises(ValueError):
            model(tokens[:, :3])
        bad = tokens.clone()
        bad[0, 0] = self.config.vocab_size
        with self.assertRaises(ValueError):
            model(bad)

    def test_gradients_reach_embedding_core_and_decoder(self):
        torch.manual_seed(11)
        model = ExactCopyModel(self.config)
        tokens = torch.tensor([[0, 1, 2, 3], [4, 5, 6, 7]], dtype=torch.int64)
        logits = model(tokens)
        loss = F.cross_entropy(logits.flatten(0, 1), tokens.flatten())
        loss.backward()
        self.assertGreater(float(model.embedding.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[0].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.decoder.weight.grad.abs().sum()), 0.0)
        self.assertIsNone(model.core.module_set[1].up.weight.grad)

    def test_training_improves_held_out_copy_to_exact_accuracy(self):
        result = train_copy_task(
            config=self.config,
            seed=20260911,
            steps=120,
            learning_rate=0.01,
            batch_size=32,
            train_examples=256,
            validation_examples=128,
            device="cpu",
        )
        self.assertGreater(result["initial"]["nll"], result["final"]["nll"])
        self.assertLess(result["final"]["nll"], 0.02)
        self.assertGreaterEqual(result["final"]["token_accuracy"], 0.999)
        self.assertGreaterEqual(result["final"]["exact_accuracy"], 0.99)

    def test_invalid_config_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            CopyTaskConfig(vocab_size=1)
        with self.assertRaises(ValueError):
            CopyTaskConfig(modules=2, route_index=2)
        with self.assertRaises(ValueError):
            make_copy_splits(self.config, train_examples=5000, validation_examples=1)
        with self.assertRaises(ValueError):
            train_copy_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_copy_task(config=self.config, learning_rate=0.0)


if __name__ == "__main__":
    unittest.main()
