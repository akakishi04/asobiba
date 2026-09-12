from __future__ import annotations

import unittest

from fold_lm.v05_benchmarks.gate_c_compact_linear_profile import (
    KINDS,
    ROLES,
    summarize,
)


class V05GateCCompactLinearProfileTests(unittest.TestCase):
    def test_roles_and_kinds_are_explicit(self):
        self.assertEqual(ROLES, ("up", "down"))
        self.assertEqual(KINDS, ("dense", "compact", "base_only"))

    def test_summary_reports_ratios_per_role(self):
        records = []
        for module_index in range(2):
            for role, dense, compact, base in (
                ("up", 1.0, 4.0, 1.5),
                ("down", 2.0, 6.0, 2.5),
            ):
                records.append(
                    {
                        "module_index": module_index,
                        "role": role,
                        "timings": {
                            "dense": {"mean_seconds": dense / 1000.0},
                            "compact": {"mean_seconds": compact / 1000.0},
                            "base_only": {"mean_seconds": base / 1000.0},
                        },
                    }
                )
        result = summarize(records)["roles"]
        self.assertAlmostEqual(result["up"]["compact_ratio_vs_dense"], 4.0)
        self.assertAlmostEqual(result["down"]["compact_ratio_vs_dense"], 3.0)
        self.assertAlmostEqual(result["up"]["compact_ratio_vs_base_only"], 4.0 / 1.5)
        self.assertEqual(result["up"]["modules"], 2)

    def test_summary_rejects_empty_records(self):
        with self.assertRaises(ValueError):
            summarize([])

    def test_summary_can_report_one_role_only(self):
        result = summarize(
            [
                {
                    "module_index": 0,
                    "role": "up",
                    "timings": {
                        "dense": {"mean_seconds": 0.001},
                        "compact": {"mean_seconds": 0.002},
                        "base_only": {"mean_seconds": 0.0015},
                    },
                }
            ]
        )["roles"]
        self.assertIn("up", result)
        self.assertNotIn("down", result)

    def test_microsecond_conversion_is_explicit(self):
        result = summarize(
            [
                {
                    "module_index": 0,
                    "role": "up",
                    "timings": {
                        "dense": {"mean_seconds": 2e-6},
                        "compact": {"mean_seconds": 5e-6},
                        "base_only": {"mean_seconds": 3e-6},
                    },
                }
            ]
        )["roles"]["up"]
        self.assertAlmostEqual(result["dense_mean_us"], 2.0)
        self.assertAlmostEqual(result["compact_mean_us"], 5.0)


if __name__ == "__main__":
    unittest.main()
