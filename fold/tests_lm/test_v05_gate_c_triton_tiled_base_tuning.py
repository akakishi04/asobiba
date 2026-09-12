from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.triton_tiled_tuning_runtime import (
    TiledBaseKernelConfig,
    TunedTiledBaseOnlyLinearBank,
)
from fold_lm.v05_benchmarks.gate_c_triton_tiled_base_tuning import (
    CONFIGS,
    VARIANTS,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonTiledBaseTuningTests(unittest.TestCase):
    def test_configs_and_variants_are_bounded_and_explicit(self):
        self.assertEqual(
            tuple(CONFIGS),
            (
                "ieee_16x16x32",
                "ieee_32x32x32",
                "tf32x3_32x32x32",
                "tf32_32x32x32",
                "tf32_32x64x32",
            ),
        )
        self.assertEqual(VARIANTS[0], "dense")
        self.assertEqual(len(VARIANTS), 6)

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            TiledBaseKernelConfig(24, 16, 32, 4, "ieee")
        with self.assertRaises(ValueError):
            TiledBaseKernelConfig(16, 16, 32, 4, "bad")

    def test_order_rotates(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), VARIANTS[1:] + VARIANTS[:1])
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_paired_ratios(self):
        records = []
        output_gaps = {}
        for role in ("up", "down"):
            for variant in CONFIGS:
                output_gaps[f"{role}:{variant}"] = 0.01
            for round_index, dense in ((0, 1.0), (1, 2.0), (2, 4.0)):
                records.append({
                    "role": role,
                    "round": round_index,
                    "variant": "dense",
                    "device_per_forward_ms": dense,
                })
                for offset, variant in enumerate(CONFIGS, start=2):
                    records.append({
                        "role": role,
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": dense * offset,
                    })
        summary = summarize_records(records, output_gaps)
        self.assertEqual(summary["roles"]["up"]["variants"]["ieee_16x16x32"]["vs_dense_paired_median"], 2.0)
        self.assertEqual(summary["roles"]["down"]["variants"]["tf32_32x64x32"]["vs_dense_paired_median"], 6.0)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_ieee_and_tf32_configs_execute_on_cuda(self):
        init = build_synthetic_initialization(32, 64, module_count=2, seed=20260912)
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)
        dense = F.linear(value, torch.tensor(init.template.base, dtype=torch.float32, device="cuda"), None)

        ieee = TunedTiledBaseOnlyLinearBank(init, CONFIGS["ieee_32x32x32"]).cuda()
        tf32 = TunedTiledBaseOnlyLinearBank(init, CONFIGS["tf32_32x32x32"]).cuda()
        out_ieee = ieee(value, module_index=0)
        out_tf32 = tf32(value, module_index=0)
        torch.cuda.synchronize()

        torch.testing.assert_close(out_ieee, dense, rtol=1e-4, atol=1e-5)
        self.assertTrue(torch.isfinite(out_tf32).all())
        self.assertLess(float((out_tf32 - dense).abs().max().item()), 0.05)


if __name__ == "__main__":
    unittest.main()
