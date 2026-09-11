from __future__ import annotations

import unittest

import numpy as np
import torch

from fold_lm.v05.compression_init import initialize_from_dense_weights
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class V05CompressionInitializationTests(unittest.TestCase):
    def test_exact_two_pattern_dense_weights_reconstruct_without_correction(self):
        base = np.arange(16, dtype=np.float64).reshape(4, 4) * 0.01
        delta = np.array(
            [
                [0.10, -0.05, 0.10, -0.05],
                [0.02, 0.03, 0.02, 0.03],
                [0.10, -0.05, 0.10, -0.05],
                [0.02, 0.03, 0.02, 0.03],
            ],
            dtype=np.float64,
        )
        weights = np.stack([base + delta, base - delta], axis=0)
        result = initialize_from_dense_weights(
            weights,
            block_rows=2,
            block_cols=2,
            codebook_count=1,
            entries_per_codebook=2,
        )
        for source, encoded, metric in zip(weights, result.encoded_weights, result.metrics):
            np.testing.assert_allclose(encoded.materialize(), source, rtol=0.0, atol=1e-12)
            self.assertLess(metric.rmse, 1e-12)
            self.assertLess(metric.max_abs_error, 1e-12)
            self.assertEqual(metric.correction_nnz, 0)

    def test_sparse_bounded_correction_reduces_residual_and_obeys_limits(self):
        weights = np.array(
            [
                [[0.0, 0.3], [0.1, -0.2]],
                [[0.2, -0.4], [0.0, 0.5]],
            ],
            dtype=np.float64,
        )
        without = initialize_from_dense_weights(
            weights,
            block_rows=1,
            block_cols=1,
            codebook_count=1,
            entries_per_codebook=1,
        )
        with_correction = initialize_from_dense_weights(
            weights,
            block_rows=1,
            block_cols=1,
            codebook_count=1,
            entries_per_codebook=1,
            max_correction_entries=2,
            max_abs_correction=0.05,
        )
        self.assertLess(
            sum(metric.rmse for metric in with_correction.metrics),
            sum(metric.rmse for metric in without.metrics),
        )
        for encoded, metric in zip(with_correction.encoded_weights, with_correction.metrics):
            self.assertLessEqual(encoded.correction_nnz, 2)
            self.assertLessEqual(
                float(np.max(np.abs(encoded.correction_values), initial=0.0)),
                0.05,
            )
            self.assertEqual(metric.correction_nnz, encoded.correction_nnz)

    def test_initialization_is_deterministic_and_all_modules_share_one_template(self):
        rng = np.random.default_rng(17)
        weights = rng.normal(size=(3, 8, 8))
        kwargs = dict(
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=3,
            max_abs_correction=0.02,
        )
        first = initialize_from_dense_weights(weights, **kwargs)
        second = initialize_from_dense_weights(weights, **kwargs)
        np.testing.assert_array_equal(first.template.base, second.template.base)
        np.testing.assert_array_equal(first.template.codebooks, second.template.codebooks)
        for left, right in zip(first.encoded_weights, second.encoded_weights):
            self.assertIs(left.template, first.template)
            np.testing.assert_array_equal(left.codes, right.codes)
            np.testing.assert_array_equal(left.correction_indices, right.correction_indices)
            np.testing.assert_array_equal(left.correction_values, right.correction_values)

    def test_payload_accounting_separates_shared_codes_and_correction(self):
        rng = np.random.default_rng(23)
        weights = rng.normal(size=(4, 16, 16))
        result = initialize_from_dense_weights(
            weights,
            block_rows=4,
            block_cols=4,
            codebook_count=1,
            entries_per_codebook=2,
        )
        accounting = result.accounting
        self.assertEqual(accounting.dense_float32_bytes, 4 * 16 * 16 * 4)
        self.assertEqual(
            accounting.shared_continuous_float32_bytes,
            (16 * 16 + 2 * 4 * 4) * 4,
        )
        self.assertEqual(accounting.discrete_code_bits, 4 * 4 * 4)
        self.assertEqual(accounting.discrete_code_bytes, 8)
        self.assertEqual(accounting.correction_payload_bytes, 0)
        self.assertLess(accounting.estimated_payload_ratio, 0.4)

    def test_real_v5b_module_up_weights_can_be_initialized(self):
        torch.manual_seed(31)
        core = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(width=8, slots=2, modules=3, hidden_mult=2)
        )
        weights = np.stack(
            [
                module.up.weight.detach().cpu().numpy()
                for module in core.module_set
            ],
            axis=0,
        )
        result = initialize_from_dense_weights(
            weights,
            block_rows=4,
            block_cols=4,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=4,
            max_abs_correction=0.02,
        )
        self.assertEqual(len(result.encoded_weights), 3)
        self.assertEqual(result.template.base.shape, (16, 8))
        self.assertEqual(result.encoded_weights[0].codes.shape, (4, 2, 2))
        self.assertTrue(all(np.isfinite(metric.rmse) for metric in result.metrics))

    def test_invalid_dense_shapes_configuration_and_nonfinite_values_are_rejected(self):
        weights = np.zeros((2, 4, 4), dtype=np.float64)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights[0], block_rows=2, block_cols=2)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights, block_rows=3, block_cols=2)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights, block_rows=2, block_cols=2, codebook_count=0)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights, block_rows=2, block_cols=2, entries_per_codebook=99)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights, block_rows=2, block_cols=2, max_correction_entries=-1)
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(weights, block_rows=2, block_cols=2, max_abs_correction=-0.1)
        bad = weights.copy()
        bad[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            initialize_from_dense_weights(bad, block_rows=2, block_cols=2)


if __name__ == "__main__":
    unittest.main()
