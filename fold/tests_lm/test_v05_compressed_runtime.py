from __future__ import annotations

import unittest
from unittest import mock

import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    DirectCompressedLinearBank,
    ModuleCompressionConfig,
    initialize_module_weights_from_core,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class V05CompressedRuntimeTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(19)
        self.config = LearnedCoreConfig(width=8, slots=3, modules=2, hidden_mult=2)
        self.source = HighPrecisionFixedRoutingCore(self.config)
        self.initializations = initialize_module_weights_from_core(
            self.source,
            up_config=ModuleCompressionConfig(
                block_rows=4,
                block_cols=4,
                codebook_count=2,
                entries_per_codebook=4,
                max_correction_entries=6,
                max_abs_correction=0.05,
            ),
            down_config=ModuleCompressionConfig(
                block_rows=4,
                block_cols=4,
                codebook_count=2,
                entries_per_codebook=4,
                max_correction_entries=6,
                max_abs_correction=0.05,
            ),
        )

    def test_dense_module_weights_initialize_up_and_down_compression(self):
        self.assertEqual(len(self.initializations.up.encoded_weights), self.config.modules)
        self.assertEqual(len(self.initializations.down.encoded_weights), self.config.modules)
        self.assertEqual(
            self.initializations.up.template.base.shape,
            tuple(self.source.module_set[0].up.weight.shape),
        )
        self.assertEqual(
            self.initializations.down.template.base.shape,
            tuple(self.source.module_set[0].down.weight.shape),
        )

    def test_direct_linear_bank_matches_materialized_weight(self):
        bank = DirectCompressedLinearBank(self.initializations.up)
        value = torch.randn(5, 7, self.config.width)
        for module_index in range(self.config.modules):
            direct = bank(value, module_index=module_index)
            weight = bank.materialized_weight(module_index)
            expected = F.linear(value, weight)
            torch.testing.assert_close(direct, expected, rtol=2e-5, atol=2e-6)

    def test_compressed_core_matches_materialized_reference(self):
        core = CompressedFixedRoutingCore(self.source, self.initializations)
        working = torch.randn(4, self.config.slots, self.config.width)
        context = torch.randn_like(working)
        for route_index in range(self.config.modules):
            direct = core(working, context, route_index=route_index)
            expected = core.materialized_reference(
                working, context, route_index=route_index
            )
            torch.testing.assert_close(direct, expected, rtol=3e-5, atol=3e-6)

    def test_direct_forward_does_not_materialize_dense_weights(self):
        core = CompressedFixedRoutingCore(self.source, self.initializations)
        working = torch.randn(2, self.config.slots, self.config.width)
        context = torch.randn_like(working)
        with mock.patch.object(
            core.up_bank,
            "materialized_weight",
            side_effect=AssertionError("up weight was materialized"),
        ), mock.patch.object(
            core.down_bank,
            "materialized_weight",
            side_effect=AssertionError("down weight was materialized"),
        ):
            output = core(working, context, route_index=0)
        self.assertEqual(tuple(output.shape), tuple(working.shape))
        self.assertTrue(torch.isfinite(output).all())

    def test_noncompressed_state_update_parts_are_copied_exactly(self):
        core = CompressedFixedRoutingCore(self.source, self.initializations)
        torch.testing.assert_close(core.gate_logits, self.source.gate_logits, rtol=0.0, atol=0.0)
        torch.testing.assert_close(
            core.shared.up.weight,
            self.source.shared.up.weight,
            rtol=0.0,
            atol=0.0,
        )
        for index in range(self.config.modules):
            torch.testing.assert_close(
                core.module_set[index].norm.weight,
                self.source.module_set[index].norm.weight,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                core.module_set[index].up_bias,
                self.source.module_set[index].up.bias,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                core.module_set[index].down_bias,
                self.source.module_set[index].down.bias,
                rtol=0.0,
                atol=0.0,
            )

    def test_invalid_configs_routes_shapes_and_values_are_rejected(self):
        with self.assertRaises(ValueError):
            ModuleCompressionConfig(block_rows=0, block_cols=4)
        with self.assertRaises(ValueError):
            ModuleCompressionConfig(block_rows=4, block_cols=4, max_correction_entries=-1)
        with self.assertRaises(TypeError):
            initialize_module_weights_from_core(
                object(),
                up_config=ModuleCompressionConfig(block_rows=4, block_cols=4),
                down_config=ModuleCompressionConfig(block_rows=4, block_cols=4),
            )

        core = CompressedFixedRoutingCore(self.source, self.initializations)
        working = torch.randn(2, self.config.slots, self.config.width)
        context = torch.randn_like(working)
        with self.assertRaises(ValueError):
            core(working, context, route_index=self.config.modules)
        with self.assertRaises(ValueError):
            core(working[:, :2], context[:, :2], route_index=0)
        bad = context.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            core(working, bad, route_index=0)


if __name__ == "__main__":
    unittest.main()
