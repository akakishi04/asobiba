from __future__ import annotations

import copy
from dataclasses import replace
import inspect
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import torch

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter as Adapter
from fold_lm.v05.retrieval_content import SharedRetrievalContentHead as Head
from fold_lm.v05_benchmarks import gate_e_c152_persisted_bridge as c152


class V05C152PersistedBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.descriptors = ["red round metal", "blue square wood", "green triangular stone", "yellow hexagonal glass"]

    def snapshot(self, order="CANONICAL"):
        return c152._persist_snapshot(self.root/order, self.descriptors, order, Adapter)

    def checkpoint(self):
        torch.manual_seed(731)  # Toy helper initialization; not an experiment outcome.
        h=Head(**c152.CONFIG)
        record=dict(split_id="S1",seed=20261721,arms={})
        arm=c152.ARMS[1]; name=f"S1-seed-20261721-{arm.lower()}.pt"; path=self.root/name
        vocab=tuple(f"unit{i}" for i in range(49)); fingerprint=c152._fingerprint(h)
        payload=dict(state_dict=h.state_dict(),config=c152.CONFIG,vocabulary=list(vocab),
                     experiment_id=c152.SOURCE_ID,split_id="S1",auxiliary_candidate_scope=arm,
                     split_plan_sha256=c152.PLAN_SHA,training_composition="POOL_THEN_ENCODE",
                     inference_composition="ENCODE_THEN_POOL")
        torch.save(payload,path)
        record["arms"][arm]=dict(final_head_sha256=fingerprint,parameter_count=sum(p.numel() for p in h.parameters()),
             checkpoint=dict(path=str(path),sha256=c152._sha(path),serialized_bytes=path.stat().st_size,tensor_sha256=fingerprint))
        return h,record,arm,vocab,path,payload

    def test_snapshot_generation_is_deterministic_and_does_not_mutate(self):
        before=copy.deepcopy(self.descriptors)
        self.assertEqual(c152._snapshot_payloads(self.descriptors,"CANONICAL"),c152._snapshot_payloads(self.descriptors,"CANONICAL"))
        self.assertEqual(before,self.descriptors)

    def test_catalog_positions_move_but_identity_signatures_and_payloads_do_not(self):
        p,a=c152._snapshot_payloads(self.descriptors,"CANONICAL")
        q,b=c152._snapshot_payloads(self.descriptors,"PERMUTED")
        self.assertTrue(all(x["key"]!=y["key"] for x,y in zip(a,b)))
        self.assertEqual({x["key"]:x for x in a},{x["key"]:x for x in b})
        self.assertEqual({r["key"]:r for r in p["records"]},{r["key"]:r for r in q["records"]})
        self.assertNotEqual(p["records"],q["records"])

    def test_full64_actual_adapter_respects_each_handle_in_both_orderings(self):
        self.descriptors=[" ".join(p) for p in itertools.product(("red","blue","green","yellow"),
                           ("round","square","triangular","hexagonal"),("metal","wood","glass","stone"))]
        for order in c152.ORDERS:
            snap=self.snapshot(order)
            for handle in snap.catalog:
                r=c152._fetch_selected(snap.adapter,handle,snap.corpus_path)
                self.assertTrue(r["accepted"])
                self.assertEqual(r["returned_key"],handle["key"])
                self.assertEqual(r["evidence_value"],snap.values[handle["key"]])
                self.assertEqual(r["vectors_scored"],64)

    def test_existing_snapshot_directory_is_not_overwritten(self):
        self.snapshot()
        with self.assertRaises(FileExistsError): self.snapshot()

    def test_catalog_excludes_evidence_values_and_queries(self):
        _,entries=c152._snapshot_payloads(self.descriptors,"CANONICAL")
        self.assertTrue(all("evidence_value" not in e and "query" not in e and "expected_address" not in e for e in entries))
        self.assertEqual(list(inspect.signature(c152._snapshot_payloads).parameters),["descriptors","order"])

    def test_malformed_duplicate_or_empty_descriptors_rejected(self):
        for ds in ([],["a"],["a","a"],["","b"]):
            with self.assertRaises(ValueError): c152._snapshot_payloads(ds,"CANONICAL")
        with self.assertRaises(ValueError): c152._snapshot_payloads(self.descriptors,"other")

    def test_tampered_catalog_source_hash_is_rejected(self):
        s=self.snapshot(); obj=json.loads(s.catalog_path.read_text());obj["source_sha256"]="bad"
        s.catalog_path.write_bytes(c152._bytes(obj))
        with self.assertRaises(ValueError): c152._load_snapshot(s.catalog_path,s.corpus_path,Adapter)

    def test_catalog_record_handle_mismatch_is_rejected(self):
        s=self.snapshot(); obj=json.loads(s.catalog_path.read_text());obj["entries"][0]["structure"]=obj["entries"][1]["structure"]
        s.catalog_path.write_bytes(c152._bytes(obj))
        with self.assertRaises(ValueError): c152._load_snapshot(s.catalog_path,s.corpus_path,Adapter)

    def test_naive_position_as_address_negative_control_is_detected(self):
        s=self.snapshot("PERMUTED")
        for i,handle in enumerate(s.catalog):
            wrong=copy.deepcopy(handle);wrong["structure"]=[float(j==i) for j in range(4)]
            if wrong["structure"] != handle["structure"]:
                result=c152._fetch_selected(s.adapter,wrong,s.corpus_path)
                self.assertFalse(result["accepted"])
                self.assertNotEqual(result["returned_key"],wrong["key"])
                return
        self.fail("Negative-control fixture did not move an identity signature")

    def fake_return(self,s,handle,**changes):
        e,stats=s.adapter.retrieve(handle["structure"],handle["semantics"],schema=handle["schema"],exact=True)
        return SimpleNamespace(source_sha256=s.adapter.source_sha256,index_fingerprint=s.adapter.index_fingerprint,
                               record_count=s.adapter.record_count,retrieve=lambda *a,**k:(replace(e,**changes),stats))

    def test_same_boolean_payload_with_wrong_key_is_not_accepted(self):
        s=self.snapshot();h=s.catalog[0]
        fake=self.fake_return(s,h,key="wrong-key")
        r=c152._fetch_selected(fake,h,s.corpus_path)
        self.assertEqual(r["evidence_value"],s.values[h["key"]]);self.assertFalse(r["accepted"])

    def test_wrong_provenance_fields_rejected(self):
        s=self.snapshot();h=s.catalog[0]
        for field,bad in (("domain","x"),("schema","x"),("operations",("WRITE",)),
                          ("source_sha256","x"),("index_fingerprint","x"),("source_path","elsewhere")):
            with self.subTest(field=field):
                self.assertFalse(c152._fetch_selected(self.fake_return(s,h,**{field:bad}),h,s.corpus_path)["accepted"])

    def test_wrong_schema_produces_no_evidence(self):
        s=self.snapshot();h=copy.deepcopy(s.catalog[0]);h["schema"]="unknown"
        r=c152._fetch_selected(s.adapter,h,s.corpus_path)
        self.assertIsNone(r["returned_key"]);self.assertIsNone(r["evidence_value"]);self.assertFalse(r["accepted"])

    def test_missing_requested_record_is_not_replaced_by_a_different_record(self):
        s=self.snapshot();h=s.catalog[0];p=json.loads(s.corpus_path.read_text())
        p["records"]=[r for r in p["records"] if r["key"]!=h["key"]]
        missing=self.root/"missing.json";missing.write_bytes(c152._bytes(p))
        r=c152._fetch_selected(Adapter(missing),h,missing)
        self.assertFalse(r["accepted"]);self.assertIsNone(r["returned_key"])

    def test_zero_payload_is_real_evidence_not_a_miss(self):
        s=self.snapshot()
        h=next((h for h in s.catalog if s.values[h["key"]]==0),None)
        self.assertIsNotNone(h)
        r=c152._fetch_selected(s.adapter,h,s.corpus_path)
        self.assertTrue(r["accepted"]);self.assertEqual(r["evidence_value"],0)

    def test_fetch_interface_has_no_ground_truth_parameter(self):
        self.assertEqual(list(inspect.signature(c152._fetch_selected).parameters),["adapter","handle","corpus_path"])

    def test_replay_checks_predictions_rival_and_margins(self):
        a=[dict(correct=True,predicted_address=0,best_other_address=1,expected_score=.8,best_other_score=.6,expected_margin=.2)]
        c152._check_replay(a,copy.deepcopy(a))
        for key,value in (("predicted_address",1),("best_other_address",2),("expected_score",.9),("expected_margin",float("nan"))):
            b=copy.deepcopy(a);b[0][key]=value
            with self.assertRaises(ValueError): c152._check_replay(b,a)
        with self.assertRaises(ValueError): c152._check_replay([],a)

    def test_checkpoint_reconstructed_frozen_without_parameter_change(self):
        h,r,a,v,p,_=self.checkpoint()
        loaded,path=c152._load_head(self.root,r,a,v,Head,torch.device("cpu"))
        self.assertEqual(path,p);self.assertEqual(c152._fingerprint(h),c152._fingerprint(loaded))
        self.assertFalse(loaded.training);self.assertTrue(all(not p.requires_grad for p in loaded.parameters()))

    def test_checkpoint_tampering_is_rejected(self):
        _,r,a,v,p,_=self.checkpoint();p.write_bytes(p.read_bytes()+b"tamper")
        with self.assertRaises(ValueError): c152._load_head(self.root,r,a,v,Head,torch.device("cpu"))

    def test_checkpoint_wrong_metadata_or_vocabulary_rejected(self):
        _,r,a,v,_,_=self.checkpoint()
        with self.assertRaises(ValueError): c152._load_head(self.root,r,a,tuple(reversed(v)),Head,torch.device("cpu"))
        r["arms"][a]["final_head_sha256"]="bad"
        with self.assertRaises(ValueError): c152._load_head(self.root,r,a,v,Head,torch.device("cpu"))

    def test_checkpoint_filename_or_parent_traversal_cannot_redirect(self):
        _,r,a,v,_,_=self.checkpoint()
        for name in ("elsewhere.pt","../S1-seed-20261721-global_concept.pt"):
            r["arms"][a]["checkpoint"]["path"]=name
            with self.assertRaises(ValueError): c152._load_head(self.root,r,a,v,Head,torch.device("cpu"))

    def test_prior_header_rejects_wrong_experiment(self):
        with self.assertRaises(ValueError): c152._header(dict(experiment_id="C150",status="PASS"))

    def test_metrics_separate_provenance_from_semantic_correctness(self):
        s=self.snapshot();h=s.catalog[0];r=c152._fetch_selected(s.adapter,h,s.corpus_path)
        r.update(payload_correct=True,semantic_correct=False)
        m=c152._metrics([r]);self.assertEqual(m["accepted"],1);self.assertEqual(m["semantic_evidence_correct"],0)

    def test_strict_gate_keeps_baseline_errors_but_requires_global_correctness(self):
        perfect=dict(cases=20736,accepted=20736,selected_identity_preserved=20736,provenance_valid=20736,
                     cost_valid=20736,payload_matches_selected_record=20736,semantic_evidence_correct=20736)
        groups={a:{o:copy.deepcopy(perfect) for o in c152.ORDERS} for a in c152.ARMS}
        for o in c152.ORDERS: groups[c152.ARMS[0]][o]["semantic_evidence_correct"]=20727
        self.assertTrue(c152._bridge_passed(groups))
        groups[c152.ARMS[1]]["PERMUTED"]["semantic_evidence_correct"]-=1
        self.assertFalse(c152._bridge_passed(groups))

    def test_scope_reuses_both_arms_and_all_source_seeds(self):
        self.assertEqual(c152.SEEDS,tuple(range(20261721,20261733)))
        self.assertEqual(c152.ARMS,("WITHIN_FACTOR","GLOBAL_CONCEPT"))
        self.assertEqual(c152.ORDERS,("CANONICAL","PERMUTED"))


if __name__=="__main__": unittest.main()
