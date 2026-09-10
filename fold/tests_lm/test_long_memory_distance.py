"""Tests for exact-distance long-memory capacity-sweep data generation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fold_lm.long_memory_benchmark import load_validation, make_counterfactuals
from fold_lm.long_memory_distance import generate_exact_distance_dataset


class LongMemoryDistanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_exact_distance_generation_is_deterministic(self):
        a = self.root / "a"
        b = self.root / "b"
        meta_a = generate_exact_distance_dataset(
            a, target_distance=256, train_rows=200, validation_rows=40
        )
        meta_b = generate_exact_distance_dataset(
            b, target_distance=256, train_rows=200, validation_rows=40
        )

        self.assertEqual((a / "train.jsonl").read_bytes(), (b / "train.jsonl").read_bytes())
        self.assertEqual((a / "validation.jsonl").read_bytes(), (b / "validation.jsonl").read_bytes())
        self.assertEqual(meta_a, meta_b)
        self.assertEqual(meta_a["target_distance_bytes"], 256)
        self.assertEqual(meta_a["fact_to_answer_distance_bytes"], {"min": 256, "max": 256})
        self.assertEqual(meta_a["cross_split_overlap"], 0)

    def test_every_validation_row_has_requested_owner_distance(self):
        output = self.root / "data"
        generate_exact_distance_dataset(
            output, target_distance=512, train_rows=100, validation_rows=30
        )
        for line in (output / "validation.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            prompt = row["prompt"]
            owner = row["target"][:-1]
            fact_owner = prompt.index(owner)
            answer_owner = len(prompt.encode("utf-8"))
            self.assertEqual(answer_owner - len(prompt[:fact_owner].encode("utf-8")), 512)

    def test_counterfactual_preserves_local_suffix_at_longer_distance(self):
        output = self.root / "data"
        generate_exact_distance_dataset(
            output, target_distance=512, train_rows=100, validation_rows=60
        )
        examples = load_validation(output / "validation.jsonl")
        changed, _ = make_counterfactuals(examples, seed=20260910, local_window=64)
        self.assertTrue(changed)
        for example in changed:
            self.assertIsNotNone(example.original_owner)
            old = example.prompt.replace(example.expected, example.original_owner, 1)
            self.assertEqual(len(old.encode("utf-8")), len(example.prompt.encode("utf-8")))
            self.assertEqual(old.encode("utf-8")[-64:], example.prompt.encode("utf-8")[-64:])

    def test_too_short_distance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "shorter than generated base distance|local-attention"):
            generate_exact_distance_dataset(
                self.root / "bad", target_distance=100, train_rows=10, validation_rows=2
            )


if __name__ == "__main__":
    unittest.main()
