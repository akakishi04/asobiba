from __future__ import annotations

import unittest

import torch

from fold_lm.v05.compact_runtime import (
    CompactVectorizedFixedRoutingCore,
    CompactVectorizedLinearBank,
)
from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    ModuleCompressionConfig,
    DirectCompressedLinearBank,
    initialize_module_weights_from_core,
)
from fold_lm.v05.compression_serialization import accounting_for_role
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class V05CompactRuntimeTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(20260912)
        self.source = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(width=8, slots=2, modules=2, hidden_mult=2)
        )
        config = ModuleCompressionConfig(
            block_rows=2,
            block_cols=2,
            codebook_count=2,
            entries_per_codebook=4,
            max_correction_entries=4,
            max_abs_correction=0.10,
        )
        self.initializations = initialize_module_weights_from_core(
            self.source,
            up_config=config,
            down_config=config,
        )

    def test_compact_bank_matches_direct_reference(self):
        direct = DirectCompressedLinearBank(self.initializations.up)
        compact = CompactVectorizedLinearBank(self.initializations.up)
        value = torch.randn(5, 3, compact.input_width)
        for module_index in range(compact.module_count):
            expected = direct(value, module_index=module_index)
            actual = compact(value, module_index=module_index)
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)

    def test_compact_buffers_match_compact_resident_accounting(self):
        for initialization in (self.initializations.up, self.initializations.down):
            bank = CompactVectorizedLinearBank(initialization)
            accounting = accounting_for_role(initialization)
            self.assertEqual(
                bank.resident_tensor_bytes,
                accounting.compact_resident_tensor_bytes,
            )
            self.assertLess(
                bank.resident_tensor_bytes,
                accounting.dense_float32_bytes,
            )
            self.assertEqual(bank.codes.dtype, torch.uint8)
            for module_index in range(bank.module_count):
                indices = getattr(bank, f"correction_indices_{module_index}")
                self.assertEqual(indices.dtype, torch.int32)

    def test_compact_core_matches_direct_compressed_core(self):
        direct = CompressedFixedRoutingCore(self.source, self.initializations)
        compact = CompactVectorizedFixedRoutingCore(self.source, self.initializations)
        working = torch.randn(4, self.source.config.slots, self.source.config.width)
        context = torch.randn_like(working)
        for route_index in range(self.source.config.modules):
            expected = direct(working, context, route_index=route_index)
            actual = compact(working, context, route_index=route_index)
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)

    def test_compact_core_preserves_noncompressed_parameters(self):
        compact = CompactVectorizedFixedRoutingCore(self.source, self.initializations)
        for source_parameter, compact_parameter in zip(
            self.source.shared.parameters(), compact.shared.parameters()
        ):
            torch.testing.assert_close(compact_parameter, source_parameter, rtol=0.0, atol=0.0)
        torch.testing.assert_close(compact.gate_logits, self.source.gate_logits, rtol=0.0, atol=0.0)
        for index, source_module in enumerate(self.source.module_set):
            for source_parameter, compact_parameter in zip(
                source_module.norm.parameters(), compact.norms[index].parameters()
            ):
                torch.testing.assert_close(compact_parameter, source_parameter, rtol=0.0, atol=0.0)

    def test_invalid_types_routes_shapes_and_values_are_rejected(self):
        with self.assertRaises(TypeError):
            CompactVectorizedLinearBank(object())
        with self.assertRaises(TypeError):
            CompactVectorizedFixedRoutingCore(object(), self.initializations)

        bank = CompactVectorizedLinearBank(self.initializations.up)
        value = torch.randn(2, bank.input_width)
        with self.assertRaises(ValueError):
            bank(value, module_index=-1)
        with self.assertRaises(ValueError):
            bank(value[:, :-1], module_index=0)
        bad = value.clone()
        bad[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            bank(bad, module_index=0)

        core = CompactVectorizedFixedRoutingCore(self.source, self.initializations)
        working = torch.zeros(2, self.source.config.slots, self.source.config.width)
        context = torch.zeros_like(working)
        with self.assertRaises(ValueError):
            core(working, context, route_index=self.source.config.modules)
        with self.assertRaises(ValueError):
            core(working, context[:, :1], route_index=0)


if __name__ == "__main__":
    unittest.main()
