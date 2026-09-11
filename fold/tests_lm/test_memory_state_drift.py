"""Offline tests for the FOLD-R filler-state drift diagnostic."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

import torch

from fold_lm.long_memory_benchmark import load_validation, make_counterfactuals
from fold_lm.long_memory_distance import generate_exact_distance_dataset
from fold_lm.memory_state_drift import (
    filler_bounds,
    measure_filler_state_drift,
    original_prompt,
)
from fold_lm.model import FoldLanguageModel, ModelConfig
from fold_lm.runner import TrainConfig


class MemoryStateDriftTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        generate_exact_distance_dataset(
            self.data,
            target_distance=256,
            train_rows=80,
            validation_rows=12,
        )

    def _checkpoint(self, *, memory: bool) -> Path:
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
            memory=memory,
        )
        model = FoldLanguageModel(config)
        path = self.root / ("memory.pt" if memory else "local.pt")
        torch.save({
            "format": "fold-lm-local-v1",
            "step": 7,
            "config": {
                "model": asdict(config),
                "train": asdict(TrainConfig(max_steps=10, cpu_threads=2)),
            },
            "model": model.state_dict(),
        }, path)
        return path

    def test_filler_bounds_and_counterfactual_reconstruction(self):
        examples = load_validation(self.data / "validation.jsonl")
        changed, _ = make_counterfactuals(examples, seed=20260910, local_window=64)
        example = changed[0]
        restored = original_prompt(example)
        start, end = filler_bounds(restored)
        changed_start, changed_end = filler_bounds(example.prompt)

        self.assertEqual((start, end), (changed_start, changed_end))
        self.assertEqual(
            restored.encode("utf-8")[start:end],
            example.prompt.encode("utf-8")[start:end],
        )
        self.assertNotEqual(restored, example.prompt)

    def test_measurement_reports_baseline_and_filler_progress(self):
        result = measure_filler_state_drift(
            self._checkpoint(memory=True),
            self.data / "validation.jsonl",
            device_name="cpu",
            examples=3,
            fractions=(0.0, 0.5, 1.0),
        )
        self.assertEqual(result["examples"], 3)
        self.assertEqual(result["checkpoint_step"], 7)
        self.assertEqual(result["local_attention_window"], 64)
        self.assertEqual([p["fraction"] for p in result["points"]], [0.0, 0.5, 1.0])

        baseline = result["points"][0]
        self.assertAlmostEqual(baseline["mean_common_state_drift_norm"], 0.0, places=7)
        self.assertAlmostEqual(baseline["mean_original_state_drift_norm"], 0.0, places=7)
        self.assertAlmostEqual(baseline["mean_counterfactual_state_drift_norm"], 0.0, places=7)
        self.assertAlmostEqual(baseline["mean_owner_signal_ratio"], 1.0, places=6)
        self.assertAlmostEqual(baseline["mean_owner_signal_cosine_to_start"], 1.0, places=6)

        endpoint = result["points"][-1]
        self.assertGreater(endpoint["mean_filler_bytes_processed"], 0)
        self.assertGreater(endpoint["mean_common_state_drift_norm"], 0)
        self.assertIsNotNone(endpoint["mean_owner_signal_ratio"])
        self.assertIsNotNone(endpoint["mean_owner_signal_cosine_to_start"])

    def test_local_only_checkpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "memory=true"):
            measure_filler_state_drift(
                self._checkpoint(memory=False),
                self.data / "validation.jsonl",
                device_name="cpu",
                examples=1,
            )


if __name__ == "__main__":
    unittest.main()
