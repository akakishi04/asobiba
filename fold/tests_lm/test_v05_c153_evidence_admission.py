from __future__ import annotations

from dataclasses import asdict, FrozenInstanceError, replace
import inspect
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter, RetrievalEvidence
from fold_lm.v05_benchmarks import gate_e_c153_evidence_admission as c


def sample(value=0):
    r = c.Request("request-1", "scope-1", "k0", "test", "v1", ("READ_EVIDENCE",), "source", "index", "/snapshot")
    e = RetrievalEvidence(r.key, r.domain, r.schema, value, r.operations, r.index_fingerprint, r.source_sha256, r.source_path)
    stats = dict(mode="exact", records=64, vectors_scored=64, bucket_entries_visited=64,
                 source_sha256=r.source_sha256, index_fingerprint=r.index_fingerprint)
    return r, c.Delivery(r.request_id, r.scope_id, 1, 1, e, stats)


def header():
    summary = dict(loaded_heads=24, fresh_seed_count=0, additional_training_steps=0,
                   full_replay_cases=41472, original12_replay_cases=288, corpus_orders=list(c.ORDERS),
                   retrieval_calls=82944, candidates_per_call=64, full_replay_match_rate=1.0,
                   catalog_order_selection_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                   evaluation_oov_count=0, persisted_retrieval_exercised=True, provenance_validation_exercised=True,
                   controller_exercised=False, evidence_commit_exercised=False, answer_exercised=False,
                   exact_scan_declared=True, inference_oracle_used=False, persisted_bridge_gate_passed=True)
    return dict(experiment_id=c.PRIOR_ID, commit_sha=c.PRIOR_COMMIT, status="PASS",
                diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                C151_summary_sha256=c.C151_SHA, summary=summary,
                records=[dict(seed=s, arm=a) for s in range(20261721,20261733) for a in c.ARMS])


