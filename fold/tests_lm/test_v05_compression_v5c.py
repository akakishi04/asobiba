from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


class V05CompressionV5CTests(unittest.TestCase):
    def setUp(self):
        self.base = np.arange(24, dtype=np.float64).reshape(4, 6) / 100.0
        self.codebooks = np.array(
            [
                [
                    [[0.01, 0.02, 0.03], [0.04, 0.05, 0.06]],
                    [[-0.01, 0.00, 0.01], [0.02, -0.02, 0.03]],
                    [[0.03, -0.01, 0.00], [0.01, 0.02, -0.03]],
                ],
                [
                    [[0.00, 0.01, -0.01], [0.01, 0.00, 0.02]],
                    [[0.02, 0.00, 0.01], [-0.01, 0.03, 0.00]],
                    [[-0.02, 0.02, 0.00], [0.00, -0.01, 0.01]],
                ],
            ],
            dtype=np.float64,
        )
        self.template = BlockCodebookTemplate(
            base=self.base,
            codebooks=self.codebooks,
            block_rows=2,
            block_cols=3,
        )
        self.codes = np.array(
            [
                [[0, 1], [1, 2]],
                [[2, 0], [1, 1]],
            ],
            dtype=np.int64,
        )
        self.indices = np.array([[0, 0], [3, 5]], dtype=np.int64)
        self.values = np.array([0.05, -0.04], dtype=np.float64)

    def make_weight(self) -> EncodedBlockWeight:
        return EncodedBlockWeight(
            template=self.template,
            codes=self.codes,
            correction_indices=self.indices,
            correction_values=self.values,
            max_correction_entries=2,
            max_abs_correction=0.05,
        )

    def test_materialize_matches_manual_block_decode_and_sparse_correction(self):
        encoded = self.make_weight()
        expected = self.base.copy()
        br, bc = 2, 3
        for rb in range(2):
            for cb in range(2):
                for q in range(2):
                    expected[
                        rb * br : (rb + 1) * br,
                        cb * bc : (cb + 1) * bc,
                    ] += self.codebooks[q, self.codes[rb, cb, q]]
        expected[0, 0] += 0.05
        expected[3, 5] -= 0.04
        np.testing.assert_allclose(encoded.materialize(), expected, rtol=0.0, atol=0.0)
        self.assertEqual(encoded.correction_nnz, 2)
        self.assertEqual(encoded.correction_density, 2 / 24)

    def test_direct_matmul_matches_materialized_for_rectangular_weight(self):
        encoded = self.make_weight()
        inputs = np.array(
            [[1.0, -0.5, 0.25, 2.0, 0.0, -1.0], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            dtype=np.float64,
        )
        direct = encoded.direct_matmul_transposed(inputs)
        materialized = inputs @ encoded.materialize().T
        np.testing.assert_allclose(direct, materialized, rtol=0.0, atol=1e-15)

    def test_multiple_modules_share_template_but_keep_codes_and_corrections_separate(self):
        first = self.make_weight()
        second_codes = np.zeros_like(self.codes)
        second = EncodedBlockWeight(
            template=self.template,
            codes=second_codes,
            max_correction_entries=0,
            max_abs_correction=0.0,
        )
        self.assertIs(first.template, second.template)
        self.assertFalse(np.array_equal(first.materialize(), second.materialize()))
        self.assertEqual(second.correction_nnz, 0)

    def test_correction_entry_and_magnitude_bounds_are_hard(self):
        with self.assertRaises(ValueError):
            EncodedBlockWeight(
                template=self.template,
                codes=self.codes,
                correction_indices=self.indices,
                correction_values=self.values,
                max_correction_entries=1,
                max_abs_correction=0.05,
            )
        with self.assertRaises(ValueError):
            EncodedBlockWeight(
                template=self.template,
                codes=self.codes,
                correction_indices=np.array([[0, 0]], dtype=np.int64),
                correction_values=np.array([0.051], dtype=np.float64),
                max_correction_entries=1,
                max_abs_correction=0.05,
            )
        with self.assertRaises(ValueError):
            EncodedBlockWeight(
                template=self.template,
                codes=self.codes,
                correction_indices=np.array([[0, 0], [0, 0]], dtype=np.int64),
                correction_values=np.array([0.01, 0.02], dtype=np.float64),
                max_correction_entries=2,
                max_abs_correction=0.05,
            )

    def test_invalid_block_shapes_codes_values_and_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            BlockCodebookTemplate(
                base=self.base,
                codebooks=self.codebooks,
                block_rows=3,
                block_cols=3,
            )
        with self.assertRaises(ValueError):
            BlockCodebookTemplate(
                base=self.base,
                codebooks=self.codebooks[:, :, :, :2],
                block_rows=2,
                block_cols=3,
            )
        bad_codes = self.codes.copy()
        bad_codes[0, 0, 0] = 99
        with self.assertRaises(ValueError):
            EncodedBlockWeight(template=self.template, codes=bad_codes)
        with self.assertRaises(ValueError):
            EncodedBlockWeight(
                template=self.template,
                codes=self.codes,
                correction_indices=np.array([[4, 0]], dtype=np.int64),
                correction_values=np.array([0.01], dtype=np.float64),
                max_correction_entries=1,
                max_abs_correction=0.05,
            )
        encoded = self.make_weight()
        with self.assertRaises(ValueError):
            encoded.direct_matmul_transposed(np.zeros((2, 5), dtype=np.float64))
        bad_inputs = np.zeros((2, 6), dtype=np.float64)
        bad_inputs[0, 0] = np.nan
        with self.assertRaises(ValueError):
            encoded.direct_matmul_transposed(bad_inputs)


if __name__ == "__main__":
    unittest.main()
