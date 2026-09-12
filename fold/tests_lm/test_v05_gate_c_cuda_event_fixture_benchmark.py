import unittest

from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import (
    VARIANTS,
    order_for_round,
    summarize_rounds,
)


class V05GateCCudaEventFixtureBenchmarkTests(unittest.TestCase):
    def _records(self):
        rows = []
        device = {
            0: {"dense": 4.0, "compact": 10.0, "triton": 6.0},
            1: {"dense": 5.0, "compact": 12.0, "triton": 7.5},
            2: {"dense": 6.0, "compact": 14.0, "triton": 9.0},
        }
        wall = {
            0: {"dense": 4.5, "compact": 10.5, "triton": 6.5},
            1: {"dense": 5.5, "compact": 12.5, "triton": 8.0},
            2: {"dense": 6.5, "compact": 14.5, "triton": 9.5},
        }
        for round_index in range(3):
            order = order_for_round(round_index)
            for variant in order:
                rows.append(
                    {
                        "round": round_index,
                        "order": list(order),
                        "variant": variant,
                        "device_per_forward_ms": device[round_index][variant],
                        "wall_per_forward_ms": wall[round_index][variant],
                    }
                )
        return rows

    def test_variants_are_explicit_and_complete(self):
        self.assertEqual(VARIANTS, ("dense", "compact", "triton"))

    def test_order_rotates_every_round(self):
        self.assertEqual(order_for_round(0), ("dense", "compact", "triton"))
        self.assertEqual(order_for_round(1), ("compact", "triton", "dense"))
        self.assertEqual(order_for_round(2), ("triton", "dense", "compact"))
        self.assertEqual(order_for_round(3), order_for_round(0))

    def test_order_rejects_invalid_round_index(self):
        with self.assertRaises(ValueError):
            order_for_round(-1)
        with self.assertRaises(ValueError):
            order_for_round(1.5)

    def test_summary_reports_paired_median_ratios(self):
        summary = summarize_rounds(
            self._records(),
            {"dense": 1.0, "compact": 1.0, "triton": 1.0},
        )
        self.assertEqual(summary["rounds"], 3)
        self.assertEqual(summary["variants"]["dense"]["device_median_ms"], 5.0)
        self.assertAlmostEqual(
            summary["paired_ratios"]["triton_vs_dense_device_median"],
            1.5,
        )
        self.assertAlmostEqual(
            summary["paired_ratios"]["compact_to_triton_device_speedup_median"],
            12.0 / 7.5,
        )

    def test_summary_requires_complete_rounds(self):
        records = self._records()
        records.pop()
        with self.assertRaises(ValueError):
            summarize_rounds(
                records,
                {"dense": 1.0, "compact": 1.0, "triton": 1.0},
            )


if __name__ == "__main__":
    unittest.main()
