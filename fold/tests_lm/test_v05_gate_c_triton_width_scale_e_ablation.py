from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_triton_width_scale_e_ablation import (
    VARIANTS,
    order_for_round,
    summarize_records,
)


class V05GateCTritonWidthScaleEAblationTests(unittest.TestCase):
    def test_variants_are_explicit(self) -> None:
        self.assertEqual(VARIANTS, ("dense", "triton_full", "triton_no_e"))

    def test_order_rotates_every_round(self) -> None:
        self.assertEqual(order_for_round(0), ("dense", "triton_full", "triton_no_e"))
        self.assertEqual(order_for_round(1), ("triton_full", "triton_no_e", "dense"))
        self.assertEqual(order_for_round(2), ("triton_no_e", "dense", "triton_full"))
        self.assertEqual(order_for_round(3), order_for_round(0))

    def test_order_rejects_invalid_round(self) -> None:
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_width_dependent_e_cost(self) -> None:
        records = []
        for width, full, no_e, dense in ((32, 2.0, 1.8, 1.0), (64, 6.0, 3.0, 1.0)):
            for round_index in range(3):
                values = {
                    "dense": dense,
                    "triton_full": full,
                    "triton_no_e": no_e,
                }
                for variant in VARIANTS:
                    records.append({
                        "width": width,
                        "role": "up",
                        "module_index": 0,
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": values[variant],
                    })
        summary = summarize_records(records)["points"]
        self.assertAlmostEqual(summary["w32_up"]["full_to_no_e_slowdown_paired_median"], 2.0 / 1.8)
        self.assertAlmostEqual(summary["w64_up"]["full_to_no_e_slowdown_paired_median"], 2.0)
        self.assertAlmostEqual(summary["w64_up"]["triton_no_e_vs_dense_paired_median"], 3.0)

    def test_summary_requires_complete_rounds(self) -> None:
        records = [
            {
                "width": 32,
                "role": "up",
                "module_index": 0,
                "round": 0,
                "variant": "dense",
                "device_per_forward_ms": 1.0,
            }
        ]
        with self.assertRaises(ValueError):
            summarize_records(records)


if __name__ == "__main__":
    unittest.main()
