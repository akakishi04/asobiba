from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.accounting import (
    StorageAccounting,
    accounting_for,
    code_bits_per_index,
    serialize_additive_codebook,
)
from fold_lm.v05.compression import AdditiveCodebookWeight


class V05AccountingTests(unittest.TestCase):
    def _weight(self) -> AdditiveCodebookWeight:
        base = np.arange(4, dtype=np.float64).reshape(2, 2) / 10.0
        codebook = np.arange(3 * 5 * 2 * 2, dtype=np.float64).reshape(3, 5, 2, 2) / 100.0
        codes = np.array([4, 1, 3], dtype=np.int64)
        return AdditiveCodebookWeight(base=base, codebook=codebook, codes=codes)

    def test_accounting_separates_continuous_scalars_code_bits_and_metadata(self):
        report = accounting_for(self._weight())
        self.assertEqual(report.independent_continuous_scalars, 64)
        self.assertEqual(report.continuous_payload_bytes, 64 * 8)
        self.assertEqual(report.discrete_code_bits, 9)
        self.assertEqual(report.discrete_code_bytes, 2)
        self.assertEqual(report.metadata_bytes, 17)
        self.assertEqual(report.serialized_bytes, 531)

    def test_serialized_length_matches_accounting_exactly(self):
        weight = self._weight()
        blob = serialize_additive_codebook(weight)
        report = accounting_for(weight)
        self.assertEqual(len(blob), report.serialized_bytes)
        self.assertEqual(blob[:4], b"F05A")

    def test_serialization_is_deterministic(self):
        weight = self._weight()
        first = serialize_additive_codebook(weight)
        second = serialize_additive_codebook(weight)
        self.assertEqual(first, second)

    def test_one_entry_codebook_needs_zero_code_bits(self):
        weight = AdditiveCodebookWeight(
            base=np.eye(2, dtype=np.float64),
            codebook=np.zeros((2, 1, 2, 2), dtype=np.float64),
            codes=np.array([0, 0], dtype=np.int64),
        )
        report = accounting_for(weight)
        self.assertEqual(code_bits_per_index(1), 0)
        self.assertEqual(report.discrete_code_bits, 0)
        self.assertEqual(report.discrete_code_bytes, 0)
        self.assertEqual(len(serialize_additive_codebook(weight)), report.serialized_bytes)

    def test_invalid_accounting_and_entry_count_are_rejected(self):
        with self.assertRaises(ValueError):
            code_bits_per_index(0)
        with self.assertRaises(TypeError):
            accounting_for(object())
        with self.assertRaises(ValueError):
            StorageAccounting(
                independent_continuous_scalars=1,
                continuous_payload_bytes=8,
                discrete_code_bits=1,
                discrete_code_bytes=1,
                metadata_bytes=4,
                serialized_bytes=99,
            )


if __name__ == "__main__":
    unittest.main()
