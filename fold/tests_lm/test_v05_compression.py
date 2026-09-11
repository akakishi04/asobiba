from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.compression import AdditiveCodebookWeight
from fold_lm.v05.core import ReferenceLinearCore
from fold_lm.v05.state import WorkingState


class V05CompressionReferenceTests(unittest.TestCase):
    def _encoded(self) -> AdditiveCodebookWeight:
        base = np.array([[1.0, 0.25], [-0.5, 0.75]], dtype=np.float64)
        codebook = np.array(
            [
                [
                    [[0.1, 0.0], [0.0, 0.2]],
                    [[0.0, 0.3], [0.4, 0.0]],
                    [[-0.2, 0.1], [0.0, 0.0]],
                ],
                [
                    [[0.05, -0.05], [0.1, 0.0]],
                    [[0.0, 0.0], [-0.2, 0.2]],
                    [[0.3, 0.0], [0.0, -0.1]],
                ],
            ],
            dtype=np.float64,
        )
        return AdditiveCodebookWeight(base=base, codebook=codebook, codes=np.array([1, 2]))

    def test_materialize_matches_manual_sum(self):
        encoded = self._encoded()
        expected = encoded.base + encoded.codebook[0, 1] + encoded.codebook[1, 2]
        np.testing.assert_array_equal(encoded.materialize(), expected)

    def test_direct_matmul_matches_materialized_weight(self):
        encoded = self._encoded()
        inputs = np.array([[1.0, 2.0], [-3.0, 0.5], [0.25, -1.25]], dtype=np.float64)
        direct = encoded.direct_matmul_transposed(inputs)
        materialized = inputs @ encoded.materialize().T
        np.testing.assert_allclose(direct, materialized, rtol=0.0, atol=1e-15)

    def test_direct_decode_matches_reference_core_linear_term(self):
        encoded = self._encoded()
        working = WorkingState(
            evidence_time=0,
            internal_step=0,
            slots=np.array([[0.5, -0.25], [1.0, 2.0]], dtype=np.float64),
        )
        context = np.array([[0.25, 0.5], [-0.5, 0.25]], dtype=np.float64)
        mixed = working.slots + context

        direct = encoded.direct_matmul_transposed(mixed)
        core = ReferenceLinearCore(
            weight=encoded.materialize(),
            bias=np.zeros(encoded.width, dtype=np.float64),
            gate=np.ones(encoded.width, dtype=np.float64),
        )
        expected_delta = core.compute_slots(working, context) - working.slots
        np.testing.assert_allclose(direct, expected_delta, rtol=0.0, atol=1e-15)

    def test_arrays_are_copied_and_read_only(self):
        base = np.eye(2, dtype=np.float64)
        codebook = np.zeros((1, 2, 2, 2), dtype=np.float64)
        codes = np.array([1], dtype=np.int32)
        encoded = AdditiveCodebookWeight(base=base, codebook=codebook, codes=codes)

        base[0, 0] = 99.0
        codebook[0, 1, 0, 0] = 88.0
        codes[0] = 0

        self.assertEqual(encoded.base[0, 0], 1.0)
        self.assertEqual(encoded.codebook[0, 1, 0, 0], 0.0)
        self.assertEqual(int(encoded.codes[0]), 1)
        self.assertFalse(encoded.base.flags.writeable)
        self.assertFalse(encoded.codebook.flags.writeable)
        self.assertFalse(encoded.codes.flags.writeable)
        self.assertFalse(encoded.materialize().flags.writeable)

    def test_invalid_shapes_codes_and_values_are_rejected(self):
        with self.assertRaises(ValueError):
            AdditiveCodebookWeight(
                base=np.ones((2, 3)),
                codebook=np.ones((1, 2, 2, 3)),
                codes=np.array([0]),
            )
        with self.assertRaises(ValueError):
            AdditiveCodebookWeight(
                base=np.eye(2),
                codebook=np.ones((1, 2, 3, 3)),
                codes=np.array([0]),
            )
        with self.assertRaises(TypeError):
            AdditiveCodebookWeight(
                base=np.eye(2),
                codebook=np.ones((1, 2, 2, 2)),
                codes=np.array([0.0]),
            )
        with self.assertRaises(ValueError):
            AdditiveCodebookWeight(
                base=np.eye(2),
                codebook=np.ones((1, 2, 2, 2)),
                codes=np.array([2]),
            )
        with self.assertRaises(ValueError):
            AdditiveCodebookWeight(
                base=np.array([[1.0, np.nan], [0.0, 1.0]]),
                codebook=np.ones((1, 2, 2, 2)),
                codes=np.array([0]),
            )
        encoded = self._encoded()
        with self.assertRaises(ValueError):
            encoded.direct_matmul_transposed(np.ones((2, 3)))
        with self.assertRaises(ValueError):
            encoded.direct_matmul_transposed(np.array([[1.0, np.inf]]))


if __name__ == "__main__":
    unittest.main()
