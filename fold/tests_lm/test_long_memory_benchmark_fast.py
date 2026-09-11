"""Parity tests for the shared-prefix long-memory evaluator."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import random
import tempfile
import unittest

import torch

from fold_lm.long_memory_benchmark import (
    OwnerExample,
    _build_row,
    evaluate_owner_candidates,
    make_counterfactuals,
)
from fold_lm.long_memory_benchmark_fast import evaluate_owner_candidates_shared_prefix
from fold_lm.model import FoldLanguageModel, ModelConfig
from fold_lm.runner import TrainConfig


class SharedPrefixEvaluatorTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _checkpoint(self) -> Path:
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
        torch.manual_seed(1234)
        model = FoldLanguageModel(config)
        path = self.root / "model.pt"
        torch.save({
            "format": "fold-lm-local-v1",
            "step": 9,
            "config": {
                "model": asdict(config),
                "train": asdict(TrainConfig(max_steps=10, cpu_threads=2)),
            },
            "model": model.state_dict(),
        }, path)
        return path

    def _examples(self) -> list[OwnerExample]:
        rng = random.Random(20260911)
        rows = []
        for _ in range(8):
            row, _, _ = _build_row(rng, local_window=64, max_bytes=250)
            rows.append(OwnerExample(row["prompt"], row["target"][:-1]))
        return rows

    def _assert_same_result(self, reference: dict, fast: dict):
        self.assertEqual(fast["examples"], reference["examples"])
        self.assertEqual(fast["correct"], reference["correct"])
        self.assertAlmostEqual(fast["accuracy"], reference["accuracy"], places=7)
        self.assertAlmostEqual(
            fast["mean_top1_margin"],
            reference["mean_top1_margin"],
            places=5,
        )
        self.assertEqual(
            [(row.get("expected"), row.get("predicted"), row.get("old_fact"), row.get("new_fact")) for row in fast["first_mistakes"]],
            [(row.get("expected"), row.get("predicted"), row.get("old_fact"), row.get("new_fact")) for row in reference["first_mistakes"]],
        )

    def test_matches_reference_standard(self):
        checkpoint = self._checkpoint()
        examples = self._examples()
        reference = evaluate_owner_candidates(
            checkpoint,
            examples,
            device_name="cpu",
            batch_examples=3,
        )
        fast = evaluate_owner_candidates_shared_prefix(
            checkpoint,
            examples,
            device_name="cpu",
            batch_examples=3,
            progress=False,
        )
        self._assert_same_result(reference, fast)
        self.assertEqual(fast["evaluation_mode"], "shared-prefix-state-branch-v1")

    def test_matches_reference_counterfactual(self):
        checkpoint = self._checkpoint()
        changed, _ = make_counterfactuals(self._examples(), local_window=64)
        reference = evaluate_owner_candidates(
            checkpoint,
            changed,
            device_name="cpu",
            batch_examples=2,
        )
        fast = evaluate_owner_candidates_shared_prefix(
            checkpoint,
            changed,
            device_name="cpu",
            batch_examples=2,
            progress=False,
        )
        self._assert_same_result(reference, fast)
        self.assertAlmostEqual(
            fast["original_owner_prediction_rate"],
            reference["original_owner_prediction_rate"],
            places=7,
        )


if __name__ == "__main__":
    unittest.main()
