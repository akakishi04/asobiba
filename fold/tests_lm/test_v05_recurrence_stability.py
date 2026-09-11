from __future__ import annotations

import unittest
from unittest import mock

import torch

from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    ModuleCompressionConfig,
    initialize_module_weights_from_core,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05.recurrence_stability import (
    DEFAULT_CHECKPOINTS,
    RecurrencePerturbation,
    RecurrenceStabilityReport,
    measure_recurrence_stability,
)


class V05RecurrenceStabilityTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(23)
        self.config = LearnedCoreConfig(width=4, slots=3, modules=2, hidden_mult=2)
        self.source = HighPrecisionFixedRoutingCore(self.config)
        hidden = self.config.width * self.config.hidden_mult
        exact = initialize_module_weights_from_core(
            self.source,
            up_config=ModuleCompressionConfig(
                block_rows=hidden,
                block_cols=self.config.width,
                codebook_count=1,
                entries_per_codebook=2,
            ),
            down_config=ModuleCompressionConfig(
                block_rows=self.config.width,
                block_cols=hidden,
                codebook_count=1,
                entries_per_codebook=2,
            ),
        )
        self.compressed = CompressedFixedRoutingCore(self.source, exact)
        generator = torch.Generator(device="cpu").manual_seed(31)
        self.working = torch.randn(5, 3, 4, generator=generator) * 0.2
        self.context = torch.randn(5, 3, 4, generator=generator) * 0.15

    def test_default_checkpoints_are_one_two_four_eight(self):
        self.assertEqual(DEFAULT_CHECKPOINTS, (1, 2, 4, 8))
        report = measure_recurrence_stability(
            self.source,
            self.compressed,
            self.working,
            self.context,
            route_index=0,
        )
        self.assertEqual(report.checkpoints, DEFAULT_CHECKPOINTS)
        self.assertEqual(tuple(item.steps for item in report.measurements), DEFAULT_CHECKPOINTS)

    def test_exact_compression_stays_numerically_aligned_through_eight_steps(self):
        report = measure_recurrence_stability(
            self.source,
            self.compressed,
            self.working,
            self.context,
            route_index=1,
        )
        for item in report.measurements:
            self.assertLess(item.rmse, 1e-6)
            self.assertLess(item.max_abs_error, 5e-6)
            self.assertLess(item.relative_l2_error, 1e-6)
            self.assertTrue(torch.isfinite(torch.tensor(item.dense_state_rms)))
            self.assertTrue(torch.isfinite(torch.tensor(item.compressed_state_rms)))

    def test_perturbation_is_detected_and_final_metrics_match_manual_recurrence(self):
        perturbed = CompressedFixedRoutingCore(
            self.source,
            initialize_module_weights_from_core(
                self.source,
                up_config=ModuleCompressionConfig(
                    block_rows=8,
                    block_cols=4,
                    codebook_count=1,
                    entries_per_codebook=2,
                ),
                down_config=ModuleCompressionConfig(
                    block_rows=4,
                    block_cols=8,
                    codebook_count=1,
                    entries_per_codebook=2,
                ),
            ),
        )
        with torch.no_grad():
            perturbed.up_bank.base.add_(0.04)

        report = measure_recurrence_stability(
            self.source,
            perturbed,
            self.working,
            self.context,
            route_index=0,
        )
        self.assertGreater(report.measurements[0].rmse, 0.0)
        self.assertGreater(report.final.rmse, 0.0)

        dense = self.working.clone()
        compressed = self.working.clone()
        with torch.inference_mode():
            for _ in range(8):
                dense = self.source(dense, self.context, route_index=0)
                compressed = perturbed(compressed, self.context, route_index=0)
        difference = compressed - dense
        manual_rmse = float(torch.sqrt(torch.mean(difference.double() ** 2)).item())
        manual_max = float(difference.abs().max().item())
        self.assertAlmostEqual(report.final.rmse, manual_rmse, places=10)
        self.assertAlmostEqual(report.final.max_abs_error, manual_max, places=7)

    def test_measurement_is_deterministic_and_does_not_materialize_weights(self):
        with mock.patch.object(
            self.compressed.up_bank,
            "materialized_weight",
            side_effect=AssertionError("must not materialize up weight"),
        ), mock.patch.object(
            self.compressed.down_bank,
            "materialized_weight",
            side_effect=AssertionError("must not materialize down weight"),
        ):
            first = measure_recurrence_stability(
                self.source,
                self.compressed,
                self.working,
                self.context,
                route_index=0,
            )
            second = measure_recurrence_stability(
                self.source,
                self.compressed,
                self.working,
                self.context,
                route_index=0,
            )
        self.assertEqual(first, second)

    def test_custom_checkpoints_and_report_helpers_are_consistent(self):
        report = measure_recurrence_stability(
            self.source,
            self.compressed,
            self.working,
            self.context,
            route_index=0,
            checkpoints=(1, 3, 5),
        )
        self.assertEqual(report.checkpoints, (1, 3, 5))
        self.assertEqual(report.final.steps, 5)
        self.assertEqual(
            report.max_amplification,
            max(item.amplification_vs_step1 for item in report.measurements),
        )

    def test_invalid_reports_inputs_routes_and_checkpoints_are_rejected(self):
        with self.assertRaises(ValueError):
            RecurrencePerturbation(
                steps=0,
                rmse=0.0,
                max_abs_error=0.0,
                relative_l2_error=0.0,
                dense_state_rms=0.0,
                compressed_state_rms=0.0,
                amplification_vs_step1=0.0,
            )
        with self.assertRaises(ValueError):
            RecurrenceStabilityReport(checkpoints=(2, 1), measurements=())
        with self.assertRaises(ValueError):
            measure_recurrence_stability(
                self.source,
                self.compressed,
                self.working,
                self.context,
                route_index=2,
            )
        with self.assertRaises(ValueError):
            measure_recurrence_stability(
                self.source,
                self.compressed,
                self.working,
                self.context[:, :2],
                route_index=0,
            )
        with self.assertRaises(ValueError):
            measure_recurrence_stability(
                self.source,
                self.compressed,
                self.working,
                self.context,
                route_index=0,
                checkpoints=(1, 4, 2),
            )
        bad = self.working.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            measure_recurrence_stability(
                self.source,
                self.compressed,
                bad,
                self.context,
                route_index=0,
            )


if __name__ == "__main__":
    unittest.main()
