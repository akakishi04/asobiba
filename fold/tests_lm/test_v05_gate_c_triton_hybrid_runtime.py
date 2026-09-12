from __future__ import annotations

import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.triton_hybrid_runtime import HybridNoECompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_hybrid_runtime import (
    DEFAULT_ROWS,
    VARIANTS,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonHybridRuntimeTests(unittest.TestCase):
    def test_defaults_and_variants_are_explicit(self):
        self.assertEqual(DEFAULT_ROWS, (1, 32, 216))
        self.assertEqual(VARIANTS, ("dense", "tiled_no_e", "hybrid_no_e"))

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), ("tiled_no_e", "hybrid_no_e", "dense"))
        self.assertEqual(order_for_round(2), ("hybrid_no_e", "dense", "tiled_no_e"))
        self.assertEqual(order_for_round(3), VARIANTS)
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_hybrid_speedup(self):
        records = []
        for round_index, dense, tiled, hybrid in (
            (0, 1.0, 8.0, 2.0),
            (1, 2.0, 12.0, 4.0),
            (2, 4.0, 32.0, 8.0),
        ):
            for variant, value in (
                ("dense", dense),
                ("tiled_no_e", tiled),
                ("hybrid_no_e", hybrid),
            ):
                records.append({
                    "rows": 216,
                    "role": "up",
                    "round": round_index,
                    "variant": variant,
                    "device_per_forward_ms": value,
                })
        point = summarize_records(records)["points"]["r216_up"]
        self.assertEqual(point["tiled_vs_dense_paired_median"], 8.0)
        self.assertEqual(point["hybrid_vs_dense_paired_median"], 2.0)
        self.assertEqual(point["tiled_to_hybrid_speedup_paired_median"], 4.0)

    def test_summary_requires_complete_rounds(self):
        records = [
            {
                "rows": 1,
                "role": "down",
                "round": 0,
                "variant": "dense",
                "device_per_forward_ms": 1.0,
            },
            {
                "rows": 1,
                "role": "down",
                "round": 0,
                "variant": "hybrid_no_e",
                "device_per_forward_ms": 2.0,
            },
        ]
        with self.assertRaises(ValueError):
            summarize_records(records)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_hybrid_no_e_matches_materialized_weight_on_cuda(self):
        full = build_synthetic_initialization(
            32,
            64,
            module_count=2,
            seed=20260912,
        )
        no_e = without_correction(full)
        bank = HybridNoECompressedLinearBank(no_e).cuda()
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)

        for module_index, encoded in enumerate(no_e.encoded_weights):
            materialized = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device="cuda",
            )
            dense = F.linear(value, materialized, None)
            hybrid = bank(value, module_index=module_index)
            torch.cuda.synchronize()
            torch.testing.assert_close(hybrid, dense, rtol=1e-4, atol=1e-5)

    def test_hybrid_rejects_nonzero_correction(self):
        full = build_synthetic_initialization(
            32,
            64,
            module_count=2,
            correction_density=0.03125,
            seed=20260912,
        )
        if torch.cuda.is_available():
            with self.assertRaises(ValueError):
                HybridNoECompressedLinearBank(full)


if __name__ == "__main__":
    unittest.main()
