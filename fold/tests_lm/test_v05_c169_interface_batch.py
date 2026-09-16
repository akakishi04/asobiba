"""C169 harness tests, separate from the registered diagnostic result."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fold_lm.v05_benchmarks import gate_e_c169_interface_batch as m


def empty_sections():
    return [m.section(s, {}) for s in m.SECTIONS]


class C169UnitTests(unittest.TestCase):
    def test_manifest_has_exact_six_sections(self):
        self.assertEqual(len(m.SECTIONS), 6)
        self.assertEqual(m.manifest()["sections"], list(m.SECTIONS))

    def test_manifest_returns_independent_objects(self):
        a = m.manifest(); a["sections"].clear(); a["counts"].clear()
        self.assertEqual(len(m.manifest()["sections"]), 6)
        self.assertEqual(m.manifest()["counts"], m.EXPECTED_COUNTS)

    def test_manifest_fixes_zero_learned_work(self):
        p = m.manifest()
        for k in ("learned_forward_calls", "checkpoint_loads", "adapter_calls", "training_steps", "fresh_seed_count"):
            self.assertEqual(p[k], 0)

    def test_registered_counts_do_not_call_scripted_policy_learned(self):
        self.assertEqual(m.EXPECTED_COUNTS["scripted_policy_calls"], 9)
        self.assertEqual(m.EXPECTED_COUNTS["decision_input_captures"], 8)
        self.assertEqual(m.EXPECTED_COUNTS["feature_prefix_captures"], 19)
        self.assertEqual(m.EXPECTED_COUNTS["reobservations"], 17)

    def test_all_boundary_sections_are_ready_only_without_gaps(self):
        self.assertTrue(m.aggregate(empty_sections())["interface_ready"])

    def test_single_gap_is_not_averaged_away(self):
        items = empty_sections(); items[0]["gaps"] = ["missing field"]
        s = m.aggregate(items)
        self.assertFalse(s["interface_ready"]); self.assertEqual(s["gap_sections"], 1)

    def test_finite_violation_is_distinct_from_gap(self):
        items = empty_sections(); items[3]["violations"] = ["authority"]
        s = m.aggregate(items)
        self.assertFalse(s["interface_ready"])
        self.assertEqual((s["gap_sections"], s["finite_violation_sections"]), (0, 1))

    def test_incomplete_reordered_or_duplicate_sections_are_invalid(self):
        for items in (empty_sections()[:-1], empty_sections()[::-1], empty_sections()+empty_sections()[:1]):
            with self.assertRaises(m.prior.InvalidExecution):
                m.aggregate(items)

    def test_section_reports_finite_failure_before_boundary_label(self):
        self.assertEqual(m.section("x", {}, violations=["bad"])["status"], "FAIL")
        self.assertEqual(m.section("x", {}, gaps=["missing"])["status"], "GAP")

    def test_nonfinite_data_is_not_serialized(self):
        with self.assertRaises(ValueError):
            m.blob({"v": float("nan")})

    def test_parent_hash_checked_before_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"summary.json"; p.write_text("not json")
            with self.assertRaises(m.prior.InvalidExecution):
                m.validate_parent(p)

    def test_parent_rejects_pass_wrong_scope_and_console_extract(self):
        base = dict(experiment_id=m.prior.EXPERIMENT_ID, stage=m.prior.STAGE,
            commit_sha=m.BASE, status="FAIL", diagnostic_execution_valid=True, passed=False,
            production_runtime_modified=False, gate_e_candidate=False,
            records=[{}]*8, source_controls=[{}]*4)
        with tempfile.TemporaryDirectory() as d, patch.object(m, "sha", return_value=m.C168_SHA):
            p = Path(d)/"summary.json"
            for change in (dict(status="PASS"), dict(production_runtime_modified=True), dict(records="omitted")):
                p.write_text(json.dumps(dict(base, **change)))
                with self.assertRaises(m.prior.InvalidExecution):
                    m.validate_parent(p)

    def test_parent_accepts_registered_negative_metadata(self):
        data = dict(experiment_id=m.prior.EXPERIMENT_ID, stage=m.prior.STAGE,
            commit_sha=m.BASE, status="FAIL", diagnostic_execution_valid=True, passed=False,
            production_runtime_modified=False, gate_e_candidate=False, records=[{}]*8, source_controls=[{}]*4)
        with tempfile.TemporaryDirectory() as d, patch.object(m, "sha", return_value=m.C168_SHA):
            p = Path(d)/"summary.json"; p.write_text(json.dumps(data))
            self.assertEqual(m.validate_parent(p), data)

    def test_aggregation_preserves_section_data(self):
        items = empty_sections(); old = deepcopy(items)
        m.aggregate(items); self.assertEqual(items, old)

    def test_regression_appends_only_current_module(self):
        with patch.object(m.prior, "regression_modules", return_value=["historical"]):
            self.assertEqual(m.regression_modules(Path(".")),
                             ["historical", "tests_lm.test_v05_c169_interface_batch"])

    def test_manifest_is_canonical_and_contains_no_hidden_answers(self):
        p = m.manifest()
        self.assertEqual(m.blob(p), m.blob(m.manifest()))
        self.assertNotIn("requires_acquisition", p)
        self.assertNotIn("hidden_b", p)


class C169IntegrationTests(unittest.TestCase):
    def tensors(self):
        import torch
        return torch.zeros(1, 1, 8), torch.zeros(1, 1, 8), torch.zeros(1, dtype=torch.int64)

    def test_actual_feature_prefix_ignores_tail(self):
        w, c, op = self.tensors(); meter = Counter()
        base = m.feature_prefix(w, c, op, meter)
        w[0, 0, 7] = 3; c[0, 0, 5] = -2
        self.assertEqual(m.feature_prefix(w, c, op, meter), base)
        self.assertEqual(meter["feature_prefix_captures"], 2)

    def test_actual_feature_prefix_reads_control_channels(self):
        w, c, op = self.tensors(); meter = Counter()
        base = m.feature_prefix(w, c, op, meter)
        w[0, 0, 0] = .25
        self.assertNotEqual(m.feature_prefix(w, c, op, meter), base)

    def test_actual_feature_prefix_mean_loses_slot_order(self):
        import torch
        w, c, op = self.tensors(); meter = Counter()
        w = torch.cat((w+1, w-1), dim=1); c = c.repeat(1, 2, 1)
        self.assertEqual(m.feature_prefix(w, c, op, meter), m.feature_prefix(w.flip(1), c, op, meter))

    def test_actual_reobservation_probes_keep_reasons_but_collapse_missing_features(self):
        meter = Counter(); f = m.fixture(meter); item, _ = m.observation_audit(f, meter)
        self.assertEqual(item["violations"], [])
        self.assertEqual(item["evidence"]["reason_identity_in_controller_tensor"], 1)
        self.assertEqual(meter["fixture_resolver_calls"], 4)

    def test_actual_reobservation_preserves_dependency_and_clears_stale(self):
        meter = Counter(); f = m.fixture(meter); item, _ = m.observation_audit(f, meter)
        r = item["evidence"]["probes"]
        self.assertEqual(r[0]["new_working"], r[1]["new_working"])
        self.assertNotEqual(r[0]["controller_working"], r[2]["controller_working"])
        self.assertEqual(meter["reobservations"], 8)

    def test_actual_context_and_runtime_authority_are_separate(self):
        meter = Counter(); f = m.fixture(meter); _, o = m.observation_audit(f, meter)
        item = m.context_audit(f, o, meter)
        self.assertEqual(item["violations"], [])
        self.assertEqual(item["evidence"]["distinct_tensor_classes"], 2)
        self.assertEqual(meter["authority_probes"], 8)

    def test_actual_cycle_all_six_scripted_action_dispatches(self):
        meter = Counter(); f = m.fixture(meter); item = m.dispatch_audit(f, meter)
        self.assertEqual(item["evidence"]["unsupported_indices"], [1, 3, 4])
        self.assertEqual(item["violations"], [])
        self.assertEqual((meter["scripted_cycles"], meter["scripted_policy_calls"]), (6, 7))

    def test_actual_emitter_observed_bit_and_mismatch_controls(self):
        meter = Counter(); f = m.fixture(meter); item = m.output_audit(f, meter)
        self.assertEqual(item["violations"], [])
        self.assertTrue(item["gaps"])
        self.assertEqual((meter["terminal_emissions"], meter["fixture_resolver_calls"]), (4, 2))


if __name__ == "__main__":
    unittest.main()
