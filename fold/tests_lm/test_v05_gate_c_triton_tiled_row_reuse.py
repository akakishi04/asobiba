from __future__ import annotations

import unittest

import torch

from fold_lm.v05.triton_tiled_runtime import (
    TiledNoECompressedLinearBank,
    triton_runtime_available,
)
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_tiled_row_reuse import (
    VARIANTS,
    order_for_round,
    summarize_records,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


class V05GateCTritonTiledRowReuseTests(unittest.TestCase):
    def test_variants_are_explicit(self) -> None:
        self.assertEqual(VARIANTS, ("dense", "rowwise_no_e", "tiled_no_e"))

    def test_order_rotates_every_round(self) -> None:
        self.assertEqual(order_for_round(0), ("dense", "rowwise_no_e", "tiled_no_e"))
        self.assertEqual(order_for_round(1), ("rowwise_no_e", "tiled_no_e", "dense"))
        self.assertEqual(order_for_round(2), ("tiled_no_e", "dense", "rowwise_no_e"))

    def test_summary_reports_tiled_speedup(self) -> None:
        records = []
        values = {
            0: {"dense": 1.0, "rowwise_no_e": 10.0, "tiled_no_e": 2.0},
            1: {"dense": 2.0, "rowwise_no_e": 12.0, "tiled_no_e": 3.0},
            2: {"dense": 1.5, "rowwise_no_e": 9.0, "tiled_no_e": 3.0},
        }
        for round_index, group in values.items():
            for variant, timing in group.items():
                records.append(
                    {
                        "rows": 216,
                        "role": "up",
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": timing,
                    }
                )
        summary = summarize_records(records)
        point = summary["points"]["r216_up"]
        self.assertEqual(point["rowwise_to_tiled_speedup_paired_median"], 4.0)
        self.assertEqual(point["tiled_vs_dense_paired_median"], 2.0)

    def test_summary_requires_complete_rounds(self) -> None:
        with self.assertRaises(ValueError):
            summarize_records(
                [
                    {
                        "rows": 1,
                        "role": "up",
                        "round": 0,
                        "variant": "dense",
                        "device_per_forward_ms": 1.0,
                    }
                ]
            )

    @unittest.skipUnless(torch.cuda.is_available() and triton_runtime_available(), "CUDA Triton required")
    def test_tiled_no_e_matches_materialized_weight_on_cuda(self) -> None:
        full = build_synthetic_initialization(32, 64)
        no_e = without_correction(full)
        bank = TiledNoECompressedLinearBank(no_e).cuda()
        value = torch.randn(8, 32, device="cuda", dtype=torch.float32)
        materialized = torch.tensor(
            no_e.encoded_weights[0].materialize(),
            device="cuda",
            dtype=torch.float32,
        )
        expected = torch.nn.functional.linear(value, materialized, None)
        actual = bank(value, module_index=0)
        torch.cuda.synchronize()
        torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
