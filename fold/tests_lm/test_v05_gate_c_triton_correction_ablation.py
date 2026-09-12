import unittest

from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import (
    ROLES,
    VARIANTS,
    order_for_round,
    summarize_records,
)


class V05GateCTritonCorrectionAblationTests(unittest.TestCase):
    def test_variants_and_roles_are_explicit(self):
        self.assertEqual(ROLES, ("up", "down"))
        self.assertEqual(VARIANTS, ("dense", "triton_full", "triton_no_e"))

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), VARIANTS)
        self.assertEqual(order_for_round(1), ("triton_full", "triton_no_e", "dense"))
        self.assertEqual(order_for_round(2), ("triton_no_e", "dense", "triton_full"))
        self.assertEqual(order_for_round(3), VARIANTS)

    def test_order_rejects_invalid_round(self):
        with self.assertRaises(ValueError):
            order_for_round(-1)

    def test_summary_reports_correction_cost_ratio(self):
        records = []
        for round_index, dense, full, no_e in (
            (0, 1.0, 2.0, 1.5),
            (1, 2.0, 4.0, 3.0),
        ):
            for variant, value in (
                ("dense", dense),
                ("triton_full", full),
                ("triton_no_e", no_e),
            ):
                records.append(
                    {
                        "role": "up",
                        "module_index": 0,
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": value,
                    }
                )
        summary = summarize_records(records)["roles"]["up"]
        self.assertAlmostEqual(summary["triton_full_vs_dense_paired_median"], 2.0)
        self.assertAlmostEqual(summary["triton_no_e_vs_dense_paired_median"], 1.5)
        self.assertAlmostEqual(summary["full_to_no_e_slowdown_paired_median"], 4.0 / 3.0)

    def test_summary_requires_complete_module_rounds(self):
        records = [
            {
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
