from __future__ import annotations

import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.triton_tiled_ablation_runtime import TiledBaseOnlyLinearBank
from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05.benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05.benchmarks.gate_c_triton_tiled_decode_ablation import (
    DEFAULT_ROWS,
    VARIANTS,
    order_for_round,
    summarize_records,
)
from fold_lm.v05.benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonTiledDecodeAblationTests(unittest.TestCase):
    def test_defaults_and_variants_are_explicit(self):
        self.assertEqual(DEFAULT_ROWS, (1, 32, 216))
        self.assertEqual(VARIANTS, ("dense_base", "tiled_base", "tiled_codebook"))

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), ("tiled_base", "tiled_codebook", "dense_base"))
        self.assertEqual(order_for_round(2), ("tiled_codebook", "dense_base", "tiled_base"))
        self.assertEqual(order_for_round(3), VARIANTS)
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_decode_slowdown(self):
        records = []
        for round_index, dense, base, codebook in (
            (0, 1.0, 2.0, 8.0),
            (1, 2.0, 4.0, 12.0),
            (2, 4.0, 8.0, 32.0),
        ):
            for variant, value in (
                ("dense_base", dense),
                ("tiled_base", base),
                ("tiled_codebook", codebook),
            ):
                records.append({
                    "rows": 216,
                    "role": "up",
                    "round": round_index,
                    "variant": variant,
                    "device_per_forward_ms": value,
                })
        point = summarize_records(records)["points"]["r216_up"]
        self.assertEqual(point["tiled_base_vs_dense_paired_median"], 2.0)
        self.assertEqual(point["codebook_to_base_slowdown_paired_median"], 4.0)
        self.assertEqual(point["tiled_codebook_vs_dense_paired_median"], 8.0)

    def test_summary_requires_complete_rounds(self):
        records = [
            {
                "rows": 1,
                "role": "down",
                "round": 0,
                "variant": "dense_base",
                "device_per_forward_ms": 1.0,
            },
            {
                "rows": 1,
                "role": "down",
                "round": 0,
                "variant": "tiled_base",
                "device_per_forward_ms": 2.0,
            },
        ]
        with self.assertRaises(ValueError):
            summarize_records(records)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_tiled_base_and_codebook_match_dense_references_on_cuda(self):
        full = build_synthetic_initialization(
            32,
            64,
            module_count=2,
            seed=20260912,
        )
        no_e = without_correction(full)
        base_bank = TiledBaseOnlyLinearBank(no_e).cuda()
        codebook_bank = TiledNoECompressedLinearBank(no_e).cuda()
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)

        for module_index, encoded in enumerate(no_e.encoded_weights):
            dense_base = F.linear(value, base_bank.base, None)
            tiled_base = base_bank(value, module_index=module_index)
            materialized = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device="cuda",
            )
            dense_codebook = F.linear(value, materialized, None)
            tiled_codebook = codebook_bank(value, module_index=module_index)
            torch.cuda.synchronize()
            torch.testing.assert_close(tiled_base, dense_base, rtol=1e-4, atol=1e-5)
            torch.testing.assert_close(tiled_codebook, dense_codebook, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
