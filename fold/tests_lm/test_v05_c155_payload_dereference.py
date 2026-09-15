from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import asdict, fields, replace
import hashlib
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind
from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c155_payload_dereference as c155


def make_source(root: Path, name: str, *, reverse=False):
    rows = [dict(key=f"r{i}", domain="c152", schema="c152-descriptor-handle-v1", operations=["READ_EVIDENCE"],
                 structure=[float(j == i) for j in range(64)], semantics=[1.0, 0.0], evidence_value=i % 2)
            for i in range(64)]
    path = root / name
    path.write_bytes(c155._bytes(dict(schema_version=1, records=list(reversed(rows)) if reverse else rows)))
    adapter = PersistedStructuralRetrievalAdapter(path)
    metadata = dict(source_path=str(path.resolve()), source_sha256=adapter.source_sha256,
                    index_fingerprint=adapter.index_fingerprint, request_epoch=1, provider_generation=1)
    return c155.load_binding(metadata), metadata


def make_ref(binding, key="r0"):
    return EvidenceRef(key, Provenance(binding.source_id, ProvenanceKind.OBSERVED, 1, 1))


class V05C155PayloadDereferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.binding, self.metadata = make_source(self.root, "a.json")
        self.ref = make_ref(self.binding)
        self.registry = {self.binding.source_id: self.binding}

    def tearDown(self):
        self.temp.cleanup()

    def mutated_response(self, evidence_changes=None, stat_changes=None, miss=False):
        original = self.binding.adapter.retrieve
        def call(*args, **kwargs):
            evidence, stats = original(*args, **kwargs)
            return (None if miss else replace(evidence, **(evidence_changes or {}))), dict(stats, **(stat_changes or {}))
        return patch.object(self.binding.adapter, "retrieve", side_effect=call)

    def test_source_id_matches_exact_c154_formula(self):
        data = {k: self.metadata[k] for k in ("source_sha256", "index_fingerprint", "source_path")}
        expected = "persisted-snapshot:" + hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(c155._source_id(self.metadata), expected)
        self.assertEqual(c155._source_id(dict(reversed(list(self.metadata.items())))), expected)

    def test_missing_source_metadata_is_invalid_input(self):
        for key in ("source_sha256", "source_path", "index_fingerprint"):
            with self.assertRaises(c155.InvalidInput):
                c155._source_id(dict(self.metadata, **{key: ""}))

    def test_source_hash_and_index_fingerprint_are_pinned(self):
        for key in ("source_sha256", "index_fingerprint"):
            with self.assertRaises(c155.InvalidInput):
                c155.load_binding(dict(self.metadata, **{key: "f" * 64}))

    def test_source_byte_mutation_is_rejected(self):
        (self.root / "a.json").write_bytes((self.root / "a.json").read_bytes() + b" ")
        with self.assertRaises(c155.InvalidInput):
            c155.load_binding(self.metadata)

    def test_real_adapter_resolves_all64_and_zero_is_not_missing(self):
        for i in range(64):
            ref = make_ref(self.binding, f"r{i}")
            r = c155.resolve_reference(ref, self.registry)
            self.assertEqual(r.status, "RESOLVED")
            self.assertEqual(r.value, i % 2)
            self.assertIsNotNone(r.evidence)
            self.assertEqual(r.evidence.key, f"r{i}")
            self.assertEqual((r.retrieval_calls, r.vectors_scored), (1, 64))

    def test_reversed_storage_resolves_same_values_under_different_source(self):
        b, _ = make_source(self.root, "b.json", reverse=True)
        self.assertNotEqual(self.binding.source_id, b.source_id)
        for i in range(64):
            r = c155.resolve_reference(make_ref(b, f"r{i}"), {b.source_id: b})
            self.assertEqual((r.status, r.value), ("RESOLVED", i % 2))

    def test_missing_binding_returns_no_payload_and_no_retrieval(self):
        with patch.object(self.binding.adapter, "retrieve") as spy:
            r = c155.resolve_reference(self.ref, {})
            self.assertEqual(r, c155.Resolution("SOURCE_UNBOUND"))
            spy.assert_not_called()

    def test_wrong_snapshot_is_rejected_before_payload_read(self):
        other, _ = make_source(self.root, "b.json", reverse=True)
        with patch.object(other.adapter, "retrieve") as spy:
            r = c155.resolve_reference(self.ref, {self.binding.source_id: other})
            self.assertEqual(r, c155.Resolution("SNAPSHOT_MISMATCH"))
            spy.assert_not_called()

    def test_clock_mismatch_rejects_without_retrieval(self):
        for p in (replace(self.ref.provenance, revision=2), replace(self.ref.provenance, evidence_time=2)):
            self.assertEqual(c155.resolve_reference(replace(self.ref, provenance=p), self.registry),
                             c155.Resolution("SNAPSHOT_MISMATCH"))

    def test_non_observed_reference_is_not_resolved(self):
        r = replace(self.ref, provenance=replace(self.ref.provenance, kind=ProvenanceKind.HYPOTHESIS))
        self.assertEqual(c155.resolve_reference(r, self.registry), c155.Resolution("NOT_OBSERVED"))

    def test_unbound_record_is_not_real_world_absence_or_zero(self):
        r = c155.resolve_reference(replace(self.ref, evidence_id="missing"), self.registry)
        self.assertEqual(r, c155.Resolution("RECORD_UNBOUND"))
        self.assertIsNone(r.value)

    def test_corrupt_handle_key_does_not_retarget_reference(self):
        handles = dict(self.binding.handles)
        handles["r0"] = replace(handles["r0"], key="r2")
        b = replace(self.binding, handles=handles)
        self.assertEqual(c155.resolve_reference(self.ref, {b.source_id: b}), c155.Resolution("IDENTITY_MISMATCH"))

    def test_actual_exact_search_miss_returns_none_without_fallback(self):
        handles = dict(self.binding.handles)
        handles["r0"] = replace(handles["r0"], structure=tuple([-1.0] + [0.0] * 63))
        b = replace(self.binding, handles=handles)
        r = c155.resolve_reference(self.ref, {b.source_id: b})
        self.assertEqual(r.status, "RECORD_NOT_FOUND")
        self.assertIsNone(r.value)
        self.assertEqual((r.retrieval_calls, r.vectors_scored), (1, 64))

    def test_wrong_key_with_same_zero_is_rejected(self):
        with self.mutated_response(evidence_changes=dict(key="r2")):
            r = c155.resolve_reference(self.ref, self.registry)
        self.assertEqual(r.status, "IDENTITY_MISMATCH")
        self.assertIsNone(r.value)
        self.assertIsNone(r.evidence)

    def test_wrong_domain_schema_operations_are_rejected(self):
        for changes in (dict(domain="bad"), dict(schema="bad"), dict(operations=("WRITE",))):
            with self.mutated_response(evidence_changes=changes):
                self.assertEqual(c155.resolve_reference(self.ref, self.registry).status, "IDENTITY_MISMATCH")

    def test_wrong_evidence_or_stats_provenance_is_rejected(self):
        for field in ("source_sha256", "index_fingerprint", "source_path"):
            with self.mutated_response(evidence_changes={field: "bad"}):
                self.assertEqual(c155.resolve_reference(self.ref, self.registry).status, "PROVENANCE_MISMATCH")
        for field in ("source_sha256", "index_fingerprint"):
            with self.mutated_response(stat_changes={field: "bad"}):
                self.assertEqual(c155.resolve_reference(self.ref, self.registry).status, "PROVENANCE_MISMATCH")

    def test_bool_nan_and_out_of_range_payloads_are_not_valid_bits(self):
        for value in (True, float("nan"), 2, None):
            with self.mutated_response(evidence_changes=dict(evidence_value=value)):
                r = c155.resolve_reference(self.ref, self.registry)
                self.assertEqual(r.status, "PAYLOAD_INVALID")
                self.assertIsNone(r.value)

    def test_cost_mismatch_is_explicit_not_silent_fallback(self):
        for changes in (dict(vectors_scored=63), dict(mode="bounded_lsh"), dict(records=63), dict(bucket_entries_visited=63)):
            with self.mutated_response(stat_changes=changes):
                self.assertEqual(c155.resolve_reference(self.ref, self.registry).status, "COST_MISMATCH")

    def test_duplicate_reads_preserve_state_clock_and_file_bytes(self):
        state = EvidenceState(1, 1, (self.ref,))
        before = c155._bytes(asdict(state))
        file_hash = c155._sha(self.root / "a.json")
        a = c155.resolve_reference(state.observations[0], self.registry)
        b = c155.resolve_reference(state.observations[0], self.registry)
        self.assertEqual(a, b)
        self.assertEqual(before, c155._bytes(asdict(state)))
        self.assertEqual(file_hash, c155._sha(self.root / "a.json"))
        self.assertEqual((state.evidence_time, state.revision), (1, 1))

    def test_registry_handles_are_readonly_and_have_no_expected_values(self):
        with self.assertRaises(TypeError):
            self.binding.handles["r0"] = self.binding.handles["r1"]
        self.assertNotIn("value", {f.name for f in fields(c155.Handle)})
        self.assertEqual(list(inspect.signature(c155.resolve_reference).parameters), ["ref", "registry"])

    def test_bad_measured_outcome_is_false_not_invalid_exception(self):
        r = c155.resolve_reference(self.ref, self.registry)
        self.assertTrue(c155._case_pass(r, "MATCHED", self.ref, 0, 64))
        self.assertFalse(c155._case_pass(replace(r, value=1), "MATCHED", self.ref, 0, 64))
        self.assertFalse(c155._case_pass(r, "WRONG_SNAPSHOT", self.ref, 0, 64))
        self.assertFalse(c155._case_pass(c155.Resolution("SOURCE_UNBOUND", 0), "MISSING_SOURCE", self.ref, 0, 64))

    def test_safe_artifact_paths_reject_parent_windows_and_absolute_paths(self):
        for name in ("../x", "a/x", "..\\x", "C:\\x", "/x", "", ".", ".."):
            with self.assertRaises(c155.InvalidInput):
                c155._safe_file(self.root, name)
        self.assertEqual(c155._safe_file(self.root, "s.json"), self.root / "s.json")

    def test_state_json_roundtrip_uses_real_v5_contract(self):
        state = EvidenceState(1, 1, (self.ref,))
        restored = c155._decode_state(json.loads(c155._bytes(asdict(state))))
        self.assertEqual(restored, state)
        data = json.loads(c155._bytes(asdict(state)))
        data["observations"].append(data["observations"][0])
        with self.assertRaises(ValueError):
            c155._decode_state(data)

    def test_stream_index_requires_all_unique_source_identities(self):
        records = [dict(seed=s, arm=a, order=o) for s in c155.SEEDS for a in c155.ARMS for o in c155.ORDERS]
        self.assertEqual(len(c155._index_streams(records)), 48)
        records[1] = records[0]
        with self.assertRaises(c155.InvalidInput):
            c155._index_streams(records)

    def test_gate_requires_counts_behavior_and_value_zero_coverage(self):
        s = dict(references=3072, resolver_calls=12288, status_counts=dict(RESOLVED=3072, SOURCE_UNBOUND=3072,
                 SNAPSHOT_MISMATCH=3072, RECORD_UNBOUND=3072), failed_cases=0, state_mutations=0,
                 retrieval_calls=3072, vectors_scored=196608, resolved_values={"0": 1536, "1": 1536})
        self.assertTrue(c155._gate(s))
        for field, value in (("failed_cases", 1), ("state_mutations", 1), ("vectors_scored", 0),
                             ("resolved_values", {"0": 0, "1": 3072})):
            self.assertFalse(c155._gate(dict(s, **{field: value})))


if __name__ == "__main__":
    unittest.main()
