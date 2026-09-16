"""C160 helpers; controlled dependencies, not the formal artifact-chain experiment."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

import numpy as np
import torch

from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as c


@dataclass(frozen=True)
class Provenance:
    source_id: str
    kind: str
    revision: int
    evidence_time: int


@dataclass(frozen=True)
class Ref:
    evidence_id: str
    provenance: Provenance


@dataclass(frozen=True)
class State:
    evidence_time: int
    revision: int
    observations: tuple


@dataclass(frozen=True)
class Work:
    evidence_time: int
    internal_step: int
    slots: object


@dataclass(frozen=True)
class Budget:
    internal_steps_remaining: int
    acquisitions_remaining: int


@dataclass(frozen=True)
class Output:
    status: str
    reason: str
    value: int | None
    request_id: str
    scope_id: str
    record_key: str | None
    source_id: str | None
    evidence_time: int | None
    revision: int | None


def output(value=0, key="selected"):
    return Output("ANSWERED","OBSERVED_VALUE",value,"scope|q","scope",key,"persisted-snapshot:test",1,1)


def profile():
    n=c.EPISODES
    return dict(episodes=n,failed_episodes=0,ranking_queries=n,candidate_scores=64*n,controller_decisions=2*n,acquisitions=n,publications=n,
        retrieval_calls=2*n,vectors_scored=128*n,answered=n,weight_mutations=0,output_mutations=0,
        serialization_failures=0,router_episodes={str(s):n//3 for s in c.ROUTER_SEEDS},
        ranker_replay_cases=41472,original12_replay_cases=288,c159_replay_calls=6528,minimum_controller_margin=5.,
        arms={a:{o:dict(cases=20736,binding_correct=20736,semantic_correct=20727 if a==c.ARMS[0] else 20736)
              for o in c.ORDERS} for a in c.ARMS})


def old_and_header():
    old=NS(SOURCE_SHA="old",_gate=lambda s:s.get("count_gate") is True)
    s=dict(count_gate=True,terminal_result_gate_passed=True,training_steps=0,fresh_seed_count=0,
        base_reasons={"OBSERVED_VALUE":768,"MISSING_DELIVERY":384,"PERMISSION_DENIED":384,"BUDGET_EXHAUSTED":384})
    s.update({k:False for k in ("model_loading","controller_exercised","retrieval_exercised",
            "live_cycle_replayed","answer_generation_exercised","production_state_commit")})
    return old,dict(experiment_id="C159-v5e-evidence-bound-terminal-result",commit_sha=c.C159_COMMIT,
        status="PASS",diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
        C158_summary_sha256="old",summary=s,records=[dict(router_seed=s) for s in c.ROUTER_SEEDS])


class V05C160LiveQueryResultTests(unittest.TestCase):
    def setUp(self):
        self.ref=Ref("selected",Provenance("persisted-snapshot:test","observed",1,1))

    def test_json_is_deterministic_and_nan_is_rejected(self):
        self.assertEqual(c.blob({"b":2,"a":1}),c.blob({"a":1,"b":2}))
        with self.assertRaises(ValueError):c.blob({"v":float("nan")})

    def test_ancestor_selects_summary_by_hash_not_iteration_order(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"summary.json"
            self.assertEqual(c.ancestor({str(p):"h",str(Path(d)/"x.pt"):"h"},"h"),p.resolve())

    def test_ancestor_missing_and_ambiguous_are_invalid(self):
        for paths in ({}, {"a/summary.json":"h","b/summary.json":"h"}):
            with self.assertRaises(c.InvalidInput):c.ancestor(paths,"h")

    def test_file_hash_changes_with_bytes(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"x";p.write_bytes(b"a");a=c.sha(p);p.write_bytes(b"b")
            self.assertNotEqual(a,c.sha(p))

    def test_router_schedule_is_balanced_and_identity_only(self):
        counts={i:0 for i in range(3)}
        for j in range(1728):counts[c.router_index(j)]+=1
        self.assertEqual(counts,{0:576,1:576,2:576})
        self.assertEqual(list(inspect.signature(c.router_index).parameters),["query_index"])

    def test_router_schedule_rejects_bool_and_out_of_range(self):
        for j in (-1,1728,True,1.2):
            with self.assertRaises(ValueError):c.router_index(j)

    def test_header_accepts_registered_profile(self):
        old,p=old_and_header();c.header(p,old)

    def test_header_rejects_wrong_identity_or_claim(self):
        for key,value in (("commit_sha","other"),("status","FAIL"),("production_runtime_modified",True),("gate_e_candidate",True)):
            old,p=old_and_header();p[key]=value
            with self.assertRaises(c.InvalidInput):c.header(p,old)

    def test_header_rejects_missing_or_reordered_routers(self):
        for records in ([],[dict(router_seed=s) for s in reversed(c.ROUTER_SEEDS)]):
            old,p=old_and_header();p["records"]=records
            with self.assertRaises(c.InvalidInput):c.header(p,old)

    def test_header_rejects_changed_execution_scope_or_reasons(self):
        for key,value in (("model_loading",True),("training_steps",1),("base_reasons",{})):
            old,p=old_and_header();p["summary"][key]=value
            with self.assertRaises(c.InvalidInput):c.header(p,old)

    def toy_selection(self,shift=0,bad=False):
        catalog=[dict(descriptor=str(i),key=f"k{i}",evidence_value=999) for i in range(64)]
        catalog=catalog[shift:]+catalog[:shift]
        texts=[str(i%64) for i in range(1728)]
        def compose(head,words,features):
            result=torch.nn.functional.one_hot(torch.tensor([int(w) for w in words]),64).float()
            if bad:result[0,0]=float("nan")
            return result,{"fixture":True}
        return c.select_live(None,texts,catalog,None,compose),catalog

    def test_live_selector_runs_all_queries_against_64_candidates(self):
        (positions,scores,_),_=self.toy_selection()
        self.assertEqual(positions,[i%64 for i in range(1728)])
        self.assertEqual(tuple(scores.shape),(1728,64))

    def test_reordered_catalog_changes_position_not_identity(self):
        (a,_,_),ca=self.toy_selection();(b,_,_),cb=self.toy_selection(1)
        self.assertNotEqual(a,b)
        self.assertEqual([ca[i]["key"] for i in a],[cb[i]["key"] for i in b])

    def test_selector_has_no_expected_label_or_value_parameter(self):
        self.assertEqual(list(inspect.signature(c.select_live).parameters),["head","texts","catalog","features","compose"])

    def test_nonfinite_live_scores_are_invalid(self):
        with self.assertRaises(c.InvalidInput):self.toy_selection(bad=True)

    def test_wrong_query_count_is_invalid_before_encoding(self):
        with self.assertRaises(c.InvalidInput):c.select_live(None,[],[],None,None)

    def fixture(self,emitter=None):
        ref=self.ref;state=State(1,1,(ref,Ref("other",ref.provenance)))
        binding=NS(source_id=ref.provenance.source_id,source_sha256="hash",index_fingerprint="index",source_path="path",
                   evidence_time=1,revision=1,adapter=NS(calls=0,vectors=0))
        seen={}
        def cycle(router,read,request,cold,working,budget,registry,permission,ops,delivery):
            seen.update(cold=cold,read=read,request=request,working=working,budget=budget,permission=permission,
                        router=router,ops=ops,delivery=delivery("actual"))
            binding.adapter.calls+=2;binding.adapter.vectors+=128
            return dict(final_value=0,final_reference=asdict(ref),final_evidence=asdict(state),steps=[{"action":2},{"action":0}])
        def emit(bound,rid,result):
            seen["bound"]=bound
            return output(result["final_value"],bound.record_key)
        api=NS(Request=lambda **kw:NS(**kw),EvidenceRef=Ref,Provenance=Provenance,OBSERVED="observed",
               ReadRequest=lambda *a:NS(args=a),WorkingState=Work,BudgetState=Budget,Permission=lambda b:NS(allowed=b),
               cycle=cycle,BoundRequest=lambda *a:NS(request_id=a[0],scope_id=a[1],record_key=a[2]),emit=emitter or emit)
        handle=dict(key="selected",domain="domain",schema="schema",operations=["READ"])
        return state,binding,api,handle,seen

    def execute(self,emitter=None):
        state,binding,api,handle,seen=self.fixture(emitter)
        result=c.execute_selected("scope","q",handle,"router",state,binding,{},api,"ops",1)
        return result,state,seen

    def test_selected_reference_only_removed_from_cold_state(self):
        (_,out,ref,_,_),state,seen=self.execute()
        self.assertEqual([r.evidence_id for r in seen["cold"].observations],["other"])
        self.assertEqual(len(state.observations),2)
        self.assertEqual(ref,self.ref);self.assertEqual(out.value,0)

    def test_cycle_receives_request_binding_and_actual_callback_objects(self):
        _,_,seen=self.execute()
        self.assertEqual(seen["request"].key,"selected")
        self.assertEqual(seen["request"].request_id,"scope|q")
        self.assertEqual(seen["read"].args[0:3],("scope|q","scope",self.ref))
        self.assertEqual(seen["router"],"router");self.assertEqual(seen["ops"],"ops")
        self.assertEqual(seen["delivery"],"actual")

    def test_stale_state_and_fixed_budgets_do_not_use_expected_payload(self):
        _,_,seen=self.execute()
        self.assertEqual(seen["working"].slots[0,2:4].tolist(),[1.,1.])
        self.assertEqual(seen["working"].internal_step,7)
        self.assertEqual(seen["budget"],Budget(3,1));self.assertTrue(seen["permission"].allowed)
        parameters=inspect.signature(c.execute_selected).parameters
        self.assertFalse(any("expected" in name or "target" in name for name in parameters))

    def test_metered_cost_is_independent_of_output_status(self):
        (r,_,_,_,_),_,_=self.execute(lambda b,r,x:output(None))
        self.assertEqual((r["retrieval_calls"],r["vectors_scored"]),(2,128))

    def test_rejected_output_is_not_replaced_by_answer(self):
        rejected=Output("REJECTED","bad",None,"scope|q","scope",None,None,None,None)
        (_,out,_,_,_),_,_=self.execute(lambda *a:rejected)
        self.assertIs(out,rejected)

    def test_emitter_mutation_is_measured_not_hidden(self):
        def bad(b,r,result):result["final_value"]=1;return output(1)
        (_,_,_,_,changed),_,_=self.execute(bad)
        self.assertTrue(changed)

    def test_absent_selected_reference_is_invalid_fixture(self):
        state,binding,api,handle,_=self.fixture();handle["key"]="absent"
        with self.assertRaises(c.InvalidInput):c.execute_selected("scope","q",handle,None,state,binding,{},api,None,0)

    def test_stale_bit_rejects_boolean_and_nonbit(self):
        state,binding,api,handle,_=self.fixture()
        for value in (True,2,None):
            with self.assertRaises(c.InvalidInput):c.execute_selected("scope","q",handle,None,state,binding,{},api,None,value)

    def assess(self,out=None,selected=0,key="selected",target=0):
        return c.assess_output(out or output(),"scope|q","scope",self.ref,selected,key,target)

    def test_zero_and_one_are_observed_answers(self):
        for bit in (0,1):self.assertTrue(self.assess(output(bit),bit,"selected",bit)["semantic_correct"])

    def test_same_bit_wrong_record_is_semantically_wrong_but_binding_valid(self):
        r=self.assess(key="other")
        self.assertTrue(r["bound"]);self.assertFalse(r["semantic_correct"])

    def test_boolean_or_none_is_not_a_valid_answered_integer(self):
        for value in (False,True,None,2):self.assertFalse(self.assess(output(value))["bound"])

    def test_wrong_scope_source_clock_or_key_is_not_bound(self):
        for key,value in (("scope_id","other"),("source_id","other"),("revision",2),("record_key","other")):
            args=asdict(output());args[key]=value
            self.assertFalse(self.assess(Output(**args))["bound"])

    def test_evaluator_cannot_change_output(self):
        out=output();before=asdict(out);self.assess(out,key="wrong",target=1)
        self.assertEqual(asdict(out),before)

    def test_compact_trace_keeps_all_actions_but_not_repeated_full_state(self):
        r=dict(final_evidence={"observations":[asdict(self.ref)]},steps=[{"action":2},{"action":0}],final_value=0)
        before=deepcopy(r);q=c.compact_cycle(r)
        self.assertNotIn("final_evidence",q);self.assertEqual(q["steps"],r["steps"])
        self.assertEqual(q["final_reference_count"],1);self.assertEqual(r,before)

    def replay_fixture(self, directory):
        plan={"records":[{} for _ in range(128)]}
        source=[]; records=[]
        def emit(bound,rid,r):
            if r.get("fault"):
                return Output("REJECTED","BAD",None,rid,"scope",None,None,None,None)
            return output() if r["answer"] else Output("UNRESOLVED","MISS",None,rid,"scope",None,None,None,None)
        def variants(row):
            for j in range(3 if row["result"]["answer"] else 2):
                yield "FAULT"+str(j),row["source_request_id"],{"fault":True},"BAD"
        old=NS(_safe_file=lambda root,name:root/name,_binding=lambda row:None,
               emit_terminal=emit,_variants=variants,_no_payload=lambda out:out.value is None)
        for seed in c.ROUTER_SEEDS:
            origin=dict(router_seed=seed,file=f"episodes-{seed}.jsonl",sha256="source-hash")
            rows=[dict(source_request_id="scope|q",scenario=str(i%5),result=dict(answer=i%5<2)) for i in range(640)]
            stored=[]
            for i,row in enumerate(rows):
                controls=[dict(condition=name,output=asdict(emit(None,rid,r)),passed=True) for name,rid,r,_ in variants(row)]
                stored.append(dict(source_row=i,source_request_id=row["source_request_id"],scenario=row["scenario"],
                    output=asdict(emit(None,row["source_request_id"],row["result"])),passed=True,controls=controls))
            path=directory/f"terminal-{seed}.jsonl"
            path.write_text("".join(json.dumps(r)+"\n" for r in stored),encoding="utf-8")
            records.append(dict(router_seed=seed,source_file=origin["file"],source_sha256=origin["sha256"],
                file=path.name,sha256=c.sha(path),serialized_bytes=path.stat().st_size))
            source.append((origin,rows))
        return dict(records=records),source,plan,old

    def test_all6528_source_emissions_are_validated(self):
        with TemporaryDirectory() as d:
            root=Path(d);p,source,plan,old=self.replay_fixture(root);protected={}
            self.assertEqual(c.validate_outputs(p,source,plan,root,protected,old),6528)
            self.assertEqual(len(protected),3)

    def test_source_output_tamper_is_invalid(self):
        with TemporaryDirectory() as d:
            root=Path(d);p,source,plan,old=self.replay_fixture(root)
            with (root/p["records"][0]["file"]).open("a") as f:f.write("x")
            with self.assertRaises(c.InvalidInput):c.validate_outputs(p,source,plan,root,{},old)

    def test_inconsistent_output_with_matching_hash_is_still_invalid(self):
        with TemporaryDirectory() as d:
            root=Path(d);p,source,plan,old=self.replay_fixture(root)
            rec=p["records"][0];path=root/rec["file"]
            lines=path.read_text().splitlines();row=json.loads(lines[0]);row["output"]["value"]=1
            lines[0]=json.dumps(row);path.write_text("\n".join(lines)+"\n")
            rec.update(sha256=c.sha(path),serialized_bytes=path.stat().st_size)
            with self.assertRaises(c.InvalidInput):c.validate_outputs(p,source,plan,root,{},old)

    def test_gate_accepts_known_control_errors_without_repair(self):
        self.assertTrue(c.gate(profile()))

    def test_gate_rejects_semantic_errors_in_global_arm(self):
        p=profile();p["arms"]["GLOBAL_CONCEPT"]["CANONICAL"]["semantic_correct"]-=1
        self.assertFalse(c.gate(p))

    def test_gate_rejects_oracle_repair_of_control_errors(self):
        p=profile();p["arms"]["WITHIN_FACTOR"]["CANONICAL"]["semantic_correct"]=20736
        self.assertFalse(c.gate(p))

    def test_gate_rejects_wrong_cost_mutation_and_missing_replay(self):
        for key in ("retrieval_calls","vectors_scored","weight_mutations","output_mutations","serialization_failures","c159_replay_calls"):
            p=profile();p[key]+=1;self.assertFalse(c.gate(p))

    def test_gate_requires_all_router_coverage(self):
        p=profile();p["router_episodes"][str(c.ROUTER_SEEDS[0])]-=1
        self.assertFalse(c.gate(p))

    def test_gate_rejects_tie_or_nonfinite_controller_margin(self):
        for value in (0.,-1.,float("nan"),float("inf")):
            p=profile();p["minimum_controller_margin"]=value;self.assertFalse(c.gate(p))


if __name__ == "__main__":
    unittest.main()
