from __future__ import annotations

import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.triton_runtime import triton_runtime_available
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_validation_overhead import (
    DEFAULT_ROWS,
    VARIANTS,
    StructuralValidationHybridNoECompressedLinearBank,
    StructuralValidationTiledNoECompressedLinearBank,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonValidationOverheadTests(unittest.TestCase):
    def test_defaults_and_variants_are_explicit(self):
        self.assertEqual(DEFAULT_ROWS, (1, 216))
        self.assertEqual(
            VARIANTS,
            (
                "dense",
                "tiled_full_validation",
                "tiled_structural_validation",
                "hybrid_full_validation",
                "hybrid_structural_validation",
            ),
        )

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), VARIANTS[1:] + VARIANTS[:1])
        self.assertEqual(order_for_round(5), VARIANTS)
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_keeps_both_modules_and_reports_paired_ratios(self):
        records = []
        values_by_module = {
            0: {
                "dense": 1.0,
                "tiled_full_validation": 10.0,
                "tiled_structural_validation": 2.0,
                "hybrid_full_validation": 30.0,
                "hybrid_structural_validation": 3.0,
            },
            1: {
                "dense": 1.0,
                "tiled_full_validation": 20.0,
                "tiled_structural_validation": 4.0,
                "hybrid_full_validation": 50.0,
                "hybrid_structural_validation": 5.0,
            },
        }
        for module_index, variants in values_by_module.items():
            for variant, value in variants.items():
                records.append({
                    "rows": 216,
                    "role": "up",
                    "module_index": module_index,
                    "round": 0,
                    "variant": variant,
                    "device_per_forward_ms": value,
                    "wall_per_forward_ms": value,
                })

        point = summarize_records(records)["points"]["r216_up"]
        self.assertEqual(point["paired_samples"], 2)
        self.assertEqual(
            point["variants"]["tiled_full_validation"]["device_ms"],
            15.0,
        )
        ratios = point["paired_ratios"]
        self.assertEqual(ratios["tiled_full_vs_dense_device"], 15.0)
        self.assertEqual(ratios["tiled_structural_vs_dense_device"], 3.0)
        self.assertEqual(ratios["tiled_full_to_structural_device"], 5.0)
        self.assertEqual(ratios["hybrid_full_vs_dense_device"], 40.0)
        self.assertEqual(ratios["hybrid_structural_vs_dense_device"], 4.0)
        self.assertEqual(ratios["hybrid_full_to_structural_device"], 10.0)
        self.assertEqual(ratios["hybrid_full_to_structural_wall"], 10.0)

    def test_summary_requires_complete_module_round(self):
        records = [
            {
                "rows": 1,
                "role": "down",
                "module_index": 0,
                "round": 0,
                "variant": "dense",
                "device_per_forward_ms": 1.0,
                "wall_per_forward_ms": 1.0,
            }
        ]
        with self.assertRaises(ValueError):
            summarize_records(records)

    @unittest.skipUnless(
        torch.cuda.is_available() and triton_runtime_available(),
        "CUDA + Triton required",
    )
    def test_structural_validation_paths_match_dense_and_do_not_sync(self):
        full = build_synthetic_initialization(
            32,
            64,
            module_count=2,
            seed=20260913,
        )
        no_e = without_correction(full)
        tiled = StructuralValidationTiledNoECompressedLinearBank(no_e).cuda()
        hybrid = StructuralValidationHybridNoECompressedLinearBank(no_e).cuda()
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)
        materialized = torch.tensor(
            np.array(no_e.encoded_weights[0].materialize(), copy=True),
            dtype=torch.float32,
            device="cuda",
        )
        dense = F.linear(value, materialized, None)

        old_mode = torch.cuda.get_sync_debug_mode()
        try:
            torch.cuda.set_sync_debug_mode("error")
            tiled_out = tiled(value, module_index=0)
            hybrid_out = hybrid(value, module_index=0)
        finally:
            torch.cuda.set_sync_debug_mode(old_mode)
        torch.cuda.synchronize()

        torch.testing.assert_close(tiled_out, dense, rtol=1e-4, atol=1e-5)
        torch.testing.assert_close(hybrid_out, dense, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
