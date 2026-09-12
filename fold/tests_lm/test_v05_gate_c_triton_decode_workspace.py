from __future__ import annotations

import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.triton_decode_workspace_runtime import DecodedWorkspaceNoELinearBank
from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_decode_workspace import (
    DEFAULT_ROWS,
    VARIANTS,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonDecodeWorkspaceTests(unittest.TestCase):
    def test_defaults_and_variants_are_explicit(self):
        self.assertEqual(DEFAULT_ROWS, (1, 32, 216))
        self.assertEqual(
            VARIANTS,
            ("dense", "tiled_no_e", "decode_only", "decode_workspace"),
        )

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(
            order_for_round(1),
            ("tiled_no_e", "decode_only", "decode_workspace", "dense"),
        )
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_workspace_tradeoff(self):
        records = []
        for round_index, dense, tiled, decode, workspace in (
            (0, 1.0, 8.0, 2.0, 4.0),
            (1, 2.0, 12.0, 2.0, 6.0),
            (2, 4.0, 16.0, 4.0, 8.0),
        ):
            for variant, value in (
                ("dense", dense),
                ("tiled_no_e", tiled),
                ("decode_only", decode),
                ("decode_workspace", workspace),
            ):
                records.append({
                    "rows": 216,
                    "role": "up",
                    "round": round_index,
                    "variant": variant,
                    "device_per_forward_ms": value,
                })
        point = summarize_records(records)["points"]["r216_up"]
        self.assertEqual(point["tiled_vs_dense_paired_median"], 6.0)
        self.assertEqual(point["decode_workspace_vs_dense_paired_median"], 3.0)
        self.assertEqual(point["tiled_to_decode_workspace_speedup_paired_median"], 2.0)
        self.assertEqual(point["decode_fraction_of_workspace_paired_median"], 0.5)

    def test_summary_requires_complete_rounds(self):
        records = [
            {
                "rows": 1,
                "role": "down",
                "round": 0,
                "variant": "dense",
                "device_per_forward_ms": 1.0,
            }
        ]
        with self.assertRaises(ValueError):
            summarize_records(records)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_decoded_workspace_matches_materialized_no_e_weight_on_cuda(self):
        full = build_synthetic_initialization(32, 64, module_count=2, seed=20260912)
        no_e = without_correction(full)
        bank = DecodedWorkspaceNoELinearBank(no_e).cuda()
        tiled = TiledNoECompressedLinearBank(no_e).cuda()
        self.assertEqual(bank.workspace_bytes, 64 * 32 * 4)
        value = torch.randn(17, 32, device="cuda", dtype=torch.float32)

        for module_index, encoded in enumerate(no_e.encoded_weights):
            materialized = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device="cuda",
            )
            decoded = bank.decode(module_index=module_index)
            workspace_out = bank(value, module_index=module_index)
            tiled_out = tiled(value, module_index=module_index)
            dense_out = F.linear(value, materialized, None)
            torch.cuda.synchronize()
            torch.testing.assert_close(decoded, materialized, rtol=1e-5, atol=1e-6)
            torch.testing.assert_close(workspace_out, dense_out, rtol=1e-4, atol=1e-5)
            torch.testing.assert_close(tiled_out, dense_out, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
