from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, replace
import inspect
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
import torch

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig, canonicalize_boolean_channels
from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind, WorkingState, BudgetState, advance_internal
from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as b


@dataclass(frozen=True)
class Evidence:
    key: str
    evidence_value: int
    source_sha256: str = "source"
    index_fingerprint: str = "index"
    source_path: str = "path"


@dataclass(frozen=True)
class Delivery:
    evidence: object


@dataclass(frozen=True)
class Inbox:
    entries: tuple = ()


class LogicalTestRouter(torch.nn.Module):
    """Explicit test double; never used to claim learned capability."""
    def forward(self, w, c, op):
        actions = torch.where(w[:,0,2] > 0, 0, torch.where(c[:,0,1] > 0, 2, 5))
        return torch.zeros(len(w),6).scatter_(1, actions[:,None], 10.)


class AlwaysRouter(torch.nn.Module):
    def __init__(self, action):
        super().__init__(); self.action = action
    def forward(self,w,c,op):
        return torch.zeros(len(w),6).scatter_(1, torch.full((len(w),1),self.action,dtype=torch.long),10.)


class RuntimeFixture:
    """Controlled callbacks isolate C158 orchestration; not the real adapter."""
    def __init__(self, ref, value):
        self.ref=ref;self.value=value;self.reads=0;self.fetches=0;self.admissions=0
        self.reject_projection=False;self.wrong_ref=False;self.corrupt_read=False
        self.resolver=None
    def empty_inbox(self):
        return Inbox()
    def reobserve(self,request,state,work,budget,registry,resolver):
        present=request.reference in state.observations
        value=self.value if present else None
        if present:
            self.reads+=1
        if self.corrupt_read and present:
            value=1-self.value
        slots=work.slots.copy();slots[0,2:4]=(1,float(value)) if present else (0,0)
        state2,work2,budget2=advance_internal(state,work,budget,slots=slots)
        return SimpleNamespace(value=value,reference=request.reference if present else None,
            status="RESOLVED" if present else "REFERENCE_UNBOUND",evidence_state=state2,working=work2,budget=budget2)
    def control_inputs(self,observations):
        raw=torch.tensor(np.stack([o.working.slots for o in observations]),dtype=torch.float32)
        return canonicalize_boolean_channels(raw,(1,2,3),threshold=.5)
    def fetch(self,request,registry):
        self.fetches+=1;self.reads+=1
        return Delivery(Evidence(request.key,self.value))
    def admit(self,state,request,delivery):
        self.admissions+=1
        if delivery.evidence is None:
            return "MISSING",state
        return "COMMITTED",Inbox(state.entries+(SimpleNamespace(reference=self.ref),))
    def entry_ref(self,entry):
        return replace(entry.reference,evidence_id="wrong") if self.wrong_ref else entry.reference
    def project(self,state,ref):
        if self.reject_projection:
            return "PROVENANCE_CONFLICT",state
        if ref in state.observations:
            return "ALREADY_PRESENT",state
        return "ADDED",replace(state,observations=state.observations+(ref,))


def valid_summary():
    s=dict(source_requests=82944,source_views=331776,unique_working_inputs=3,unique_working_context_inputs=6,
        routers=3,fresh_router_seeds=list(b.ROUTER_SEEDS),router_train_steps_each=900,decisions=1990656,forward_batches=576,
        action_errors=0,nonpositive_margins=0,input_mutations=0,weight_mutations=0,matched_zero_correct=209952,
        matched_one_correct=287712,actual_action_counts={"0":497664,"2":746496,"5":746496},full_router_pass_count=3,
        controller_bridge_gate_passed=True,learned_controller_exercised=True,answer_generation_exercised=False,
        live_reobservation_exercised=False,retrieval_exercised=False,action_execution_exercised=False,
        production_state_commit=False,minimum_expected_margin=5.344475269317627)
    return dict(experiment_id="C157-v5e-learned-controller-readback-bridge",commit_sha=b.C157_COMMIT,status="PASS",
        diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,C156_summary_sha256=b.C156_SHA,
        config=b.CONFIG.copy(),summary=s,records=[dict(seed=seed,weights_preserved=True,errors=0,
            nonpositive_margins=0,optimizer_steps=900,streams=[{} for _ in range(48)]) for seed in b.ROUTER_SEEDS])


