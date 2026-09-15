from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks import gate_e_c157_controller_bridge as c


def stream():
    return dict(seed=20261721,arm="WITHIN_FACTOR",order="CANONICAL",split_id="S1",
                source_requests=1728,observations=6912,state_preserved=True)


def rows():
    s=stream()
    scope=f"C153|{s['seed']}|{s['arm']}|{s['order']}"
    result=[]
    for i in range(1728):
        outcomes=[]
        for j,(scenario,status) in enumerate(zip(c.SCENARIOS,c.STATUSES)):
            value=i%2 if j == 0 else None
            outcomes.append(dict(scenario=scenario,status=status,value=value,passed=True,control_input_passed=True,
                internal_step=8,internal_remaining=2,acquisition_remaining=2,retrieval_calls=int(j==0),vectors_scored=64*int(j==0),
                working_slots=[1.,1.,1. if j==0 else 0.,float(value) if j==0 else 0.,.125,-.25,.375,-.5],
                control_channels=[1.,1.,1. if j==0 else -1.,(1. if value else -1.) if j==0 else -1.]))
        result.append(dict(request_id=f"{scope}|{i}",scope_id=scope,
            reference=dict(evidence_id=f"record-{i%64}",provenance=dict(source_id="persisted-snapshot:unit-test",
                kind="observed",revision=1,evidence_time=1)),outcomes=outcomes))
    return result


def header():
    records=[]
    for seed in c.SOURCE_SEEDS:
        for arm in c.ARMS:
            for order in c.ORDERS:
                records.append(dict(stream(),seed=seed,arm=arm,order=order,split_id=f"S{(seed-20261721)//3+1}"))
    return dict(experiment_id=c.SOURCE_ID,commit_sha=c.SOURCE_COMMIT,status="PASS",diagnostic_execution_valid=True,
        production_runtime_modified=False,gate_e_candidate=False,records=records,
        summary=dict(source_streams=48,source_requests=82944,reobservation_calls=331776,status_counts={s:82944 for s in c.STATUSES},
            resolved_values={"0":34992,"1":47952},failed_cases=0,control_tensor_failures=0,state_mutations=0,old_working_mutations=0,
            retrieval_calls=82944,vectors_scored=5308416,internal_steps_consumed=331776,acquisition_budget_consumed=0,
            fresh_seed_count=0,training_steps=0,model_loading=False,actual_working_state_exercised=True,advance_internal_exercised=True,
            control_input_canonicalizer_exercised=True,controller_exercised=False,answer_exercised=False,
            production_state_commit=False,new_observation_committed=False,crash_recovery_exercised=False,
            request_reobservation_gate_passed=True))


def good_summary():
    return dict(source_views=331776,routers=3,decisions=1990656,action_errors=0,nonpositive_margins=0,input_mutations=0,
                weight_mutations=0,full_router_pass_count=3,actual_action_counts={"0":497664,"2":746496,"5":746496},
                matched_zero_correct=209952,matched_one_correct=287712,minimum_expected_margin=.5)


