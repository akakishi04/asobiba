from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import torch

from fold_lm.v05.compressed_runtime import (
    ModuleCompressionConfig,
    initialize_module_weights_from_core,
)
from fold_lm.v05.composition_task import CompositionModel, CompositionTaskConfig
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import (
    FIXTURE_SCHEMA,
    load_runtime_fixture,
    save_runtime_fixture,
)
from fold_lm.v05_benchmarks.gate_c_task_aware_revalidation import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
)


class V05GateCRuntimeFixtureTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(20260912)
        self.model = CompositionModel(
            CompositionTaskConfig(width=8, modules=2, hidden_mult=2)
        )
        config = ModuleCompressionConfig(
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=2,
            max_abs_correction=0.10,
        )
        self.initializations = initialize_module_weights_from_core(
            self.model.core,
            up_config=config,
            down_config=config,
        )
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "composition.pt"

    def tearDown(self):
        self.tempdir.cleanup()

    def _save(self):
        return save_runtime_fixture(
            self.path,
            task="composition",
            seed=FRESH_SEEDS[0],
            dense_model=self.model,
            compressed_initializations=self.initializations,
            scores={"dense": 1.0, "direct": 1.0, "compact": 1.0},
        )

    def test_fixture_payload_loads_with_weights_only(self):
        self._save()
        payload = torch.load(self.path, map_location="cpu", weights_only=True)
        self.assertEqual(payload["schema"], FIXTURE_SCHEMA)
        self.assertEqual(payload["task"], "composition")
        self.assertEqual(payload["seed"], FRESH_SEEDS[0])
        self.assertEqual(payload["compressed_blob"].dtype, torch.uint8)
        self.assertTrue(payload["compressed_blob"].numel() > 0)

    def test_fixture_reconstructs_dense_direct_and_compact_models(self):
        self._save()
        loaded = load_runtime_fixture(self.path, device="cpu")
        self.assertEqual(loaded["task"], "composition")
        self.assertEqual(loaded["seed"], FRESH_SEEDS[0])
        self.assertEqual(set(loaded["models"]), {"dense", "direct", "compact"})
        validation = loaded["validation"]
        prepared = (
            validation.initial_values,
            validation.operations,
            validation.operands,
        )
        with torch.inference_mode():
            direct = loaded["models"]["direct"](*prepared)
            compact = loaded["models"]["compact"](*prepared)
        torch.testing.assert_close(compact, direct, rtol=1e-5, atol=1e-6)

    def test_fixture_restores_task_config_and_validation_deterministically(self):
        self._save()
        first = load_runtime_fixture(self.path, device="cpu")
        second = load_runtime_fixture(self.path, device="cpu")
        self.assertEqual(first["config"], second["config"])
        self.assertEqual(first["validation"].size, second["validation"].size)
        torch.testing.assert_close(
            first["validation"].targets,
            second["validation"].targets,
            rtol=0.0,
            atol=0.0,
        )

    def test_exploratory_seed_is_rejected(self):
        with self.assertRaises(ValueError):
            save_runtime_fixture(
                self.path,
                task="composition",
                seed=EXPLORATORY_SEEDS[0],
                dense_model=self.model,
                compressed_initializations=self.initializations,
                scores={"dense": 1.0, "direct": 1.0, "compact": 1.0},
            )

    def test_corrupt_schema_and_invalid_scores_are_rejected(self):
        with self.assertRaises(ValueError):
            save_runtime_fixture(
                self.path,
                task="composition",
                seed=FRESH_SEEDS[0],
                dense_model=self.model,
                compressed_initializations=self.initializations,
                scores={"dense": 1.0},
            )
        self._save()
        payload = torch.load(self.path, map_location="cpu", weights_only=True)
        payload["schema"] = "bad-schema"
        torch.save(payload, self.path)
        with self.assertRaises(ValueError):
            load_runtime_fixture(self.path, device="cpu")


if __name__ == "__main__":
    unittest.main()