class V05C158LiveRecoveryTests(unittest.TestCase):
    def setup_case(self,value=0):
        ref=EvidenceRef("record-0",Provenance("persisted-snapshot:source",ProvenanceKind.OBSERVED,1,1))
        other=replace(ref,evidence_id="record-other")
        state=EvidenceState(1,1,(ref,other))
        req=SimpleNamespace(request_id="scope|query",scope_id="scope",reference=ref)
        admit=SimpleNamespace(request_id=req.request_id,scope_id=req.scope_id,key=ref.evidence_id)
        return ref,state,req,admit,RuntimeFixture(ref,value)

    def exercise(self,scenario,value=0,model=None,configure=None):
        ref,full,req,admit,ops=self.setup_case(value)
        if configure: configure(ops)
        state=full if scenario=="WARM_PRESENT" else replace(full,observations=full.observations[1:])
        work=WorkingState(1,7,[[1,1,1,1-value,.125,-.25,.375,-.5]])
        budget=BudgetState(3,0 if scenario=="COLD_BUDGET_EXHAUSTED" else 1)
        permission=b.Permission(scenario!="COLD_PERMISSION_DENIED")
        deliver=(lambda d:replace(d,evidence=None)) if scenario=="COLD_MISSING_DELIVERY" else (lambda d:d)
        result=b.cycle(model or LogicalTestRouter(),req,admit,state,work,budget,{},permission,ops,deliver)
        result.update(retrieval_calls=ops.reads,vectors_scored=ops.reads*64)
        judged=b._assess_episode(result,scenario,ref,full,value,budget)
        return result,judged,ops

    def test_warm_zero_answers_without_acquisition(self):
        r,j,o=self.exercise("WARM_PRESENT",0)
        self.assertTrue(j["passed"],j);self.assertEqual(r["final_value"],0);self.assertEqual(o.fetches,0)

    def test_warm_one_answers_without_acquisition(self):
        r,j,o=self.exercise("WARM_PRESENT",1)
        self.assertTrue(j["passed"],j);self.assertEqual(r["final_value"],1);self.assertEqual(o.fetches,0)

    def test_cold_zero_acquires_publishes_rereads_then_answers(self):
        r,j,o=self.exercise("COLD_RECOVER",0)
        self.assertTrue(j["passed"],j);self.assertEqual([s["action"] for s in r["steps"]],[2,0]);self.assertEqual(o.reads,2)

    def test_cold_one_acquires_publishes_rereads_then_answers(self):
        r,j,o=self.exercise("COLD_RECOVER",1)
        self.assertTrue(j["passed"],j);self.assertEqual(r["publications"],1);self.assertEqual(r["inbox_entries"],1)

    def test_missing_delivery_discards_real_response_without_false_payload(self):
        r,j,o=self.exercise("COLD_MISSING_DELIVERY",0)
        self.assertTrue(j["passed"],j);self.assertEqual(o.fetches,1);self.assertIsNone(r["final_value"])
        self.assertEqual(r["steps"][0]["fetched"]["evidence_value"],0)

    def test_permission_denial_keeps_budget_and_makes_no_fetch(self):
        r,j,o=self.exercise("COLD_PERMISSION_DENIED",1)
        self.assertTrue(j["passed"],j);self.assertEqual(o.fetches,0);self.assertEqual(r["final_budget"]["acquisitions_remaining"],1)

    def test_exhausted_budget_makes_no_fetch(self):
        r,j,o=self.exercise("COLD_BUDGET_EXHAUSTED",1)
        self.assertTrue(j["passed"],j);self.assertEqual(o.fetches,0);self.assertEqual(r["steps"][0]["authority"],"BUDGET_EXHAUSTED")

    def test_wrong_answer_is_retained_as_valid_behavioral_failure(self):
        r,j,o=self.exercise("COLD_RECOVER",model=AlwaysRouter(0))
        self.assertFalse(j["passed"]);self.assertEqual(r["steps"][0]["action"],0);self.assertEqual(o.fetches,0)

    def test_wrong_stop_is_not_overridden(self):
        r,j,o=self.exercise("COLD_RECOVER",model=AlwaysRouter(5))
        self.assertFalse(j["passed"]);self.assertEqual(r["terminal"],"STOP_UNRESOLVED");self.assertEqual(o.fetches,0)

    def test_other_action_does_not_trigger_retrieval(self):
        r,j,o=self.exercise("COLD_RECOVER",model=AlwaysRouter(3))
        self.assertFalse(j["passed"]);self.assertEqual(r["terminal"],"UNEXPECTED_ACTION");self.assertEqual(o.fetches,0)

    def test_repeated_retrieve_is_bounded_and_never_reexecutes(self):
        r,j,o=self.exercise("COLD_RECOVER",model=AlwaysRouter(2))
        self.assertFalse(j["passed"]);self.assertEqual(r["terminal"],"DECISION_LIMIT")
        self.assertEqual(len(r["steps"]),3);self.assertEqual(o.fetches,1);self.assertEqual(r["steps"][1]["authority"],"ATTEMPT_LIMIT")

    def test_projection_failure_does_not_partially_publish_inbox(self):
        r,j,o=self.exercise("COLD_RECOVER",configure=lambda x:setattr(x,"reject_projection",True))
        self.assertFalse(j["passed"]);self.assertEqual(r["inbox_entries"],0);self.assertEqual(r["publications"],0)

    def test_wrong_projected_identity_is_not_adopted(self):
        r,j,o=self.exercise("COLD_RECOVER",configure=lambda x:setattr(x,"wrong_ref",True))
        self.assertFalse(j["passed"]);self.assertEqual(r["inbox_entries"],0)
        self.assertNotIn("wrong",[q["evidence_id"] for q in r["final_evidence"]["observations"]])

    def test_corrupt_live_read_is_valid_failed_measurement(self):
        r,j,o=self.exercise("WARM_PRESENT",configure=lambda x:setattr(x,"corrupt_read",True))
        self.assertFalse(j["passed"]);self.assertFalse(j["checks"]["value"])

    def test_state_and_working_inputs_stay_immutable(self):
        for scenario in b.SCENARIOS:
            r,j,o=self.exercise(scenario)
            self.assertTrue(r["original_state_preserved"]);self.assertTrue(r["original_working_preserved"])

    def test_bound_request_mismatch_is_invalid_before_callbacks(self):
        ref,state,req,admit,ops=self.setup_case();admit.key="other"
        with self.assertRaises(ValueError):
            b.cycle(LogicalTestRouter(),req,admit,state,WorkingState(1,7,[[0]*8]),BudgetState(3,1),{},b.Permission(True),ops,lambda x:x)
        self.assertEqual(ops.reads,0)

    def test_minimum_internal_budget_checked_before_read(self):
        ref,state,req,admit,ops=self.setup_case()
        with self.assertRaises(ValueError):
            b.cycle(LogicalTestRouter(),req,admit,state,WorkingState(1,7,[[0]*8]),BudgetState(2,1),{},b.Permission(True),ops,lambda x:x)
        self.assertEqual(ops.reads,0)

    def test_permission_does_not_accept_integer_as_boolean(self):
        with self.assertRaises(TypeError): b.Permission(1)

    def test_cycle_has_no_expected_value_or_scenario_interface(self):
        params=inspect.signature(b.cycle).parameters
        for name in ("expected_value","scenario","expected_action","semantic_label"):
            self.assertNotIn(name,params)

    def test_actual_production_controller_forward_matches_decision(self):
        torch.manual_seed(1234)
        model=ControlLaneActionRouter(ControlLaneRouterConfig(**b.CONFIG)).eval()
        ref,state,req,admit,ops=self.setup_case()
        o=ops.reobserve(req,state,WorkingState(1,7,[[1,1,1,1,.125,-.25,.375,-.5]]),BudgetState(3,1),{},None)
        action,logits,mutated=b._decision(model,o,True,ops)
        w=ops.control_inputs([o]);c=torch.zeros_like(w);c[0,0,:4]=torch.tensor([0,1,0,0])
        c=canonicalize_boolean_channels(c,(0,1,2,3),threshold=.5)
        with torch.inference_mode(): expected=model(w,c,torch.zeros(1,dtype=torch.long))
        self.assertEqual(logits,expected[0].tolist());self.assertEqual(action,int(expected.argmax()));self.assertFalse(mutated)

    def test_nonfinite_controller_output_is_execution_error(self):
        class Bad(torch.nn.Module):
            def forward(self,*args):return torch.full((1,6),float("nan"))
        with self.assertRaises(RuntimeError):self.exercise("WARM_PRESENT",model=Bad())

    def test_tied_logits_fail_strict_margin(self):
        class Tie(torch.nn.Module):
            def forward(self,*args):return torch.zeros((1,6))
        r,j,o=self.exercise("WARM_PRESENT",model=Tie())
        self.assertEqual(r["steps"][0]["action"],0);self.assertFalse(j["passed"]);self.assertEqual(j["margins"],[0.0])

    def test_measured_cost_mismatch_does_not_become_invalid(self):
        r,j,o=self.exercise("COLD_RECOVER")
        r["vectors_scored"]-=1
        ref,full,req,admit,ops=self.setup_case()
        self.assertFalse(b._assess_episode(r,"COLD_RECOVER",ref,full,0,BudgetState(3,1))["passed"])

    def test_meter_counts_underlying_calls_and_delegates_identity(self):
        a=SimpleNamespace(source_sha256="a",retrieve=lambda *x,**k:(None,{"vectors_scored":64}))
        m=b.MeteredAdapter(a);m.retrieve("x");m.retrieve("y")
        self.assertEqual((m.calls,m.vectors),(2,128));self.assertEqual(m.source_sha256,"a")

    def test_bad_meter_scan_field_is_rejected(self):
        a=SimpleNamespace(retrieve=lambda *x,**k:(None,{"vectors_scored":True}))
        with self.assertRaises(RuntimeError):b.MeteredAdapter(a).retrieve()

    def test_header_validates_exact_c157_profile(self):
        b._header(valid_summary())
        for key,value in (("records","omitted"),("status","FAIL"),("commit_sha","wrong")):
            d=valid_summary();d[key]=value
            with self.assertRaises(b.InvalidInput):b._header(d)

    def test_header_rejects_counts_seeds_and_margins(self):
        for key,value in (("decisions",6),("fresh_router_seeds",[1,2,3]),("minimum_expected_margin",float("nan"))):
            d=valid_summary();d["summary"][key]=value
            with self.assertRaises(b.InvalidInput):b._header(d)

    def make_checkpoint(self,root):
        torch.manual_seed(5678)
        model=ControlLaneActionRouter(ControlLaneRouterConfig(**b.CONFIG))
        path=root/f"controller-{b.ROUTER_SEEDS[0]}.pt"
        torch.save(dict(config=b.CONFIG,state_dict=model.state_dict(),seed=b.ROUTER_SEEDS[0],recipe="C113._train_router"),path)
        row=dict(seed=b.ROUTER_SEEDS[0],checkpoint=dict(file=path.name,sha256=b._sha(path),state_sha256=b._fingerprint(model),serialized_bytes=path.stat().st_size))
        return model,path,row

    def test_saved_router_is_frozen_and_weights_identical(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model,path,row=self.make_checkpoint(root);loaded,_=b._load_router(root,row)
            self.assertEqual(b._fingerprint(loaded),b._fingerprint(model));self.assertFalse(loaded.training)
            self.assertTrue(all(not p.requires_grad for p in loaded.parameters()))

    def test_checkpoint_tamper_and_unsafe_names_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model,path,row=self.make_checkpoint(root)
            changed=copy.deepcopy(row);changed["checkpoint"]["file"]="../outside.pt"
            with self.assertRaises(b.InvalidInput):b._load_router(root,changed)
            path.write_bytes(path.read_bytes()+b"x")
            with self.assertRaises(b.InvalidInput):b._load_router(root,row)

    def test_checkpoint_wrong_config_is_rejected_after_rehash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model,path,row=self.make_checkpoint(root)
            p=torch.load(path,weights_only=True);p["recipe"]="wrong";torch.save(p,path)
            row["checkpoint"].update(sha256=b._sha(path),serialized_bytes=path.stat().st_size)
            with self.assertRaises(b.InvalidInput):b._load_router(root,row)

    def make_streams(self):
        streams=[]
        for order in ("CANONICAL","PERMUTED"):
            refs=tuple(EvidenceRef(f"r{i:02}",Provenance("persisted-snapshot:"+order,ProvenanceKind.OBSERVED,1,1)) for i in range(64))
            state=EvidenceState(1,1,refs)
            for arm in ("WITHIN_FACTOR","GLOBAL_CONCEPT"):
                reqs={r.evidence_id:dict(request_id=arm+"|"+r.evidence_id) for r in refs}
                streams.append((dict(order=order,arm=arm,seed=1),state,{r.evidence_id:i%2 for i,r in enumerate(refs)},reqs))
        return streams

    def test_plan_is_identity_only_deterministic_and_covers_both_snapshots(self):
        streams=self.make_streams();before=copy.deepcopy(streams)
        a=b._plan(streams);z=b._plan(list(reversed(streams)))
        self.assertEqual(a,z);self.assertEqual(len(a),128);self.assertEqual(streams,before)
        self.assertEqual([x[0] for x in a].count("CANONICAL"),64)

    def test_plan_conflicting_record_value_is_invalid(self):
        streams=self.make_streams();streams[1][2]["r00"]=99
        with self.assertRaises(b.InvalidInput):b._plan(streams)

    def test_safe_file_blocks_windows_and_posix_escape(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("../a","x/y","x\\y","C:\\a",".."):
                with self.assertRaises(b.InvalidInput):b._safe_file(Path(d),name)

    def test_gate_requires_every_registered_count_and_both_values(self):
        s=dict(episodes=1920,failed_episodes=0,controller_decisions=3456,retrieval_calls=1536,vectors_scored=98304,
            executed_acquisitions=768,published_references=384,internal_steps_consumed=3456,
            terminal_counts={"ANSWER_ACTION":768,"STOP_UNRESOLVED":1152},resolved_values={"0":324,"1":444},
            full_router_pass_count=3,weight_mutations=0,replay_decisions=1990656)
        self.assertTrue(b._gate(s))
        for key in ("episodes","failed_episodes","retrieval_calls","full_router_pass_count","weight_mutations"):
            bad=dict(s);bad[key]+=1;self.assertFalse(b._gate(bad))

    def test_no_formal_seeds_are_trained_by_this_experiment(self):
        self.assertEqual(b.ROUTER_SEEDS,(20261741,20261742,20261743))
        self.assertEqual(b.MAX_DECISIONS,3)
        source=inspect.getsource(b.run)
        self.assertNotIn("_train_router",source);self.assertNotIn(".backward(",source)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
