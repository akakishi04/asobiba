from __future__ import annotations

import unittest

import torch

from fold_lm.v05_benchmarks.gate_b_baseline_comparison import (
    ARCHITECTURES,
    TASKS,
    CoreComparisonStats,
    _build_composition,
    _build_condition,
    _build_language,
    core_stats_for,
    run_benchmark,
    summarize,
)


class V05GateBBaselineComparisonTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.device = torch.device("cpu")
        self.seed = 20260911

    def test_registered_comparison_scope_is_explicit(self):
        self.assertEqual(ARCHITECTURES, ("v5b", "dense", "shared"))
        self.assertEqual(TASKS, ("condition", "composition", "language"))

    def test_condition_split_and_noncore_initialization_match_across_architectures(self):
        built = {
            architecture: _build_condition(self.seed, architecture, self.device)
            for architecture in ARCHITECTURES
        }
        reference = built["v5b"]
        for architecture in ("dense", "shared"):
            current = built[architecture]
            torch.testing.assert_close(reference[2].initial_values, current[2].initial_values)
            torch.testing.assert_close(reference[2].operations, current[2].operations)
            torch.testing.assert_close(reference[2].candidates, current[2].candidates)
            torch.testing.assert_close(reference[3].initial_values, current[3].initial_values)
            torch.testing.assert_close(reference[3].operations, current[3].operations)
            torch.testing.assert_close(reference[3].candidates, current[3].candidates)
            torch.testing.assert_close(
                reference[1].state_embedding.weight,
                current[1].state_embedding.weight,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                reference[1].event_embedding.weight,
                current[1].event_embedding.weight,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                reference[1].decoder.weight,
                current[1].decoder.weight,
                rtol=0.0,
                atol=0.0,
            )

    def test_language_split_and_noncore_initialization_match_across_architectures(self):
        built = {
            architecture: _build_language(self.seed, architecture, self.device)
            for architecture in ARCHITECTURES
        }
        reference = built["v5b"]
        for architecture in ("dense", "shared"):
            current = built[architecture]
            torch.testing.assert_close(reference[2].tokens, current[2].tokens)
            torch.testing.assert_close(reference[2].targets, current[2].targets)
            torch.testing.assert_close(reference[3].tokens, current[3].tokens)
            torch.testing.assert_close(reference[3].targets, current[3].targets)
            self.assertEqual(reference[2].prompts, current[2].prompts)
            self.assertEqual(reference[3].prompts, current[3].prompts)
            torch.testing.assert_close(
                reference[1].byte_embedding.weight,
                current[1].byte_embedding.weight,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                reference[1].local_encoder.weight_ih_l0,
                current[1].local_encoder.weight_ih_l0,
                rtol=0.0,
                atol=0.0,
            )
            torch.testing.assert_close(
                reference[1].decoder.weight,
                current[1].decoder.weight,
                rtol=0.0,
                atol=0.0,
            )

    def test_core_matching_contracts_hold_inside_benchmark_models(self):
        _config_ref, ref_model, _train, _validation = _build_composition(
            self.seed, "v5b", self.device
        )
        _config_dense, dense_model, _train, _validation = _build_composition(
            self.seed, "dense", self.device
        )
        _config_shared, shared_model, _train, _validation = _build_composition(
            self.seed, "shared", self.device
        )
        ref = core_stats_for(ref_model, "v5b")
        dense = core_stats_for(dense_model, "dense")
        shared = core_stats_for(shared_model, "shared")
        self.assertEqual(ref.active_linear_macs_per_slot_step, dense.active_linear_macs_per_slot_step)
        self.assertLessEqual(
            abs(ref.trainable_parameters - shared.trainable_parameters),
            max(1, int(0.01 * ref.trainable_parameters)),
        )

    def test_summary_keeps_architectures_separate_and_invalid_inputs_fail(self):
        records = []
        for architecture, score in (("v5b", 1.0), ("dense", 0.8), ("shared", 0.9)):
            records.append(
                {
                    "task": "condition",
                    "architecture": architecture,
                    "score": score,
                    "elapsed_seconds": 1.0,
                    "core_parameters": 100,
                    "active_linear_macs_per_slot_step": 200,
                }
            )
        summary = summarize(records)
        self.assertEqual(summary["tasks"]["condition"]["v5b"]["mean_score"], 1.0)
        self.assertEqual(summary["tasks"]["condition"]["dense"]["mean_score"], 0.8)
        self.assertEqual(summary["tasks"]["condition"]["shared"]["mean_score"], 0.9)
        with self.assertRaises(ValueError):
            CoreComparisonStats("bad", 1, 1)
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1,), task_names=("condition",), architectures=("v5b",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1, 2), task_names=("bad",), architectures=("v5b",))
        with self.assertRaises(ValueError):
            run_benchmark(seeds=(1, 2), task_names=("condition",), architectures=("bad",))


if __name__ == "__main__":
    unittest.main()
