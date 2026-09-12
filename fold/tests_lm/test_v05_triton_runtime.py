from __future__ import annotations

import unittest

import torch

from fold_lm.v05.compact_runtime import CompactVectorizedLinearBank
from fold_lm.v05.compressed_runtime import (
    ModuleCompressionConfig,
    initialize_module_weights_from_core,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05.triton_runtime import (
    TritonCompressedFixedRoutingCore,
    TritonCompressedLinearBank,
    triton_runtime_available,
)


class V05TritonRuntimeTests(unittest.TestCase):
    def setUp(self):
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

    def test_availability_flag_is_boolean(self):
        self.assertIsInstance(triton_runtime_available(), bool)

    def test_triton_bank_requires_cuda_activation(self):
        if not triton_runtime_available():
            self.skipTest("Triton unavailable")
        bank = TritonCompressedLinearBank(self.initializations.up)
        value = torch.randn(3, 2, bank.input_width)
        with self.assertRaises(RuntimeError):
            bank(value, module_index=0)

    def test_triton_bank_preserves_compact_resident_buffers(self):
        if not triton_runtime_available():
            self.skipTest("Triton unavailable")
        compact = CompactVectorizedLinearBank(self.initializations.up)
        triton_bank = TritonCompressedLinearBank(self.initializations.up)
        self.assertEqual(triton_bank.resident_tensor_bytes, compact.resident_tensor_bytes)
        self.assertEqual(triton_bank.codes.dtype, torch.uint8)
        for module_index in range(triton_bank.module_count):
            indices = getattr(triton_bank, f"correction_indices_{module_index}")
            self.assertEqual(indices.dtype, torch.int32)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA unavailable")
    def test_triton_bank_matches_compact_reference_on_cuda(self):
        if not triton_runtime_available():
            self.skipTest("Triton unavailable")
        compact = CompactVectorizedLinearBank(self.initializations.up).cuda()
        triton_bank = TritonCompressedLinearBank(self.initializations.up).cuda()
        value = torch.randn(5, 3, triton_bank.input_width, device="cuda")
        for module_index in range(triton_bank.module_count):
            expected = compact(value, module_index=module_index)
            actual = triton_bank(value, module_index=module_index)
            torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA unavailable")
    def test_triton_core_matches_compact_weighted_reference_on_cuda(self):
        if not triton_runtime_available():
            self.skipTest("Triton unavailable")
        from fold_lm.v05.compact_runtime import CompactVectorizedFixedRoutingCore

        source = self.source.cuda()
        compact = CompactVectorizedFixedRoutingCore(source, self.initializations).cuda()
        triton_core = TritonCompressedFixedRoutingCore(source, self.initializations).cuda()
        working = torch.randn(4, source.config.slots, source.config.width, device="cuda")
        context = torch.randn_like(working)
        for route_index in range(source.config.modules):
            expected = compact(working, context, route_index=route_index)
            actual = triton_core(working, context, route_index=route_index)
            torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
