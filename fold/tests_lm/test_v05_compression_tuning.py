from __future__ import annotations

import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.compression_init import (
    CompressionInitialization,
    initialize_from_dense_weights,
)
from fold_lm.v05.compression_tuning import (
    ContinuousTuningResult,
    FixedCodeContinuousCompression,
    fit_fixed_codes_to_dense,
)
from fold_lm.v05.compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


class V05CompressionTuningTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        rng = np.random.default_rng(17)
        self.weights = rng.normal(0.0, 0.35, size=(3, 4, 4)).astype(np.float64)
        self.initial = initialize_from_dense_weights(
            self.weights,
            block_rows=2,
            block_cols=2,
            codebook_count=1,
            entries_per_codebook=2,
            max_correction_entries=3,
            max_abs_correction=0.10,
        )

    def _perturbed_initialization(self) -> CompressionInitialization:
        template = BlockCodebookTemplate(
            base=self.initial.template.base + 0.08,
            codebooks=self.initial.template.codebooks - 0.03,
            block_rows=self.initial.template.block_rows,
            block_cols=self.initial.template.block_cols,
        )
        encoded = tuple(
            EncodedBlockWeight(
                template=template,
                codes=item.codes,
                correction_indices=item.correction_indices,
                correction_values=item.correction_values,
                max_correction_entries=item.max_correction_entries,
                max_abs_correction=item.max_abs_correction,
            )
            for item in self.initial.encoded_weights
        )
        return CompressionInitialization(
            template=template,
            encoded_weights=encoded,
            metrics=self.initial.metrics,
            accounting=self.initial.accounting,
        )

    def _mse(self, initialization: CompressionInitialization) -> float:
        reconstructed = np.stack(
            [encoded.materialize() for encoded in initialization.encoded_weights], axis=0
        )
        error = reconstructed - self.weights
        return float(np.mean(error * error))

    def test_codes_and_correction_coordinates_are_fixed_buffers(self):
        model = FixedCodeContinuousCompression(self.initial)
        parameter_names = {name for name, _ in model.named_parameters()}
        buffer_names = {name for name, _ in model.named_buffers()}
        self.assertIn("base", parameter_names)
        self.assertIn("codebooks", parameter_names)
        self.assertIn("codes", buffer_names)
        self.assertNotIn("codes", parameter_names)
        for index in range(model.module_count):
            self.assertIn(f"corrections.{index}.indices", buffer_names)
            self.assertIn(f"corrections.{index}.raw_values", parameter_names)

    def test_gradients_reach_continuous_values_but_not_discrete_choices(self):
        model = FixedCodeContinuousCompression(self.initial)
        targets = torch.tensor(self.weights, dtype=torch.float32)
        loss = F.mse_loss(model.materialized_weights(), targets)
        loss.backward()
        self.assertGreater(float(model.base.grad.abs().sum()), 0.0)
        self.assertGreater(float(model.codebooks.grad.abs().sum()), 0.0)
        correction_grad = sum(
            float(item.raw_values.grad.abs().sum())
            for item in model.corrections
            if item.raw_values.numel() > 0
        )
        self.assertGreater(correction_grad, 0.0)
        self.assertIsNone(model.codes.grad)

    def test_fixed_code_tuning_removes_added_error_down_to_representation_floor(self):
        perturbed = self._perturbed_initialization()
        reference_floor = self._mse(self.initial)
        result = fit_fixed_codes_to_dense(
            self.weights,
            perturbed,
            steps=120,
            learning_rate=0.02,
            device="cpu",
        )
        self.assertIsInstance(result, ContinuousTuningResult)
        self.assertGreater(result.initial_mse, reference_floor)
        self.assertGreater(result.initial_mse, result.final_mse)

        # Fixed codes and fixed correction coordinates impose a non-zero
        # representational floor.  Continuous tuning should remove the error
        # introduced by perturbing the continuous values; it is not expected to
        # halve the irreducible code-assignment error itself.
        added_error = result.initial_mse - reference_floor
        residual_added_error = max(result.final_mse - reference_floor, 0.0)
        self.assertLess(residual_added_error, added_error * 0.10)
        self.assertLessEqual(result.final_mse, reference_floor * 1.01 + 1e-8)

    def test_tuning_preserves_codes_coordinates_bounds_and_payload(self):
        perturbed = self._perturbed_initialization()
        result = fit_fixed_codes_to_dense(
            self.weights,
            perturbed,
            steps=80,
            learning_rate=0.02,
            device="cpu",
        )
        tuned = result.initialization
        self.assertEqual(tuned.accounting, perturbed.accounting)
        for before, after in zip(perturbed.encoded_weights, tuned.encoded_weights):
            np.testing.assert_array_equal(before.codes, after.codes)
            np.testing.assert_array_equal(before.correction_indices, after.correction_indices)
            self.assertEqual(before.correction_nnz, after.correction_nnz)
            if after.correction_values.size:
                self.assertLessEqual(
                    float(np.max(np.abs(after.correction_values))),
                    after.max_abs_correction + 1e-6,
                )

    def test_exported_metrics_match_tuned_reconstruction(self):
        result = fit_fixed_codes_to_dense(
            self.weights,
            self._perturbed_initialization(),
            steps=60,
            learning_rate=0.02,
            device="cpu",
        )
        for target, encoded, metric in zip(
            self.weights,
            result.initialization.encoded_weights,
            result.initialization.metrics,
        ):
            error = target - encoded.materialize()
            self.assertAlmostEqual(metric.rmse, float(np.sqrt(np.mean(error * error))), places=7)
            self.assertAlmostEqual(metric.max_abs_error, float(np.max(np.abs(error))), places=7)
            self.assertEqual(metric.correction_nnz, encoded.correction_nnz)

    def test_invalid_initialization_shapes_and_training_arguments_are_rejected(self):
        with self.assertRaises(TypeError):
            FixedCodeContinuousCompression(object())
        with self.assertRaises(ValueError):
            fit_fixed_codes_to_dense(self.weights, self.initial, steps=0)
        with self.assertRaises(ValueError):
            fit_fixed_codes_to_dense(self.weights, self.initial, learning_rate=0.0)
        with self.assertRaises(ValueError):
            fit_fixed_codes_to_dense(self.weights[:, :, :2], self.initial)
        bad = self.weights.copy()
        bad[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            fit_fixed_codes_to_dense(bad, self.initial)


if __name__ == "__main__":
    unittest.main()
