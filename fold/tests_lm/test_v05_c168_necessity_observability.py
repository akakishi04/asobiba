"""Implementation controls, not the artifact-backed C168 deciding run."""
import inspect
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fold_lm.v05_benchmarks import gate_e_c168_necessity_observability as m


def capture(v=0):
    return dict(tensors={"toy": v}, runtime={"available": True})


def row(name, label, value=0):
    return dict(case_id=name, requires_acquisition=label, capture=capture(value))


class C168UnitTests(unittest.TestCase):
    def test_truth_table_and(self):
        self.assertEqual([m.truth("AND", a, b) for a in (0,1) for b in (0,1)], [0,0,0,1])

    def test_truth_table_or(self):
        self.assertEqual([m.truth("OR", a, b) for a in (0,1) for b in (0,1)], [0,1,1,1])

    def test_necessity_changes_with_operator(self):
        for a in (0,1):
            self.assertNotEqual(m.necessity("AND", a)["requires_acquisition"],
                                m.necessity("OR", a)["requires_acquisition"])

    def test_fixed_output_is_not_an_observed_b(self):
        self.assertEqual(m.necessity("AND", 0), dict(possible_outputs=[0], requires_acquisition=False))
        self.assertEqual(m.necessity("OR", 1), dict(possible_outputs=[1], requires_acquisition=False))

    def test_bit_rejects_bool_none_and_float(self):
        for x in (True, False, None, 1.0, -1, 2):
            with self.assertRaises(ValueError): m.bit(x)

    def test_unregistered_operator_is_rejected(self):
        with self.assertRaises(ValueError): m.truth("XOR", 0, 1)

    def test_manifest_has_eight_challenges_four_controls(self):
        p = m.manifest()
        self.assertEqual((len(p["cases"]), len(p["source_controls"])), (8,4))
        self.assertEqual(len({r["case_id"] for r in p["cases"]}), 8)

    def test_manifest_is_deterministic_and_independent(self):
        a, b = m.manifest(), m.manifest()
        self.assertEqual(m.blob(a), m.blob(b))
        self.assertEqual(hashlib.sha256(m.blob(a)).hexdigest(), m.MANIFEST_SHA)
        a["cases"][0]["known_a"] = 99
        self.assertEqual(b, m.manifest())

    def test_manifest_does_not_contain_hidden_values_or_labels(self):
        for r in m.manifest()["cases"]:
            self.assertEqual(set(r), {"case_id","operator","known_a","b_observed","stale_bit"})
            self.assertIs(r["b_observed"], False)

    def test_stale_bit_is_fully_crossed_not_a_proxy_for_known_a(self):
        p = m.manifest()["cases"]
        for op in ("AND","OR"):
            for a in (0,1):
                self.assertEqual({r["stale_bit"] for r in p if r["operator"]==op and r["known_a"]==a}, {0,1})

    def test_capture_interface_excludes_task_and_evaluator(self):
        self.assertEqual(list(inspect.signature(m.capture_current_inputs).parameters), ["stale_bit","available"])

    def test_collision_is_retained_as_finite_result(self):
        result = m.analyze([row("a",True), row("b",False)])
        self.assertEqual((result["conflicting_classes"], result["classification_error_lower_bound"]), (1,1))

    def test_separable_inputs_have_zero_lower_bound(self):
        result = m.analyze([row("a",True,0), row("b",False,1)])
        self.assertEqual((result["equivalence_classes"], result["classification_error_lower_bound"]), (2,0))

    def test_class_lower_bound_uses_minority_not_pair_count(self):
        result = m.analyze([row("a",True),row("b",True),row("c",False)])
        self.assertEqual(result["classification_error_lower_bound"],1)

    def test_labels_and_ids_do_not_enter_input_equivalence(self):
        a, b = row("alpha",True), row("beta",False)
        self.assertEqual(m.input_key(a["capture"]),m.input_key(b["capture"]))

    def test_runtime_availability_is_part_of_equivalence(self):
        a,b=capture(),capture()
        b["runtime"]["available"]=False
        self.assertNotEqual(m.input_key(a),m.input_key(b))

    def test_reordering_rows_does_not_change_analysis(self):
        rows=[row("b",True),row("a",False),row("c",True,1)]
        self.assertEqual(m.analyze(rows),m.analyze(list(reversed(rows))))

    def test_malformed_labels_and_duplicate_ids_are_rejected(self):
        for rows in ([],[row("a",1)],[row("a",True),row("a",False)]):
            with self.assertRaises(ValueError): m.analyze(rows)

    def test_nan_is_not_silently_serialized(self):
        with self.assertRaises(ValueError): m.blob({"x":float("nan")})

    def test_changed_parent_hash_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"summary.json";p.write_text("{}")
            with self.assertRaises(m.InvalidExecution): m.validate_parent(p)


class C168SourceIntegrationTests(unittest.TestCase):
    def test_actual_capture_stops_before_forward_and_retrieval(self):
        r=m.capture_current_inputs(0)
        self.assertEqual((r["capture_callbacks"],r["model_forward_calls"],r["retrieval_calls"]),(1,0,0))
        self.assertEqual(r["runtime"]["reference_count"],63)
        self.assertIsNone(r["observation"]["value"])

    def test_actual_capture_clears_stale_zero_and_one(self):
        a,b=m.capture_current_inputs(0),m.capture_current_inputs(1)
        self.assertEqual(m.input_key(a),m.input_key(b))
        self.assertEqual(a["tensors"]["working"]["values"][0][0][1:4], [1.0,-1.0,-1.0])

    def test_actual_availability_context_is_distinct(self):
        a,b=m.capture_current_inputs(0,False),m.capture_current_inputs(0,True)
        self.assertNotEqual(m.input_key(a),m.input_key(b))
        self.assertEqual(a["tensors"]["operation_ids"]["values"],[0])

    def test_actual_capture_preserves_external_clock_and_pays_one_internal_step(self):
        r=m.capture_current_inputs(1)
        self.assertEqual(r["runtime"]["budget"],dict(internal_steps_remaining=2,acquisitions_remaining=1))
        self.assertEqual((r["observation"]["internal_step"],r["runtime"]["evidence_time"],r["runtime"]["revision"]),(8,1,1))


if __name__ == "__main__":
    unittest.main()
