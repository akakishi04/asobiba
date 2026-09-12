from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    DEFAULT_WIDTHS,
    ROLES,
    VARIANTS,
    build_synthetic_initialization,
    order_for_round,
    role_shape,
    summarize_records,
)


class V05GateCTritonWidthScaleTests(unittest.TestCase):
    def test_defaults_and_roles_are_explicit(self) -> None:
        self.assertEqual(DEFAULT_WIDTHS, (32, 64, 128, 256))
        self.assertEqual(ROLES, ("up", "down"))
        self.assertEqual(VARIANTS, ("dense", "triton"))

    def test_role_shape_matches_two_x_hidden_contract(self) -> None:
        self.assertEqual(role_shape(32, "up"), (32, 64))
        self.assertEqual(role_shape(32, "down"), (64, 32))
        with self.assertRaises(ValueError):
            role_shape(0, "up")
        with self.assertRaises(ValueError):
            role_shape(32, "other")

    def test_order_rotates_every_round(self) -> None:
        self.assertEqual(order_for_round(0), ("dense", "triton"))
        self.assertEqual(order_for_round(1), ("triton", "dense"))
        self.assertEqual(order_for_round(2), ("dense", "triton"))
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_synthetic_initialization_preserves_current_structure(self) -> None:
        init = build_synthetic_initialization(32, 64)
        self.assertEqual(len(init.encoded_weights), 2)
        self.assertEqual(init.template.block_rows, 2)
        self.assertEqual(init.template.block_cols, 2)
        self.assertEqual(init.template.codebook_count, 3)
        self.assertEqual(init.template.entries_per_codebook, 8)
        self.assertAlmostEqual(init.metrics[0].correction_density, 0.03125)
        self.assertGreater(init.accounting.dense_float32_bytes, 0)
        self.assertGreater(init.accounting.estimated_encoded_payload_bytes, 0)

    def test_summary_reports_paired_ratio_per_width_role(self) -> None:
        records = []
        for round_index, values in enumerate(((1.0, 1.5), (2.0, 2.0), (1.0, 1.25))):
            dense, triton = values
            records.extend(
                [
                    {
                        "width": 32,
                        "role": "up",
                        "module_index": 0,
                        "round": round_index,
                        "variant": "dense",
                        "device_per_forward_ms": dense,
                    },
                    {
                        "width": 32,
                        "role": "up",
                        "module_index": 0,
                        "round": round_index,
                        "variant": "triton",
                        "device_per_forward_ms": triton,
                    },
                ]
            )
        summary = summarize_records(records)
        point = summary["points"]["w32_up"]
        self.assertEqual(point["width"], 32)
        self.assertEqual(point["role"], "up")
        self.assertEqual(point["rounds"], 3)
        self.assertAlmostEqual(point["triton_vs_dense_paired_median"], 1.25)


if __name__ == "__main__":
    unittest.main()
