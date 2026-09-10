"""Offline tests for the deterministic long-memory benchmark harness."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
import tempfile
import unittest

import torch

from fold_lm.long_memory_benchmark import (
    FACT_RE,
    NAMES,
    evaluate_owner_candidates,
    generate_dataset,
    load_validation,
    make_counterfactuals,
)
from fold_lm.model import FoldLanguageModel, ModelConfig
from fold_lm.runner import TrainConfig


class LongMemoryBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_generation_is_deterministic_and_cross_split_clean(self):
        a = self.root / "a"
        b = self.root / "b"
        meta_a = generate_dataset(a, train_rows=200, validation_rows=40)
        meta_b = generate_dataset(b, train_rows=200, validation_rows=40)

        self.assertEqual((a / "train.jsonl").read_bytes(), (b / "train.jsonl").read_bytes())
        self.assertEqual((a / "validation.jsonl").read_bytes(), (b / "validation.jsonl").read_bytes())
        self.assertEqual(meta_a, meta_b)
        self.assertEqual(meta_a["train_rows"], 200)
        self.assertEqual(meta_a["validation_rows"], 40)
        self.assertEqual(meta_a["cross_split_overlap"], 0)
        self.assertGreater(meta_a["fact_to_answer_distance_bytes"]["min"], 64)
        self.assertLessEqual(meta_a["example_bytes"]["max"], 250)

        train = {
            json.loads(line)["prompt"] + json.loads(line)["target"]
            for line in (a / "train.jsonl").read_text(encoding="utf-8").splitlines()
        }
        validation = {
            json.loads(line)["prompt"] + json.loads(line)["target"]
            for line in (a / "validation.jsonl").read_text(encoding="utf-8").splitlines()
        }
        self.assertFalse(train & validation)
        self.assertEqual(len(validation), 40)

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "data"
        generate_dataset(output, train_rows=20, validation_rows=5)
        original = (output / "train.jsonl").read_bytes()
        with self.assertRaises(FileExistsError):
            generate_dataset(output, train_rows=21, validation_rows=5)
        self.assertEqual((output / "train.jsonl").read_bytes(), original)

    def test_counterfactual_keeps_length_and_local_suffix(self):
        output = self.root / "data"
        generate_dataset(output, train_rows=100, validation_rows=60)
        examples = load_validation(output / "validation.jsonl")
        changed, counts = make_counterfactuals(examples, seed=20260910, local_window=64)

        self.assertTrue(changed)
        self.assertEqual(sum(counts.values()), len(changed))
        for example in changed:
            self.assertIsNotNone(example.original_owner)
            match = FACT_RE.match(example.prompt)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(2), example.expected)
            old_prompt = (
                example.prompt[:match.start(2)]
                + example.original_owner
                + example.prompt[match.end(2):]
            )
            self.assertEqual(len(old_prompt.encode("utf-8")), len(example.prompt.encode("utf-8")))
            self.assertEqual(old_prompt.encode("utf-8")[-64:], example.prompt.encode("utf-8")[-64:])
            self.assertNotEqual(example.original_owner, example.expected)
            self.assertIn(example.expected, NAMES)

    def test_validation_parser_rejects_fact_target_mismatch(self):
        path = self.root / "bad.jsonl"
        path.write_text(
            json.dumps({
                "prompt": "Important fact: the red key belongs to Alice. Question: who owns the red key? Answer: ",
                "target": "Bob.",
            }) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "mismatch"):
            load_validation(path)

    def test_owner_evaluator_runs_on_cpu(self):
        output = self.root / "data"
        generate_dataset(output, train_rows=50, validation_rows=4)
        examples = load_validation(output / "validation.jsonl")[:2]

        config = ModelConfig(
            width=16,
            layers=1,
            heads=2,
            window=64,
            chunk=16,
            ff_mult=2,
            capsules=1,
            latent=6,
            rank=3,
            reads=3,
            memory=True,
        )
        model = FoldLanguageModel(config)
        checkpoint = self.root / "random.pt"
        torch.save({
            "format": "fold-lm-local-v1",
            "step": 0,
            "config": {
                "model": asdict(config),
                "train": asdict(TrainConfig(max_steps=1, cpu_threads=2)),
            },
            "model": model.state_dict(),
        }, checkpoint)

        result = evaluate_owner_candidates(
            checkpoint,
            examples,
            device_name="cpu",
            batch_examples=2,
        )
        self.assertEqual(result["examples"], 2)
        self.assertEqual(result["memory"], True)
        self.assertEqual(result["local_attention_window"], 64)
        self.assertGreaterEqual(result["accuracy"], 0.0)
        self.assertLessEqual(result["accuracy"], 1.0)
        self.assertEqual(result["chance_accuracy"], 1 / 12)


if __name__ == "__main__":
    unittest.main()
