from __future__ import annotations

import copy
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from fold_lm.v05_benchmarks.gate_c_full_model_validation_boundary import (
    VARIANTS, make_models, order_for_round, run_benchmark, summarize_records,
    trajectory_score, validate_scope, validate_state_metadata, validate_task_metadata,
)


def records_for(rounds=2):
    records = []
    for r in range(rounds):
        for name, factor in zip(VARIANTS, (2.0, 8.0, 1.0, 3.0)):
            records.append({"round": r, "variant": name,
                            "device_per_forward_ms": factor * (r + 1),
                            "wall_per_forward_ms": 2 * factor * (r + 1)})
    return records


class V05GateCFullModelValidationBoundaryTests(unittest.TestCase):
    def test_variants_are_explicit_and_do_not_mix_policies(self):
        self.assertEqual(VARIANTS, ("dense_checked", "triton_checked", "dense_boundary", "triton_boundary"))

    def test_order_balances_every_four_rounds(self):
        for slot in range(4):
            self.assertEqual({order_for_round(r)[slot] for r in range(4)}, set(VARIANTS))
        for bad in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                order_for_round(bad)

    def test_invalid_scope_rejected_before_loading_or_cuda(self):
        for kwargs in ({"warmup": -1}, {"rounds": 0}, {"iterations": True}):
            with self.assertRaises(ValueError):
                run_benchmark("not-used.pt", **kwargs)
        validate_scope(0, 8, 1)

    def test_summary_reports_each_policy_and_raw_record_count(self):
        result = summarize_records(records_for(), {n: 1.0 for n in VARIANTS}, rounds=2)
        self.assertEqual(result["record_count"], 8)
        ratios = result["paired_ratios"]
        self.assertEqual(ratios["triton_vs_dense_checked_device"]["median"], 4.0)
        self.assertEqual(ratios["triton_vs_dense_boundary_device"]["median"], 3.0)
        self.assertEqual(ratios["dense_checked_to_boundary_speedup_wall"]["median"], 2.0)

    def test_all_rounds_contribute_and_record_order_is_irrelevant(self):
        records = records_for()
        scores = {n: 1.0 for n in VARIANTS}
        before = summarize_records(records, scores, rounds=2)
        self.assertEqual(before, summarize_records(list(reversed(records)), scores, rounds=2))
        next(r for r in records if r["round"] == 0 and r["variant"] == "triton_boundary")["device_per_forward_ms"] = 300
        after = summarize_records(records, scores, rounds=2)
        self.assertNotEqual(before["paired_ratios"], after["paired_ratios"])

    def test_missing_duplicate_unknown_and_invalid_rounds_are_rejected(self):
        scores = {n: 1.0 for n in VARIANTS}
        bad_sets = [records_for()[:-1], records_for() + [records_for()[0]]]
        for key, value in (("variant", "unknown"), ("round", -1), ("round", True), ("round", 2)):
            rows = records_for()
            rows[0][key] = value
            bad_sets.append(rows)
        for rows in bad_sets:
            with self.assertRaises(ValueError):
                summarize_records(rows, scores, rounds=2)

    def test_invalid_timings_and_scores_are_rejected(self):
        for bad in (0, -1, True, math.inf, math.nan):
            for metric in ("device_per_forward_ms", "wall_per_forward_ms"):
                records = records_for()
                records[0][metric] = bad
                with self.assertRaises(ValueError):
                    summarize_records(records, {n: 1.0 for n in VARIANTS}, rounds=2)
        for bad in (-1, 1.01, True, math.inf, math.nan):
            scores = {n: 1.0 for n in VARIANTS}; scores["dense_checked"] = bad
            with self.assertRaises(ValueError):
                summarize_records(records_for(), scores, rounds=2)
        with self.assertRaises(ValueError):
            summarize_records(records_for(), {}, rounds=2)

    def test_task_metadata_preserves_type_shape_and_dtype_checks(self):
        cfg = SimpleNamespace(operation_steps=3)
        initial = torch.zeros(2, dtype=torch.int64)
        ops = torch.zeros(2, 3, dtype=torch.int64)
        with patch("torch.any", side_effect=AssertionError("no reductions in metadata")):
            validate_task_metadata(cfg, initial, ops, ops)
        for args in (([], ops, ops), (initial.float(), ops, ops), (initial, ops[:, :2], ops)):
            with self.assertRaises((TypeError, ValueError)):
                validate_task_metadata(cfg, *args)

    def test_state_metadata_does_not_scan_values_and_rejects_bad_structure(self):
        cfg = SimpleNamespace(modules=2, slots=1, width=4)
        h = torch.zeros(2, 1, 4)
        with patch("torch.isfinite", side_effect=AssertionError("no finite scan in metadata")):
            validate_state_metadata(cfg, h, h, 0)
        for args in ((h, h, True), (h, h, 2), (h[:, 0], h, 0), (h, h.double(), 0), (h, h.long(), 0)):
            with self.assertRaises((TypeError, ValueError)):
                validate_state_metadata(cfg, *args)

    def test_trajectory_score_and_nonfinite_rejection(self):
        targets = torch.tensor([[0, 1], [1, 0]], dtype=torch.int64)
        output = targets.float() / 10
        self.assertEqual(trajectory_score(output, targets, 10), 1.0)
        output[0, 1] = 1.0
        self.assertEqual(trajectory_score(output, targets, 10), 0.5)
        output[0, 0] = math.nan
        with self.assertRaises(ValueError):
            trajectory_score(output, targets, 10)

    def _cuda_models(self):
        from fold_lm.v05.composition_task import CompositionModel, CompositionTaskConfig
        from fold_lm.v05.compressed_runtime import CompressedModuleInitializations
        from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization
        torch.manual_seed(20260913)
        dense = CompositionModel(CompositionTaskConfig(width=32)).cuda().eval()
        init = CompressedModuleInitializations(
            up=build_synthetic_initialization(32, 64),
            down=build_synthetic_initialization(64, 32),
        )
        return dense, init

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_boundary_models_keep_e_states_outputs_and_original_validation(self):
        dense, init = self._cuda_models()
        original = copy.deepcopy(dense.state_dict())
        models = make_models(dense, init)
        inputs = (torch.tensor([0, 1], device="cuda"),
                  torch.tensor([[0, 1, 0], [1, 0, 1]], device="cuda"),
                  torch.tensor([[1, 0, 2], [2, 1, 0]], device="cuda"))
        with torch.inference_mode():
            for root in ("dense", "triton"):
                checked, boundary = models[root + "_checked"], models[root + "_boundary"]
                self.assertEqual(set(checked.state_dict()), set(boundary.state_dict()))
                for key, value in checked.state_dict().items():
                    torch.testing.assert_close(value, boundary.state_dict()[key], rtol=0, atol=0)
                expected = checked(*inputs)
                output = boundary(*inputs)
                torch.testing.assert_close(output, expected, rtol=1e-4, atol=1e-5)
                old = torch.cuda.get_sync_debug_mode()
                try:
                    torch.cuda.set_sync_debug_mode("error")
                    boundary(*inputs)
                finally:
                    torch.cuda.set_sync_debug_mode(old)
                torch.cuda.synchronize()
            for role in ("up", "down"):
                a = getattr(models["triton_checked"].core, role + "_bank")
                b = getattr(models["triton_boundary"].core, role + "_bank")
                self.assertEqual(a.resident_tensor_bytes, b.resident_tensor_bytes)
                self.assertGreater(a._correction(0)[1].numel(), 0)
            for key, value in original.items():
                torch.testing.assert_close(value, dense.state_dict()[key], rtol=0, atol=0)
            bad = inputs[0].clone(); bad[0] = -1
            with self.assertRaises(ValueError):
                dense._validate(bad, inputs[1], inputs[2])

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_complete_runner_on_synthetic_saved_fixture_without_training(self):
        from fold_lm.v05.composition_task import evaluate_composition, make_composition_splits
        from fold_lm.v05.compact_runtime import CompactVectorizedFixedRoutingCore
        from fold_lm.v05_benchmarks.gate_c_runtime_fixture import save_runtime_fixture
        dense, init = self._cuda_models()
        _, validation = make_composition_splits(dense.config)
        compact = copy.deepcopy(dense)
        compact.core = CompactVectorizedFixedRoutingCore(dense.core, init).cuda()
        key = "trajectory_exact_accuracy"
        dscore = evaluate_composition(dense, validation)[key]
        cscore = evaluate_composition(compact, validation)[key]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.pt"
            save_runtime_fixture(path, task="composition", seed=20260921, dense_model=dense,
                                 compressed_initializations=init,
                                 scores={"dense": dscore, "compact": cscore, "direct": cscore})
            digest = path.read_bytes()
            result = run_benchmark(path, warmup=0, rounds=4, iterations=1)
            self.assertEqual(result["summary"]["record_count"], 16)
            self.assertFalse(result["retrained"])
            self.assertFalse(result["gate_c_candidate"])
            self.assertEqual(result["scores"]["triton_boundary"], cscore)
            self.assertEqual(path.read_bytes(), digest)


if __name__ == "__main__":
    unittest.main()