class V05C157ControllerBridgeTests(unittest.TestCase):
    def model(self):
        torch.manual_seed(314159)  # Never a registered formal seed.
        return ControlLaneActionRouter(ControlLaneRouterConfig(**c.CONFIG)).eval()

    def working(self):
        return torch.tensor([[[1.,1.,1.,-1.,.125,-.25,.375,-.5]],
                             [[1.,1.,1.,1.,.125,-.25,.375,-.5]],
                             [[1.,1.,-1.,-1.,.125,-.25,.375,-.5]]])

    def test_full_trace_decoding_keeps_zero_one_and_none_distinct(self):
        w,v,s,status,bits=c._decode_rows(rows(),stream())
        self.assertEqual(tuple(w.shape),(6912,1,8))
        self.assertEqual(v[:8],[0,None,None,None,1,None,None,None])
        self.assertEqual(status,{k:1728 for k in c.STATUSES})
        self.assertEqual(bits,{"0":864,"1":864})
        self.assertEqual(len(set(tuple(x) for x in w[:,0].tolist())),3)

    def test_trace_decoding_does_not_mutate_records(self):
        data=rows(); before=copy.deepcopy(data)
        c._decode_rows(data,stream())
        self.assertEqual(data,before)

    def test_trace_rejects_stale_payload_in_unresolved_view(self):
        data=rows(); data[0]["outcomes"][1]["value"]=1
        with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_trace_rejects_wrong_scope_and_duplicate_request(self):
        for mutation in ("scope","duplicate"):
            data=rows()
            if mutation=="scope": data[0]["scope_id"]="wrong"
            else: data[1]["request_id"]=data[0]["request_id"]
            with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_trace_rejects_nonobserved_or_future_reference(self):
        for field,value in (("kind","hypothesis"),("revision",2),("evidence_time",2)):
            data=rows(); data[0]["reference"]["provenance"][field]=value
            with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_trace_rejects_changed_raw_signed_budget_and_cost(self):
        for field,value in (("working_slots",[0.]*8),("control_channels",[1.]*4),
                            ("internal_remaining",3),("vectors_scored",0)):
            data=rows(); data[0]["outcomes"][0][field]=value
            with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_trace_rejects_missing_or_reordered_scenarios(self):
        for method in ("missing","reordered"):
            data=rows()
            if method=="missing": data[0]["outcomes"].pop()
            else: data[0]["outcomes"].reverse()
            with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_trace_rejects_bool_as_resolved_payload(self):
        data=rows(); data[0]["outcomes"][0]["value"]=False
        with self.assertRaises(c.InvalidInput): c._decode_rows(data,stream())

    def test_safe_file_rejects_directory_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../x","/x",r"C:\\x",r"..\x","", "."):
                with self.assertRaises(c.InvalidInput): c._safe_file(Path(directory),name)
            self.assertEqual(c._safe_file(Path(directory),"rows.jsonl"),Path(directory)/"rows.jsonl")

    def test_trace_loader_requires_exact_hash_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"rows.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows())+"\n",encoding="utf-8")
            metadata=dict(stream(),result_file=path.name,result_sha256=c._sha(path),serialized_bytes=path.stat().st_size)
            self.assertEqual(len(c._load_stream(root,metadata)[1]),6912)
            path.write_text(path.read_text(encoding="utf-8")+"\n",encoding="utf-8")
            with self.assertRaises(c.InvalidInput): c._load_stream(root,metadata)

    def test_header_accepts_exact_full_source_profile(self):
        c._header(header())

    def test_header_rejects_console_only_wrong_commit_and_duplicate_stream(self):
        for mode in ("records","commit","duplicate","counts"):
            data=header()
            if mode=="records": data["records"]="omitted; see summary.json"
            elif mode=="commit": data["commit_sha"]="wrong"
            elif mode=="duplicate": data["records"][1]=data["records"][0]
            else: data["summary"]["failed_cases"]=1
            with self.assertRaises(c.InvalidInput): c._header(data)

    def test_context_is_explicit_and_independent_of_evidence_value(self):
        w=self.working()
        for mode,expected in ((c.MODES[0],[-1.,1.,-1.,-1.]),(c.MODES[1],[-1.]*4)):
            working,context,op=c.router_inputs(w,mode)
            self.assertTrue(torch.equal(working,w))
            self.assertEqual(context[:,0,:4].tolist(),[expected]*3)
            self.assertEqual(op.tolist(),[0,0,0])
            self.assertEqual(op.dtype,torch.int64)
            self.assertEqual(context[:,:,4:].count_nonzero().item(),0)

    def test_router_inputs_preserve_source_and_no_oracle_interface(self):
        w=self.working(); before=w.clone()
        inputs=c.router_inputs(w,c.MODES[0]); inputs[0][0,0,0]=77
        self.assertTrue(torch.equal(w,before))
        self.assertEqual(list(inspect.signature(c.router_inputs).parameters),["working","mode"])
        self.assertNotIn("expected",inspect.signature(c.score_router).parameters)

    def test_invalid_input_shape_dtype_mode_and_nan_are_rejected(self):
        for w,mode in ((self.working().double(),c.MODES[0]),(torch.ones(2,8),c.MODES[0]),
                       (self.working(),"other"),(torch.full((3,1,8),float("nan")),c.MODES[0])):
            with self.assertRaises(ValueError): c.router_inputs(w,mode)

    def test_actual_production_router_batches_match_single_forward(self):
        model=self.model(); inputs=c.router_inputs(self.working(),c.MODES[0])
        before=c._fingerprint(model)
        a,n=c.score_router(model,inputs,chunk=1); b,m=c.score_router(model,inputs,chunk=8)
        np.testing.assert_allclose(a,b,atol=1e-6,rtol=1e-6)
        self.assertEqual((n,m),(3,1)); self.assertEqual(a.shape,(3,6))
        self.assertEqual(c._fingerprint(model),before)

    def test_scorer_does_not_override_wrong_raw_model_decisions(self):
        class AlwaysAnswer(torch.nn.Module):
            def forward(self,w,context,op):
                result=torch.zeros(len(w),6); result[:,0]=5
                return result
        logits,_=c.score_router(AlwaysAnswer(),c.router_inputs(self.working(),c.MODES[1]))
        result=c._assess(logits,[0,1,None],c.MODES[1])
        self.assertEqual(result["actions"].tolist(),[0,0,0])
        self.assertEqual(result["correct"].tolist(),[True,True,False])
        self.assertLess(result["margins"][-1],0)

    def test_scorer_rejects_nonfinite_or_wrong_shaped_output(self):
        for shape,nan in (((3,5),False),((3,6),True)):
            class Bad(torch.nn.Module):
                def forward(self,*args):
                    return torch.full(shape,float("nan") if nan else 0.)
            with self.assertRaises(RuntimeError): c.score_router(Bad(),c.router_inputs(self.working(),c.MODES[0]))
        with self.assertRaises(ValueError): c.score_router(self.model(),c.router_inputs(self.working(),c.MODES[0]),chunk=0)

    def test_assessment_uses_presence_not_payload_truthiness(self):
        for mode,expected in ((c.MODES[0],[0,0,2]),(c.MODES[1],[0,0,5])):
            logits=np.zeros((3,6),dtype=np.float32); logits[np.arange(3),expected]=2
            result=c._assess(logits,[0,1,None],mode)
            self.assertEqual(result["expected"].tolist(),expected)
            self.assertTrue(result["strict"].all())

    def test_assessment_tie_has_nonpositive_margin_even_with_correct_argmax(self):
        result=c._assess(np.zeros((1,6)),[0],c.MODES[0])
        self.assertTrue(result["correct"][0]); self.assertFalse(result["strict"][0])
        self.assertEqual(result["margins"][0],0.)

    def test_assessment_labels_cannot_modify_logits(self):
        logits=np.ones((3,6),dtype=np.float32); before=logits.copy()
        c._assess(logits,[0,1,None],c.MODES[0])
        np.testing.assert_array_equal(logits,before)
        for values in ([False,1,None],[3,1,None]):
            with self.assertRaises(ValueError): c._assess(logits,values,c.MODES[0])

    def test_reference_training_wrapper_freezes_without_validation_selection(self):
        calls=[]; model=self.model()
        def trainer(seed,device):
            calls.append((seed,str(device))); return model,.125
        frozen,loss=c._train_reference(314159,trainer)
        self.assertEqual(calls,[(314159,"cpu")]); self.assertIs(frozen,model)
        self.assertEqual(loss,.125); self.assertFalse(frozen.training)
        self.assertFalse(any(p.requires_grad for p in frozen.parameters()))

    def test_reference_wrapper_rejects_nonfinite_training(self):
        model=self.model()
        with self.assertRaises(RuntimeError): c._train_reference(314159,lambda *_:(model,float("nan")))

    def test_checkpoint_is_weights_only_reconstructible(self):
        model=self.model()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"router.pt"; meta=c._save_router(path,model,314159)
            saved=torch.load(path,weights_only=True,map_location="cpu")
            clone=ControlLaneActionRouter(ControlLaneRouterConfig(**saved["config"]))
            clone.load_state_dict(saved["state_dict"])
            self.assertEqual(c._fingerprint(model),c._fingerprint(clone))
            self.assertEqual(meta["sha256"],c._sha(path)); self.assertGreater(meta["serialized_bytes"],0)

    def test_fingerprint_detects_changed_controller_weights(self):
        model=self.model(); before=c._fingerprint(model)
        with torch.no_grad(): next(model.parameters()).add_(.01)
        self.assertNotEqual(before,c._fingerprint(model))

    def test_gate_counts_and_strict_margins_are_not_relaxed(self):
        good=good_summary(); self.assertTrue(c._gate(good))
        for field,value in (("action_errors",1),("nonpositive_margins",1),("input_mutations",1),
                            ("weight_mutations",1),("decisions",1),("matched_zero_correct",0),
                            ("minimum_expected_margin",0.),("minimum_expected_margin",float("nan"))):
            self.assertFalse(c._gate(dict(good,**{field:value})))

    def test_fresh_router_seeds_are_not_source_or_previous_router_seeds(self):
        self.assertEqual(c.ROUTER_SEEDS,(20261741,20261742,20261743))
        self.assertFalse(set(c.ROUTER_SEEDS)&set(c.SOURCE_SEEDS))
        self.assertFalse(set(c.ROUTER_SEEDS)&{20261341,20261342,20261343})
        self.assertEqual(c.CONFIG["action_count"],6)

    def test_all_source_views_are_scored_not_unique_pattern_cached(self):
        class Counting(torch.nn.Module):
            def __init__(self): super().__init__(); self.seen=0
            def forward(self,w,context,op):
                self.seen+=len(w); return torch.zeros(len(w),6)
        model=Counting(); w=self.working().repeat(10,1,1)
        logits,calls=c.score_router(model,c.router_inputs(w,c.MODES[0]),chunk=7)
        self.assertEqual(model.seen,30); self.assertEqual(calls,5); self.assertEqual(len(logits),30)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
