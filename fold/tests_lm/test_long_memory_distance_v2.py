"""Tests for the exact-distance diverse-filler long-memory benchmark."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fold_lm.long_memory_benchmark import NAMES, OBJECTS, load_validation, make_counterfactuals
from fold_lm.long_memory_distance import FILLER_UNIT
from fold_lm.long_memory_distance_v2 import (
    TRAIN_FILLER_WORDS,
    VALIDATION_FILLER_WORDS,
    generate_exact_distance_dataset_v2,
)


class LongMemoryDistanceV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def _filler(self, row: dict) -> str:
        prompt = row["prompt"]
        start = prompt.index(FILLER_UNIT)
        end = prompt.rindex("Question: ")
        return prompt[start:end]

    def test_generation_is_deterministic_and_exact_distance(self):
        a = self.root / "a"
        b = self.root / "b"
        meta_a = generate_exact_distance_dataset_v2(
            a, target_distance=512, train_rows=120, validation_rows=30
        )
        meta_b = generate_exact_distance_dataset_v2(
            b, target_distance=512, train_rows=120, validation_rows=30
        )

        self.assertEqual((a / "train.jsonl").read_bytes(), (b / "train.jsonl").read_bytes())
        self.assertEqual((a / "validation.jsonl").read_bytes(), (b / "validation.jsonl").read_bytes())
        self.assertEqual(meta_a, meta_b)
        self.assertEqual(meta_a["benchmark"], "fold-r-long-memory-owner-distance-v2-diverse-filler")
        self.assertEqual(meta_a["fact_to_answer_distance_bytes"], {"min": 512, "max": 512})
        self.assertEqual(meta_a["exact_filler_overlap"], 0)

        for row in self._rows(a / "validation.jsonl"):
            prompt = row["prompt"]
            owner = row["target"][:-1]
            fact_owner = prompt.index(owner)
            answer_owner = len(prompt.encode("utf-8"))
            self.assertEqual(answer_owner - len(prompt[:fact_owner].encode("utf-8")), 512)

    def test_train_and_validation_use_diverse_held_out_filler(self):
        output = self.root / "data"
        generate_exact_distance_dataset_v2(
            output, target_distance=512, train_rows=160, validation_rows=40
        )
        train_fillers = {self._filler(row) for row in self._rows(output / "train.jsonl")}
        validation_fillers = {self._filler(row) for row in self._rows(output / "validation.jsonl")}

        self.assertGreater(len(train_fillers), 100)
        self.assertGreater(len(validation_fillers), 30)
        self.assertFalse(train_fillers & validation_fillers)
        self.assertFalse(set(TRAIN_FILLER_WORDS) & set(VALIDATION_FILLER_WORDS))

        for filler in train_fillers | validation_fillers:
            lowered = filler.lower()
            self.assertFalse(any(name.lower() in lowered for name in NAMES))
            self.assertFalse(any(obj.lower() in lowered for obj in OBJECTS))

    def test_counterfactual_keeps_diverse_filler_and_local_suffix_identical(self):
        output = self.root / "data"
        generate_exact_distance_dataset_v2(
            output, target_distance=512, train_rows=100, validation_rows=60
        )
        examples = load_validation(output / "validation.jsonl")
        changed, _ = make_counterfactuals(examples, seed=20260910, local_window=64)
        self.assertTrue(changed)
        for example in changed:
            self.assertIsNotNone(example.original_owner)
            original = example.prompt.replace(example.expected, example.original_owner, 1)
            self.assertEqual(len(original.encode("utf-8")), len(example.prompt.encode("utf-8")))
            self.assertEqual(original.encode("utf-8")[-64:], example.prompt.encode("utf-8")[-64:])
            original_start = original.index(FILLER_UNIT)
            changed_start = example.prompt.index(FILLER_UNIT)
            original_end = original.rindex("Question: ")
            changed_end = example.prompt.rindex("Question: ")
            self.assertEqual(
                original[original_start:original_end],
                example.prompt[changed_start:changed_end],
            )

    def test_too_short_distance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "shorter than generated base distance|local-attention"):
            generate_exact_distance_dataset_v2(
                self.root / "bad", target_distance=100, train_rows=10, validation_rows=2
            )


if __name__ == "__main__":
    unittest.main()
