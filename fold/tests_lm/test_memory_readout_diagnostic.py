"""Offline tests for the FOLD-R readout-decomposition diagnostic."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

import torch

from fold_lm.long_memory_distance_v2 import generate_exact_distance_dataset_v2
from fold_lm.memory_readout_diagnostic import measure_readout_diagnostic
from fold_lm.model import FoldLanguageModel, ModelConfig
from fold_lm.runner import TrainConfig


class MemoryReadoutDiagnosticTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        generate_exact_distance_dataset_v2(
            self.data,
            target_distance=256,
            train_rows=80,
            validation_rows=12,
        )

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
        model = FoldLanguageModel(config)
        path = self.root / "memory.pt"
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

    def test_reports_readout_stage_ratios_and_denominator_spectrum(self):
        result = measure_readout_diagnostic(
            self._checkpoint(),
            self.data / "validation.jsonl",
            device_name="cpu",
            examples=3,
            fractions=(0.0, 0.5, 1.0),
        )
        self.assertEqual(result["examples"], 3)
        self.assertEqual(result["checkpoint_step"], 7)
        self.assertEqual([point["fraction"] for point in result["points"]], [0.0, 0.5, 1.0])

        baseline = result["points"][0]
        for key in (
            "mean_raw_signal_ratio",
            "mean_rhs_signal_ratio",
            "mean_correction_signal_ratio",
            "mean_response_signal_ratio",
        ):
            self.assertAlmostEqual(baseline[key], 1.0, places=5)
        self.assertGreaterEqual(baseline["mean_denominator_min_eigenvalue"], 1.0 - 1e-5)
        self.assertGreaterEqual(baseline["mean_denominator_max_eigenvalue"], 1.0 - 1e-5)

        endpoint = result["points"][-1]
        self.assertGreater(endpoint["mean_filler_bytes_processed"], 0)
        self.assertIsNotNone(endpoint["mean_rhs_signal_ratio"])
        self.assertIsNotNone(endpoint["mean_correction_signal_ratio"])
        self.assertIsNotNone(endpoint["mean_response_signal_ratio"])
        self.assertGreaterEqual(endpoint["mean_denominator_condition"], 1.0)
        self.assertGreater(endpoint["mean_inverse_min_gain_bound"], 0.0)


if __name__ == "__main__":
    unittest.main()
