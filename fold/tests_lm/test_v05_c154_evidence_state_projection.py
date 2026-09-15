from __future__ import annotations

from dataclasses import replace
import unittest

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind
from fold_lm.v05_benchmarks import gate_e_c154_evidence_state_projection as c154


class V05C154EvidenceStateProjectionTests(unittest.TestCase):
    def request(self, key="record-a"):
        return dict(
            request_id="C153|20261721|GLOBAL_CONCEPT|CANONICAL|case-1",
            scope_id="C153|20261721|GLOBAL_CONCEPT|CANONICAL",
            key=key,
            domain="retrieval",
            schema="boolean_v1",
            operations=["lookup"],
            source_sha256="a" * 64,
            index_fingerprint="fingerprint-a",
            source_path="snapshot-a/records.json",
            request_epoch=1,
            provider_generation=1,
        )

    def entry(self, key="record-a", value=1):
        return {"request": self.request(key), "value": value}

    def state(self):
        return EvidenceState(evidence_time=1, revision=1, observations=())

    def test_source_binding_is_deterministic(self):
        request = self.request()
        self.assertEqual(c154._source_id(request), c154._source_id(dict(request)))
        changed = dict(request, source_sha256="b" * 64)
        self.assertNotEqual(c154._source_id(request), c154._source_id(changed))

    def test_entry_uses_record_key_and_observed_provenance(self):
        ref = c154._ref_from_entry(self.entry())
        self.assertEqual(ref.evidence_id, "record-a")
        self.assertIs(ref.provenance.kind, ProvenanceKind.OBSERVED)
        self.assertEqual((ref.provenance.evidence_time, ref.provenance.revision), (1, 1))

    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            c154._ref_from_entry(self.entry(value=2))

    def test_new_observation_is_added(self):
        state = self.state()
        ref = c154._ref_from_entry(self.entry())
        status, after = c154.project_observation(state, ref)
        self.assertEqual(status, "ADDED")
        self.assertIsNot(after, state)
        self.assertEqual(after.observations, (ref,))

    def test_exact_duplicate_is_idempotent(self):
        ref = c154._ref_from_entry(self.entry())
        _, state = c154.project_observation(self.state(), ref)
        status, after = c154.project_observation(state, ref)
        self.assertEqual(status, "ALREADY_PRESENT")
        self.assertIs(after, state)

    def test_same_id_conflicting_provenance_is_rejected(self):
        ref = c154._ref_from_entry(self.entry())
        _, state = c154.project_observation(self.state(), ref)
        bad = replace(ref, provenance=replace(ref.provenance, source_id="different"))
        status, after = c154.project_observation(state, bad)
        self.assertEqual(status, "PROVENANCE_CONFLICT")
        self.assertIs(after, state)

    def test_distinct_records_coexist(self):
        state = self.state()
        for key in ("record-a", "record-b"):
            status, state = c154.project_observation(state, c154._ref_from_entry(self.entry(key)))
            self.assertEqual(status, "ADDED")
        self.assertEqual([x.evidence_id for x in state.observations], ["record-a", "record-b"])

    def test_future_provenance_uses_actual_evidence_state_guard(self):
        ref = EvidenceRef("future", Provenance("source", ProvenanceKind.OBSERVED, 2, 1))
        with self.assertRaisesRegex(ValueError, "future revision"):
            c154.project_observation(self.state(), ref)

    def test_gate_requires_all_registered_totals(self):
        semantics = {
            "WITHIN_FACTOR": {o: {"cases": 20736, "semantic_correct": 20727} for o in c154.ORDERS},
            "GLOBAL_CONCEPT": {o: {"cases": 20736, "semantic_correct": 20736} for o in c154.ORDERS},
        }
        metrics = dict(streams=48, source_entries=82944, added=3072, already_present=79872,
                       conflict_rejections=3072, final_observations=3072,
                       semantic_source_counts=semantics)
        self.assertTrue(c154._gate(metrics))
        metrics["added"] -= 1
        self.assertFalse(c154._gate(metrics))

    def test_header_requires_full_accepted_c153(self):
        data = dict(
            experiment_id=c154.PRIOR_ID, commit_sha=c154.PRIOR_COMMIT, status="PASS",
            diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
            summary=dict(source_selection_trace_reused=True, source_trace_heads=24, model_loading=False,
                         fresh_seed_count=0, training_steps=0, retrieval_calls=82944,
                         submissions_per_request=7, submissions=580608, expected_rejections=414720,
                         expected_commits=82944, expected_duplicate_rejections=82944,
                         inbox_kind="DIAGNOSTIC_IMMUTABLE_IN_PROCESS", production_state_commit=False,
                         controller_exercised=False, answer_exercised=False, crash_recovery_exercised=False,
                         evidence_admission_gate_passed=True),
            records=[{} for _ in range(48)],
        )
        c154._header(data)
        data["status"] = "FAIL"
        with self.assertRaises(ValueError):
            c154._header(data)

    def test_source_id_requires_complete_binding(self):
        request = self.request()
        request["source_path"] = ""
        with self.assertRaises(ValueError):
            c154._source_id(request)

    def test_projection_preserves_state_clock(self):
        _, state = c154.project_observation(self.state(), c154._ref_from_entry(self.entry()))
        self.assertEqual((state.evidence_time, state.revision), (1, 1))


if __name__ == "__main__":
    unittest.main()