class V05C153EvidenceAdmissionTests(unittest.TestCase):
    def assert_rejected(self, expected, r, d):
        initial = c.State()
        status, state = c.admit(initial, r, d)
        self.assertEqual(status, expected)
        self.assertIs(state, initial)
        self.assertFalse(state.processed)

    def test_zero_is_committed_as_evidence(self):
        r,d = sample(0)
        status,state = c.admit(c.State(),r,d)
        self.assertEqual(status,"COMMITTED")
        self.assertEqual(state.entries,(c.Entry(r,0),))
        self.assertEqual(state.processed,frozenset((r.request_id,)))

    def test_one_and_full_provenance_are_committed(self):
        r,d = sample(1)
        _,state = c.admit(c.State(),r,d)
        self.assertEqual(asdict(state.entries[0]),dict(request=asdict(r),value=1))

    def test_duplicate_preserves_exact_state_object(self):
        r,d=sample();_,state=c.admit(c.State(),r,d)
        status,after=c.admit(state,r,d)
        self.assertEqual(status,"DUPLICATE");self.assertIs(after,state)

    def test_rejection_does_not_consume_request_and_valid_retry_works(self):
        r,d=sample();initial=c.State()
        _,after=c.admit(initial,r,replace(d,evidence=None))
        status,final=c.admit(after,r,d)
        self.assertIs(after,initial);self.assertEqual(status,"COMMITTED")
        self.assertEqual(len(final.entries),1)

    def test_missing_delivery_is_not_a_zero_payload(self):
        r,d=sample(0);self.assert_rejected("MISSING",r,replace(d,evidence=None))

    def test_wrong_key_with_same_bit_is_rejected(self):
        r,d=sample();self.assert_rejected("WRONG_KEY",r,replace(d,evidence=replace(d.evidence,key="k1")))

    def test_wrong_domain_schema_or_operation_is_rejected(self):
        r,d=sample()
        for field,value in (("domain","other"),("schema","other"),("operations",("WRITE",))):
            with self.subTest(field=field):
                self.assert_rejected("WRONG_METADATA",r,replace(d,evidence=replace(d.evidence,**{field:value})))

    def test_wrong_source_hash_fingerprint_or_path_is_rejected(self):
        r,d=sample()
        for field in ("source_sha256","index_fingerprint","source_path"):
            with self.subTest(field=field):
                self.assert_rejected("WRONG_SOURCE",r,replace(d,evidence=replace(d.evidence,**{field:"other"})))

    def test_stats_provenance_is_also_checked(self):
        r,d=sample()
        for field in ("source_sha256","index_fingerprint"):
            self.assert_rejected("WRONG_SOURCE",r,replace(d,stats={**d.stats,field:"other"}))

    def test_scan_accounting_must_match_declared_exact_reference(self):
        r,d=sample()
        for field,value in (("mode","bounded_lsh"),("records",63),("vectors_scored",0),("bucket_entries_visited",63)):
            self.assert_rejected("WRONG_COST",r,replace(d,stats={**d.stats,field:value}))

    def test_wrong_scope_and_request_do_not_write(self):
        r,d=sample()
        self.assert_rejected("WRONG_SCOPE",r,replace(d,scope_id="other"))
        self.assert_rejected("WRONG_REQUEST",r,replace(d,request_id="other"))

    def test_stale_epoch_or_provider_generation_does_not_write(self):
        r,d=sample()
        for field in ("request_epoch","provider_generation"):
            self.assert_rejected("STALE_REQUEST",r,replace(d,**{field:0}))

    def test_invalid_payload_type_or_value_is_rejected(self):
        r,d=sample()
        for value in (True,False,0.0,2,-1,None):
            self.assert_rejected("INVALID_PAYLOAD",r,replace(d,evidence=replace(d.evidence,evidence_value=value)))

    def test_same_record_is_allowed_in_distinct_requests(self):
        r,d=sample();_,state=c.admit(c.State(),r,d)
        r2=replace(r,request_id="request-2");d2=replace(d,request_id=r2.request_id)
        status,after=c.admit(state,r2,d2)
        self.assertEqual(status,"COMMITTED");self.assertEqual(len(after.entries),2)
        self.assertEqual(len(state.entries),1)

    def test_entry_and_state_are_immutable(self):
        r,d=sample();_,state=c.admit(c.State(),r,d)
        with self.assertRaises(FrozenInstanceError): state.entries[0].value=1
        with self.assertRaises(FrozenInstanceError): state.entries=()
        d.stats["source_sha256"]="changed-after-delivery"
        self.assertEqual(state.entries[0].request.source_sha256,"source")

    def test_seven_step_protocol_preserves_initial_state(self):
        r,d=sample();initial=c.State();final,m=c._exercise(initial,r,d)
        self.assertTrue(m["passed"]);self.assertEqual(tuple(m["statuses"]),c.EXPECTED)
        self.assertFalse(initial.entries);self.assertEqual(len(final.entries),1)

    def test_unexpected_real_miss_fails_protocol_not_false_success(self):
        r,d=sample();initial=c.State();after,m=c._exercise(initial,r,replace(d,evidence=None))
        self.assertFalse(m["passed"]);self.assertIs(initial,after)

    def test_no_semantic_truth_interface(self):
        self.assertEqual(tuple(inspect.signature(c.admit).parameters),("state","request","delivery"))
        self.assertEqual(tuple(inspect.signature(c._fetch).parameters),("request","handle","adapter"))

    def test_header_accepts_registered_identity(self):
        c._header(header())

    def test_header_rejects_wrong_id_console_only_duplicate_or_wrong_order(self):
        for field,value in (("experiment_id","wrong"),("records","omitted"),("status","FAIL")):
            data=header();data[field]=value
            with self.assertRaises(ValueError): c._header(data)
        data=header();data["records"][1]=data["records"][0]
        with self.assertRaises(ValueError): c._header(data)

    def test_trace_requires_full_manifest_before_reaggregation(self):
        with self.assertRaisesRegex(ValueError,"Manifest coverage"):
            c._validate_trace(header(),dict(queries=[],descriptors=[]),{},None)

    def test_gate_requires_all_rejections_commits_and_preserved_semantic_errors(self):
        groups={a:{o:dict(cases=20736,passed=20736,committed_entries=20736,
                          semantic_correct=20727 if a==c.ARMS[0] else 20736,vectors_scored=1327104,
                          status_counts={s:20736 for s in c.EXPECTED}) for o in c.ORDERS} for a in c.ARMS}
        self.assertTrue(c._passed(groups))
        groups[c.ARMS[0]][c.ORDERS[0]]["semantic_correct"]=20736
        self.assertFalse(c._passed(groups))

    def test_actual_adapter_to_inbox_over_64_records_and_two_storage_orders(self):
        records=[dict(key=f"key-{i}",domain="test",schema="v1",structure=[float(i==j) for j in range(64)],
                      semantics=[1.,0.],operations=["READ_EVIDENCE"],evidence_value=i%2) for i in range(64)]
        with tempfile.TemporaryDirectory() as directory:
            for order,rows in enumerate((records,list(reversed(records)))):
                path=Path(directory)/f"{order}.json";path.write_bytes(c._bytes(dict(schema_version=1,records=rows)))
                adapter=PersistedStructuralRetrievalAdapter(path)
                snapshot=SimpleNamespace(adapter=adapter,corpus_path=path)
                state=c.State()
                for i in range(64):
                    handle={k:v for k,v in records[i].items() if k!="evidence_value"}
                    request=c._request(f"{order}/{i}",f"scope{order}",handle,snapshot)
                    good=c._fetch(request,handle,adapter)
                    state,m=c._exercise(state,request,good)
                    self.assertTrue(m["passed"])
                    self.assertEqual(state.entries[-1].value,i%2)
                self.assertEqual(len(state.entries),64)
                self.assertEqual(len(state.processed),64)

    def test_snapshot_serializes_actual_entries_and_claims(self):
        r,d=sample();_,state=c.admit(c.State(),r,d)
        payload=dict(entries=[asdict(e) for e in state.entries],processed=sorted(state.processed))
        recovered=json.loads(c._bytes(payload))
        self.assertEqual(recovered["entries"][0]["value"],0)
        self.assertEqual(recovered["entries"][0]["request"]["key"],r.key)
        self.assertEqual(recovered["processed"],[r.request_id])


if __name__=="__main__": unittest.main()
