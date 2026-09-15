from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, replace
import copy
import inspect
from types import SimpleNamespace
import unittest

import numpy as np
import torch

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind, WorkingState, BudgetState
from fold_lm.v05_benchmarks import gate_e_c156_request_reobservation as c156


class V05C156RequestReobservationTests(unittest.TestCase):
    def setUp(self):
        self.md = dict(source_sha256="a"*64, index_fingerprint="index-a", source_path="snapshot-a/records.json")
        self.sid = c156._source_id(self.md)
        self.ref = EvidenceRef("record-a", Provenance(self.sid, ProvenanceKind.OBSERVED, 1, 1))
        self.other = replace(self.ref, evidence_id="record-b")
        self.state = EvidenceState(1, 1, (self.ref, self.other))
        self.work = WorkingState(1, 7, np.array([[1., 1., 1., 1., .125, -.25, .375, -.5]]))
        self.budget = BudgetState(3, 2)
        self.req = c156.ReadRequest("scope|request-1", "scope", self.ref, "domain", "schema", ("READ",))
        self.calls = []

    def result(self, value=0, **changes):
        evidence = SimpleNamespace(key="record-a", domain="domain", schema="schema", operations=("READ",),
                                   evidence_value=value, **self.md)
        out = SimpleNamespace(status="RESOLVED", value=value, evidence=evidence, retrieval_calls=1, vectors_scored=64)
        for key, val in changes.items():
            setattr(out, key, val)
        return out

    def read(self, result=None, state=None, work=None, budget=None, req=None):
        def resolver(ref, registry):
            self.calls.append(ref)
            return self.result() if result is None else result
        return c156.reobserve(self.req if req is None else req, self.state if state is None else state,
                               self.work if work is None else work, self.budget if budget is None else budget,
                               {}, resolver)

    def test_valid_zero_is_present_and_overwrites_stale_one(self):
        out = self.read()
        self.assertEqual(out.value, 0)
        self.assertEqual(out.status, "RESOLVED")
        self.assertEqual(out.working.slots[0, 2:4].tolist(), [1., 0.])
        self.assertIs(out.reference, self.ref)

    def test_valid_one_is_present_and_overwrites_stale_zero(self):
        work = WorkingState(1, 7, np.array([[1., 1., 1., 0., .125, -.25, .375, -.5]]))
        out = self.read(self.result(1), work=work)
        self.assertEqual(out.value, 1)
        self.assertEqual(out.working.slots[0, 2:4].tolist(), [1., 1.])

    def test_missing_ref_does_not_read_other_available_ref(self):
        state = replace(self.state, observations=(self.other,))
        out = self.read(state=state)
        self.assertEqual(out.status, "REFERENCE_UNBOUND")
        self.assertFalse(self.calls)
        self.assertIsNone(out.value)
        self.assertEqual(out.working.slots[0, 2:4].tolist(), [0., 0.])

    def test_same_key_wrong_provenance_does_not_read(self):
        bad = replace(self.ref, provenance=replace(self.ref.provenance, source_id="other-source"))
        out = self.read(state=EvidenceState(1, 1, (bad,)))
        self.assertEqual(out.status, "REFERENCE_MISMATCH")
        self.assertFalse(self.calls)

    def test_resolution_failure_clears_old_payload_and_presence(self):
        out = self.read(self.result(1, status="SOURCE_UNBOUND", retrieval_calls=0, vectors_scored=0))
        self.assertIsNone(out.value)
        self.assertIsNone(out.reference)
        self.assertEqual(out.working.slots[0, 2:4].tolist(), [0., 0.])

    def test_wrong_resolved_key_with_same_bit_is_rejected(self):
        result = self.result()
        result.evidence.key = "record-b"
        out = self.read(result)
        self.assertEqual(out.status, "READBACK_MISMATCH")
        self.assertIsNone(out.value)

    def test_wrong_resolved_source_is_rejected(self):
        for field in self.md:
            result = self.result()
            setattr(result.evidence, field, "wrong")
            self.assertEqual(self.read(result).status, "READBACK_MISMATCH")

    def test_wrong_domain_schema_or_operations_are_rejected(self):
        for field, value in (("domain", "other"), ("schema", "other"), ("operations", ("WRITE",))):
            result = self.result()
            setattr(result.evidence, field, value)
            self.assertEqual(self.read(result).status, "READBACK_MISMATCH")

    def test_invalid_bit_types_and_nonfinite_values_are_not_exposed(self):
        for bit in (True, False, 2, -1, .5, float("nan"), None):
            out = self.read(self.result(bit))
            self.assertEqual(out.status, "READBACK_MISMATCH")
            self.assertIsNone(out.value)

    def test_success_without_evidence_or_inconsistent_payload_rejected(self):
        self.assertEqual(self.read(self.result(evidence=None)).status, "READBACK_MISMATCH")
        result = self.result()
        result.evidence.evidence_value = 1
        self.assertEqual(self.read(result).status, "READBACK_MISMATCH")

    def test_state_clock_and_object_identity_preserved(self):
        out = self.read()
        self.assertIs(out.evidence_state, self.state)
        self.assertEqual((out.evidence_state.evidence_time, out.evidence_state.revision), (1, 1))
        self.assertEqual(out.working.evidence_time, 1)

    def test_one_internal_step_is_consumed_not_acquisition_budget(self):
        out = self.read()
        self.assertEqual(out.working.internal_step, 8)
        self.assertEqual(out.budget, BudgetState(2, 2))
        self.assertEqual(self.budget, BudgetState(3, 2))

    def test_exhausted_budget_rejects_before_dereference(self):
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            self.read(budget=BudgetState(0, 2))
        self.assertFalse(self.calls)

    def test_invalid_shape_and_clock_reject_before_dereference(self):
        for work in (WorkingState(2, 7, np.ones((1, 8))), WorkingState(1, 7, np.ones((2, 8)))):
            with self.assertRaises(ValueError):
                self.read(work=work)
        self.assertFalse(self.calls)

    def test_other_working_channels_and_old_object_unchanged(self):
        saved = self.work.slots.copy()
        out = self.read()
        np.testing.assert_array_equal(out.working.slots[:, [0, 1, 4, 5, 6, 7]], saved[:, [0, 1, 4, 5, 6, 7]])
        np.testing.assert_array_equal(self.work.slots, saved)
        self.assertFalse(out.working.slots.flags.writeable)
        self.assertIsNot(out.working, self.work)

    def test_request_scope_and_selected_ref_not_replaced_by_other_key(self):
        req = replace(self.req, request_id="scope|request-2", reference=self.other)
        result = self.result(1)
        result.evidence.key = "record-b"
        out = self.read(result, req=req)
        self.assertEqual(self.calls, [self.other])
        self.assertEqual((out.request_id, out.scope_id), (req.request_id, req.scope_id))
        self.assertIs(out.reference, self.other)

    def test_request_binding_is_frozen_and_rejects_invalid_scope(self):
        with self.assertRaises(FrozenInstanceError):
            self.req.domain = "bad"
        with self.assertRaises(ValueError):
            replace(self.req, request_id="another|request")
        with self.assertRaises(ValueError):
            replace(self.req, operations=())

    def test_signed_control_inputs_distinguish_zero_from_unresolved(self):
        zero = self.read()
        miss = self.read(state=EvidenceState(1, 1, ()))
        tensors = c156.control_inputs([zero, miss])
        self.assertEqual(tensors.shape, (2, 1, 8))
        self.assertEqual(tensors.dtype, torch.float32)
        self.assertEqual(tensors[:, 0, 2:4].tolist(), [[1., -1.], [-1., -1.]])
        self.assertEqual(zero.value, 0)
        self.assertIsNone(miss.value)

    def test_control_inputs_preserve_data_channels_and_do_not_mutate_views(self):
        o = self.read(self.result(1))
        before = o.working.slots.copy()
        t = c156.control_inputs([o])
        np.testing.assert_array_equal(t.numpy()[0, 0, 4:], before[0, 4:].astype(np.float32))
        np.testing.assert_array_equal(o.working.slots, before)
        with self.assertRaises(ValueError):
            c156.control_inputs([])

    def test_source_digest_is_deterministic_and_requires_complete_fields(self):
        self.assertEqual(c156._source_id(dict(reversed(list(self.md.items())))), self.sid)
        self.assertNotEqual(c156._source_id(dict(self.md, source_path="other")), self.sid)
        with self.assertRaises(ValueError):
            c156._source_id({})

    def test_no_ground_truth_parameter_in_read_or_control_interface(self):
        for function in (c156.reobserve, c156.control_inputs):
            names = inspect.signature(function).parameters
            self.assertFalse(any("expected" in name or "label" in name or "correct" in name for name in names))

    def test_behavioral_mismatch_is_false_not_invalid_exception(self):
        out = self.read(self.result(1))
        self.assertFalse(c156._case_pass(out, self.req, self.state, self.work, self.budget, "MATCHED", 0))
        self.assertTrue(c156._case_pass(out, self.req, self.state, self.work, self.budget, "MATCHED", 1))

    def test_prerequisite_rejects_console_extract_and_wrong_gate(self):
        data = dict(experiment_id=c156.C155_ID, commit_sha=c156.C155_COMMIT, status="PASS",
                    diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                    summary=dict(source_streams=48, references=3072, resolver_calls=12288, failed_cases=0,
                      state_mutations=0, retrieval_calls=3072, vectors_scored=196608,
                      resolved_values={"0":1296,"1":1776}, payload_dereference_gate_passed=True,
                      model_loading=False,new_neural_scoring=False,fresh_seed_count=0,training_steps=0,
                      controller_exercised=False,answer_exercised=False,new_observation_committed=False,
                      status_counts={k:3072 for k in ("RESOLVED","SOURCE_UNBOUND","SNAPSHOT_MISMATCH","RECORD_UNBOUND")}),
                    records=[{} for _ in range(48)])
        c156._header(data)
        for field, value in (("records", "omitted; see summary.json"), ("status", "FAIL"), ("commit_sha", "wrong")):
            changed = dict(data, **{field:value})
            with self.assertRaises(ValueError):
                c156._header(changed)

    def test_gate_requires_all_cases_costs_state_and_both_bit_values(self):
        good = dict(source_requests=c156.REQUESTS, reobservation_calls=4*c156.REQUESTS,
                    status_counts={k:c156.REQUESTS for k in c156.STATUSES.values()}, failed_cases=0,
                    control_tensor_failures=0, state_mutations=0, old_working_mutations=0,
                    retrieval_calls=c156.REQUESTS,vectors_scored=c156.REQUESTS*64,
                    internal_steps_consumed=4*c156.REQUESTS,acquisition_budget_consumed=0,
                    resolved_values={"0":1,"1":c156.REQUESTS-1})
        self.assertTrue(c156._gate(good))
        for field in ("failed_cases", "control_tensor_failures", "state_mutations", "old_working_mutations", "acquisition_budget_consumed"):
            self.assertFalse(c156._gate(dict(good, **{field:1})))
        self.assertFalse(c156._gate(dict(good, resolved_values={"0":0,"1":c156.REQUESTS})))
        self.assertFalse(c156._gate(dict(good, retrieval_calls=0)))


if __name__ == "__main__":
    unittest.main()
