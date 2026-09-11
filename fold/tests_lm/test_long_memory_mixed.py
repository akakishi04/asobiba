"""Tests for mixed-distance long-memory benchmark generation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fold_lm.long_memory_benchmark import load_validation, make_counterfactuals
from fold_lm.long_memory_mixed import (
    DEFAULT_EXTRAPOLATION_DISTANCES,
    TRAIN_DISTANCE_BANDS,
    generate_mixed_distance_dataset,
)


class LongMemoryMixedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _generate(self, name: str):
        output = self.root / name
        meta = generate_mixed_distance_dataset(
            output,
            train_rows=80,
            validation_rows=40,
            extrapolation_rows=8,
        )
        return output, meta

    def test_generation_is_deterministic(self):
        a, meta_a = self._generate("a")
        b, meta_b = self._generate("b")
        self.assertEqual(meta_a, meta_b)
        for name in meta_a["files"]:
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())

    def test_training_range_is_band_balanced_and_extrapolation_is_unseen(self):
        output, meta = self._generate("data")
        counts = meta["training_distance_policy"]["counts"]
        self.assertEqual(set(counts.values()), {20})
        self.assertEqual(meta["training_distance_policy"]["min_bytes"], 256)
        self.assertEqual(meta["training_distance_policy"]["max_bytes"], 4096)
        self.assertEqual(meta["extrapolation_distances_seen_in_training"], 0)

        train_distances = []
        for line in (output / "train.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            train_distances.append(row["distance_bytes"])
            self.assertTrue(any(lo <= row["distance_bytes"] <= hi for lo, hi in TRAIN_DISTANCE_BANDS))
        self.assertLessEqual(max(train_distances), 4096)

        for distance in DEFAULT_EXTRAPOLATION_DISTANCES:
            rows = [json.loads(line) for line in (output / f"eval-{distance}.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["distance_bytes"] == distance for row in rows))
            self.assertGreater(distance, max(train_distances))

    def test_validation_and_extrapolation_support_counterfactuals(self):
        output, _ = self._generate("data")
        for name in ("validation.jsonl", "eval-8192.jsonl"):
            examples = load_validation(output / name)
            changed, _ = make_counterfactuals(examples, seed=20260910, local_window=64)
            self.assertTrue(changed)
            for example in changed:
                self.assertIsNotNone(example.original_owner)
                old = example.prompt.replace(example.expected, example.original_owner, 1)
                self.assertEqual(old.encode("utf-8")[-64:], example.prompt.encode("utf-8")[-64:])

    def test_invalid_extrapolation_distance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than 4096"):
            generate_mixed_distance_dataset(
                self.root / "bad",
                train_rows=8,
                validation_rows=4,
                extrapolation_rows=2,
                extrapolation_distances=(4096,),
            )


if __name__ == "__main__":
    unittest.main()
