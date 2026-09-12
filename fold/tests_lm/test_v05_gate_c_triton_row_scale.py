from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_triton_row_scale import (
    DEFAULT_ROWS,
    DEFAULT_WIDTH,
    VARIANTS,
    order_for_round,
    summarize_records,
)


class V05GateCTritonRowScaleTests(unittest.TestCase):
    def test_defaults_and_variants_are_explicit(self) -> None:
        self.assertEqual(DEFAULT_WIDTH, 256)
        self.assertEqual(DEFAULT_ROWS, (1, 8, 32, 216))
        self.assertEqual(VARIANTS, ("dense", "triton_no_e"))

    def test_order_rotates_every_round(self) -> None:
        self.assertEqual(order_for_round(0), ("dense", "triton_no_e"))
        self.assertEqual(order_for_round(1), ("triton_no_e", "dense"))
        self.assertEqual(order_for_round(2), ("dense", "triton_no_e"))

    def test_order_rejects_invalid_round(self) -> None:
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_row_dependent_ratio(self) -> None:
        records = []
        for rows_count, dense, triton in ((1, 1.0, 2.0), (8, 1.0, 4.0)):
            for round_index in range(2):
                records.extend(
                    [
                        {
                            "rows": rows_count,
                            "role": "up",
                            "round": round_index,
                            "variant": "dense",
                            "device_per_forward_ms": dense,
                        },
                        {
                            "rows": rows_count,
                            "role": "up",
                            "round": round_index,
                            "variant": "triton_no_e",
                            "device_per_forward_ms": triton,
                        },
                    ]
                )
        summary = summarize_records(records)
        self.assertEqual(summary["points"]["r1_up"]["triton_no_e_vs_dense_paired_median"], 2.0)
        self.assertEqual(summary["points"]["r8_up"]["triton_no_e_vs_dense_paired_median"], 4.0)

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


if __name__ == "__main__":
    unittest.main()
