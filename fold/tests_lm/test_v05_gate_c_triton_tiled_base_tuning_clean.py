from __future__ import annotations

import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.triton_tiled_tuning_runtime import TiledBaseKernelConfig
from fold_lm.v05_benchmarks.gate_c_triton_tiled_base_tuning_clean import (
    CONFIGS,
    VARIANTS,
    StructuralValidationTunedTiledBaseOnlyLinearBank,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonTiledBaseTuningCleanTests(unittest.TestCase):
    def test_configs_and_variants_match_bounded_c30_sweep(self):
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
        self.assertEqual(VARIANTS, ("dense", *CONFIGS.keys()))
        self.assertTrue(all(isinstance(cfg, TiledBaseKernelConfig) for cfg in CONFIGS.values()))

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), VARIANTS[1:] + VARIANTS[:1])
        self.assertEqual(order_for_round(len(VARIANTS)), VARIANTS)
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_device_and_wall_paired_ratios(self):
        records = []
        for role in ("up", "down"):
            for round_index in range(2):
                dense = 1.0 + round_index
                for variant in VARIANTS:
                    multiplier = 1.0 if variant == "dense" else 2.0
                    records.append({
                        "role": role,
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": dense * multiplier,
                        "wall_per_forward_ms": dense * multiplier * 1.5,
                    })
        gaps = {f"{role}:{variant}": 0.0 for role in ("up", "down") for variant in CONFIGS}
        summary = summarize_records(records, gaps)
        point = summary["roles"]["up"]["variants"]["ieee_32x32x32"]
        self.assertEqual(point["vs_dense_device_paired_median"], 2.0)
        self.assertEqual(point["vs_dense_wall_paired_median"], 2.0)

    def test_summary_requires_complete_rounds(self):
        records = [{
            "role": "up",
            "round": 0,
            "variant": "dense",
            "device_per_forward_ms": 1.0,
            "wall_per_forward_ms": 1.0,
        }]
        with self.assertRaises(ValueError):
            summarize_records(records, {})

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_structural_validation_path_matches_ieee_dense_and_does_not_sync(self):
        init = build_synthetic_initialization(32, 64, module_count=2, seed=20260913)
        cfg = CONFIGS["ieee_32x32x32"]
        bank = StructuralValidationTunedTiledBaseOnlyLinearBank(init, cfg).cuda().eval()
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)

        old_mode = torch.cuda.get_sync_debug_mode()
        try:
            torch.cuda.set_sync_debug_mode("error")
            bank._validate(value, 0)
            output = bank(value, module_index=0)
        finally:
            torch.cuda.set_sync_debug_mode(old_mode)
        torch.cuda.synchronize()

        dense = F.linear(value, bank.base, None)
        torch.testing.assert_close(output, dense, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
