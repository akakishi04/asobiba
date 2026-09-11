from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.data import BOS, EOS, PAD
from fold_lm.v05.language_task import (
    LANG_EN,
    LANG_JA,
    TASK_INSTRUCTION,
    TASK_NEXT,
    LanguageTaskConfig,
    ShortByteLanguageModel,
    encode_fixed_prompt,
    make_language_splits,
    train_short_language_task,
)


class V05LanguageTaskTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.config = LanguageTaskConfig(
            symbol_count=8,
            max_tokens=20,
            width=32,
            modules=2,
            hidden_mult=2,
            next_route=0,
            instruction_route=1,
            internal_steps=2,
        )

    def test_fixed_utf8_byte_encoding_uses_existing_special_tokens(self):
        text = "答え:3"
        encoded = encode_fixed_prompt(text, max_tokens=self.config.max_tokens)
        raw = list(text.encode("utf-8"))
        self.assertEqual(int(encoded[0]), BOS)
        self.assertEqual(encoded[1 : 1 + len(raw)].tolist(), raw)
        self.assertEqual(int(encoded[1 + len(raw)]), EOS)
        self.assertTrue(torch.all(encoded[2 + len(raw) :] == PAD))
        with self.assertRaises(ValueError):
            encode_fixed_prompt(text, max_tokens=4)

    def test_splits_are_deterministic_disjoint_bilingual_and_cover_both_tasks(self):
        train_a, validation_a = make_language_splits(self.config)
        train_b, validation_b = make_language_splits(self.config)
        torch.testing.assert_close(train_a.tokens, train_b.tokens, rtol=0.0, atol=0.0)
        torch.testing.assert_close(validation_a.tokens, validation_b.tokens, rtol=0.0, atol=0.0)
        self.assertEqual(train_a.prompts, train_b.prompts)
        self.assertEqual(validation_a.prompts, validation_b.prompts)
        self.assertFalse(set(train_a.prompts) & set(validation_a.prompts))
        for examples in (train_a, validation_a):
            self.assertEqual(set(examples.languages.tolist()), {LANG_EN, LANG_JA})
            self.assertEqual(set(examples.tasks.tolist()), {TASK_NEXT, TASK_INSTRUCTION})
        self.assertTrue(any(any(byte >= 0x80 for byte in prompt.encode("utf-8")) for prompt in validation_a.prompts))

    def test_forward_validation_and_gradients_reach_both_routes(self):
        torch.manual_seed(7)
        train, _ = make_language_splits(self.config)
        next_index = int((train.tasks == TASK_NEXT).nonzero(as_tuple=False)[0])
        instruction_index = int((train.tasks == TASK_INSTRUCTION).nonzero(as_tuple=False)[0])
        indices = torch.tensor([next_index, instruction_index], dtype=torch.int64)
        tokens = train.tokens[indices]
        tasks = train.tasks[indices]
        targets = train.targets[indices]

        model = ShortByteLanguageModel(self.config)
        logits = model(tokens, tasks)
        self.assertEqual(tuple(logits.shape), (2, 256))
        self.assertTrue(torch.isfinite(logits).all())
        loss = F.cross_entropy(logits, targets)
        loss.backward()
        self.assertGreater(float(model.byte_embedding.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.shared.up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[self.config.next_route].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.module_set[self.config.instruction_route].up.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.core.gate_logits.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.decoder.weight.grad.abs().sum()), 0.0)

        with self.assertRaises(TypeError):
            model(tokens.float(), tasks)
        with self.assertRaises(ValueError):
            model(tokens[:, :-1], tasks)
        bad_tasks = tasks.clone()
        bad_tasks[0] = 9
        with self.assertRaises(ValueError):
            model(tokens, bad_tasks)

    def test_training_improves_held_out_bilingual_next_and_instruction_accuracy(self):
        result = train_short_language_task(
            config=self.config,
            seed=20260911,
            steps=600,
            learning_rate=0.01,
            batch_size=24,
            device="cpu",
        )
        self.assertGreater(result["initial"]["nll"], result["final"]["nll"])
        self.assertLess(result["final"]["nll"], 0.10)
        self.assertGreaterEqual(result["final"]["accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["english_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["japanese_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["next_accuracy"], 0.99)
        self.assertGreaterEqual(result["final"]["instruction_accuracy"], 0.99)

    def test_invalid_config_and_training_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            LanguageTaskConfig(symbol_count=11)
        with self.assertRaises(ValueError):
            LanguageTaskConfig(next_route=0, instruction_route=0)
        with self.assertRaises(ValueError):
            LanguageTaskConfig(modules=2, instruction_route=2)
        with self.assertRaises(ValueError):
            train_short_language_task(config=self.config, steps=0)
        with self.assertRaises(ValueError):
            train_short_language_task(config=self.config, learning_rate=0.0)
        with self.assertRaises(ValueError):
            train_short_language_task(config=self.config, batch_size=0)


if __name__ == "__main__":
    unittest.main()
