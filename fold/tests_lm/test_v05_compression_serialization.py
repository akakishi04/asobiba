from __future__ import annotations

import unittest

import numpy as np
import torch

from fold_lm.v05.compressed_runtime import (
    CompressedModuleInitializations,
    DirectCompressedLinearBank,
)
from fold_lm.v05.compression_init import initialize_from_dense_weights
from fold_lm.v05.compression_serialization import (
    accounting_for_modules,
    accounting_for_role,
    deserialize_module_initializations,
    deserialize_role,
    serialize_module_initializations,
    serialize_role,
)


class V05CompressionSerializationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(20260912)
        # Two same-role module matrices.  The small correction budget ensures the
        # format exercises codes, per-module metadata, coordinates, and values.
        self.up_weights = rng.normal(0.0, 0.25, size=(2, 8, 4)).astype(np.float64)
        self.down_weights = rng.normal(0.0, 0.25, size=(2, 4, 8)).astype(np.float64)
        self.up = initialize_from_dense_weights(
            self.up_weights,
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=2,
            max_abs_correction=0.10,
        )
        self.down = initialize_from_dense_weights(
            self.down_weights,
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=2,
            max_abs_correction=0.10,
        )
        self.modules = CompressedModuleInitializations(up=self.up, down=self.down)

    def test_role_blob_length_matches_exact_accounting_and_includes_metadata(self):
        accounting = accounting_for_role(self.up)
        blob = serialize_role(self.up)
        self.assertEqual(len(blob), accounting.serialized_bytes)
        self.assertGreater(accounting.metadata_bytes, 0)
        self.assertGreater(
            accounting.serialized_bytes,
            self.up.accounting.estimated_encoded_payload_bytes,
        )
        self.assertEqual(
            accounting.serialized_bytes,
            accounting.continuous_payload_bytes
            + accounting.discrete_code_bytes
            + accounting.correction_payload_bytes
            + accounting.metadata_bytes,
        )

    def test_role_round_trip_preserves_codes_corrections_and_materialized_weights(self):
        restored = deserialize_role(serialize_role(self.up))
        np.testing.assert_array_equal(restored.template.base, self.up.template.base.astype(np.float32))
        np.testing.assert_array_equal(
            restored.template.codebooks,
            self.up.template.codebooks.astype(np.float32),
        )
        for before, after in zip(self.up.encoded_weights, restored.encoded_weights):
            np.testing.assert_array_equal(before.codes, after.codes)
            np.testing.assert_array_equal(before.correction_indices, after.correction_indices)
            np.testing.assert_array_equal(
                before.correction_values.astype(np.float32), after.correction_values
            )
            self.assertEqual(before.max_correction_entries, after.max_correction_entries)
            self.assertAlmostEqual(before.max_abs_correction, after.max_abs_correction, places=6)
            np.testing.assert_allclose(
                before.materialize().astype(np.float32),
                after.materialize().astype(np.float32),
                rtol=0.0,
                atol=0.0,
            )

    def test_module_pair_round_trip_and_ratios_are_exact(self):
        accounting = accounting_for_modules(self.modules)
        blob = serialize_module_initializations(self.modules)
        restored = deserialize_module_initializations(blob)
        self.assertEqual(len(blob), accounting.serialized_bytes)
        self.assertEqual(
            accounting.dense_float32_bytes,
            self.up.accounting.dense_float32_bytes
            + self.down.accounting.dense_float32_bytes,
        )
        self.assertAlmostEqual(
            accounting.serialized_ratio,
            accounting.serialized_bytes / accounting.dense_float32_bytes,
        )
        self.assertAlmostEqual(
            accounting.compact_resident_ratio,
            accounting.compact_resident_tensor_bytes / accounting.dense_float32_bytes,
        )
        self.assertAlmostEqual(
            accounting.reference_runtime_resident_ratio,
            accounting.reference_runtime_tensor_bytes / accounting.dense_float32_bytes,
        )
        for before_role, after_role in ((self.up, restored.up), (self.down, restored.down)):
            for before, after in zip(before_role.encoded_weights, after_role.encoded_weights):
                np.testing.assert_allclose(
                    before.materialize().astype(np.float32),
                    after.materialize().astype(np.float32),
                    rtol=0.0,
                    atol=0.0,
                )

    def test_reference_runtime_tensor_bytes_match_actual_direct_bank_buffers(self):
        accounting = accounting_for_role(self.up)
        bank = DirectCompressedLinearBank(self.up)
        # DirectCompressedLinearBank owns each compressed tensor once.  Count
        # registered buffers recursively; module wrappers only reference the bank.
        actual = sum(
            int(buffer.numel() * buffer.element_size())
            for _name, buffer in bank.named_buffers()
        )
        self.assertEqual(actual, accounting.reference_runtime_tensor_bytes)
        self.assertGreaterEqual(
            accounting.reference_runtime_tensor_bytes,
            accounting.compact_resident_tensor_bytes,
        )
        # Bit-packed on-disk codes are strictly smaller than unpacked uint8 codes
        # for this 4-entry (2-bit) codebook configuration.
        self.assertLess(accounting.discrete_code_bytes, int(self.up.encoded_weights[0].codes.size * 2))

    def test_invalid_or_truncated_blobs_are_rejected(self):
        role_blob = serialize_role(self.up)
        pair_blob = serialize_module_initializations(self.modules)
        with self.assertRaises(TypeError):
            deserialize_role("not-bytes")
        with self.assertRaises(ValueError):
            deserialize_role(role_blob[:8])
        with self.assertRaises(ValueError):
            deserialize_role(role_blob + b"x")
        corrupted = bytearray(role_blob)
        corrupted[0:4] = b"BAD!"
        with self.assertRaises(ValueError):
            deserialize_role(bytes(corrupted))
        with self.assertRaises(ValueError):
            deserialize_module_initializations(pair_blob[:-1])
        corrupted_pair = bytearray(pair_blob)
        corrupted_pair[0:4] = b"BAD!"
        with self.assertRaises(ValueError):
            deserialize_module_initializations(bytes(corrupted_pair))


if __name__ == "__main__":
    unittest.main()
