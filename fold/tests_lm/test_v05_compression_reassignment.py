from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.compression_init import (
    CompressionInitialization,
    InitializationAccounting,
    ReconstructionMetrics,
    initialize_from_dense_weights,
)
from fold_lm.v05.compression_reassignment import (
    CodeReassignmentResult,
    reassign_block_codes,
)
from fold_lm.v05.compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


class V05CompressionReassignmentTests(unittest.TestCase):
    def _manual_case(self, *, with_correction: bool = False):
        template = BlockCodebookTemplate(
            base=np.zeros((4, 4), dtype=np.float64),
            codebooks=np.array(
                [
                    [
                        [[0.0, 0.0], [0.0, 0.0]],
                        [[1.0, -1.0], [0.5, -0.5]],
                    ]
                ],
                dtype=np.float64,
            ),
            block_rows=2,
            block_cols=2,
        )
        correct_codes = np.array(
            [[[0], [1]], [[1], [0]]], dtype=np.int64
        )
        correction_indices = (
            np.array([[0, 0]], dtype=np.int64)
            if with_correction
            else np.empty((0, 2), dtype=np.int64)
        )
        correction_values = (
            np.array([0.25], dtype=np.float64)
            if with_correction
            else np.empty((0,), dtype=np.float64)
        )
        correct = EncodedBlockWeight(
            template=template,
            codes=correct_codes,
            correction_indices=correction_indices,
            correction_values=correction_values,
            max_correction_entries=1 if with_correction else 0,
            max_abs_correction=0.25 if with_correction else 0.0,
        )
        target = np.stack([correct.materialize()], axis=0)

        wrong = EncodedBlockWeight(
            template=template,
            codes=np.zeros_like(correct_codes),
            correction_indices=correction_indices,
            correction_values=correction_values,
            max_correction_entries=1 if with_correction else 0,
            max_abs_correction=0.25 if with_correction else 0.0,
        )
        accounting = InitializationAccounting(
            dense_float32_bytes=64,
            shared_continuous_float32_bytes=96,
            discrete_code_bits=4,
            discrete_code_bytes=1,
            correction_payload_bytes=12 if with_correction else 0,
            estimated_encoded_payload_bytes=109 if with_correction else 97,
        )
        initialization = CompressionInitialization(
            template=template,
            encoded_weights=(wrong,),
            metrics=(
                ReconstructionMetrics(
                    rmse=float(np.sqrt(np.mean((target[0] - wrong.materialize()) ** 2))),
                    max_abs_error=float(np.max(np.abs(target[0] - wrong.materialize()))),
                    correction_nnz=wrong.correction_nnz,
                    correction_density=wrong.correction_density,
                ),
            ),
            accounting=accounting,
        )
        return target, correct_codes, initialization

    def test_wrong_codes_are_reassigned_to_exact_block_solution(self):
        target, correct_codes, initialization = self._manual_case()
        result = reassign_block_codes(target, initialization, sweeps=3)
        self.assertIsInstance(result, CodeReassignmentResult)
        self.assertGreater(result.initial_mse, 0.0)
        self.assertEqual(result.final_mse, 0.0)
        np.testing.assert_array_equal(
            result.initialization.encoded_weights[0].codes,
            correct_codes,
        )
        self.assertGreater(result.changed_code_count, 0)

    def test_reassignment_is_deterministic_and_non_worsening(self):
        target, _, initialization = self._manual_case()
        first = reassign_block_codes(target, initialization, sweeps=4)
        second = reassign_block_codes(target, initialization, sweeps=4)
        self.assertLessEqual(first.final_mse, first.initial_mse)
        self.assertEqual(first.final_mse, second.final_mse)
        self.assertEqual(first.changed_code_count, second.changed_code_count)
        np.testing.assert_array_equal(
            first.initialization.encoded_weights[0].codes,
            second.initialization.encoded_weights[0].codes,
        )

    def test_template_correction_and_payload_are_unchanged(self):
        target, _, initialization = self._manual_case(with_correction=True)
        before = initialization.encoded_weights[0]
        result = reassign_block_codes(target, initialization, sweeps=2)
        after = result.initialization.encoded_weights[0]
        self.assertIs(result.initialization.template, initialization.template)
        self.assertEqual(result.initialization.accounting, initialization.accounting)
        np.testing.assert_array_equal(before.correction_indices, after.correction_indices)
        np.testing.assert_array_equal(before.correction_values, after.correction_values)
        self.assertEqual(before.max_correction_entries, after.max_correction_entries)
        self.assertEqual(before.max_abs_correction, after.max_abs_correction)

    def test_fixed_correction_is_included_when_selecting_codes(self):
        target, correct_codes, initialization = self._manual_case(with_correction=True)
        result = reassign_block_codes(target, initialization, sweeps=3)
        np.testing.assert_array_equal(
            result.initialization.encoded_weights[0].codes,
            correct_codes,
        )
        self.assertEqual(result.final_mse, 0.0)
        after = result.initialization.encoded_weights[0]
        self.assertLessEqual(float(np.max(np.abs(after.correction_values))), 0.25)

    def test_real_dense_initialization_can_be_reassigned_and_metrics_match(self):
        rng = np.random.default_rng(29)
        weights = rng.normal(0.0, 0.25, size=(3, 4, 4)).astype(np.float64)
        initialization = initialize_from_dense_weights(
            weights,
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=3,
            max_correction_entries=2,
            max_abs_correction=0.10,
        )
        result = reassign_block_codes(weights, initialization, sweeps=3)
        self.assertLessEqual(result.final_mse, result.initial_mse + 1e-12)
        for target, encoded, metric in zip(
            weights,
            result.initialization.encoded_weights,
            result.initialization.metrics,
        ):
            error = target - encoded.materialize()
            self.assertAlmostEqual(
                metric.rmse, float(np.sqrt(np.mean(error * error))), places=10
            )
            self.assertAlmostEqual(
                metric.max_abs_error, float(np.max(np.abs(error))), places=10
            )

    def test_invalid_inputs_and_sweeps_are_rejected(self):
        target, _, initialization = self._manual_case()
        with self.assertRaises(TypeError):
            reassign_block_codes(target, object())
        with self.assertRaises(ValueError):
            reassign_block_codes(target, initialization, sweeps=0)
        with self.assertRaises(ValueError):
            reassign_block_codes(target[:, :, :2], initialization)
        bad = target.copy()
        bad[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            reassign_block_codes(bad, initialization)


if __name__ == "__main__":
    unittest.main()
