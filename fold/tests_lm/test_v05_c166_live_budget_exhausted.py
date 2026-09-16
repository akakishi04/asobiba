"""C166 helper contracts; controlled fixtures are not learned-model evidence."""
from dataclasses import asdict, replace
import inspect
from types import SimpleNamespace as NS
import unittest

from fold_lm.v05_benchmarks import gate_e_c166_live_budget_exhausted as c
from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind, WorkingState, BudgetState
from tests_lm.test_v05_c158_live_recovery import RuntimeFixture, LogicalTestRouter, AlwaysRouter


def profile():
    n=c.PREFIXES
    s=dict(episodes=2*n,failed_episodes=0,ranking_queries=n,candidate_scores=64*n,
        ranker_replay_cases=41472,original12_replay_cases=288,c159_replay_calls=6528,
        controller_decisions=4*n,acquisitions=n,publications=n,retrieval_calls=2*n,vectors_scored=128*n,
        metered_adapter_calls=2*n,metered_vectors_scored=128*n,
        answered=n,unresolved=n,output_mutations=0,serialization_failures=0,weight_mutations=0,
        source_codes_preserved=True,router_episodes={str(r):2*n//3 for r in c.ROUTERS},
        raw_action_counts={"2":2*n,"0":n,"5":n},answer_values={"0":34992,"1":47952},conditions={})
    for cond in c.CONDITIONS:
        answer=cond==c.CONDITIONS[0]
        s["conditions"][cond]=dict(episodes=n,failed_episodes=0,controller_decisions=2*n,
            acquisitions=n if answer else 0,publications=n if answer else 0,
            retrieval_calls=2*n if answer else 0,vectors_scored=128*n if answer else 0,
            answered=n if answer else 0,unresolved=0 if answer else n,terminal_correct=n,
            unresolved_without_payload=0 if answer else n,minimum_controller_margin=5.,
            router_episodes={str(r):n//3 for r in c.ROUTERS},
            arms={a:{o:dict(cases=20736,terminal_correct=20736,answer_bound=20736 if answer else 0,
                unresolved_without_payload=0 if answer else 20736,
                semantic_correct=(20727 if a==c.ARMS[0] else 20736) if answer else None)
                for o in c.ORDERS} for a in c.ARMS})
    s["conditions"][c.CONDITIONS[1]].update(budget_exhausted_authority=n,
        initial_acquisition_budget_zero=n,acquisition_budget_preserved=n,no_overbudget_fetch=n)
    s["emission"]=dict(native_emitter_calls=2*n,adapted_emitter_calls=2*n,native_tuple=2*n,adapted_list=2*n,
        content_unchanged=2*n,native_rejected=2*n,input_preserved=2*n,guard_emitter_calls=768,
        guard_control_cases=768,guard_control_passed=768,guard_control_failed=0,guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":2*n},adapted_status_counts={"ANSWERED":n,"UNRESOLVED":n},
        adapted_reason_counts={"OBSERVED_VALUE":n,"BUDGET_EXHAUSTED":n})
    return s


class V05C166LiveBudgetExhaustedTests(unittest.TestCase):
    def binding(self):
        b=c.terminal.BoundRequest("scope|q","scope","selected","persisted-snapshot:source",1,1)
        r=EvidenceRef(b.record_key,Provenance(b.source_id,ProvenanceKind.OBSERVED,1,1))
        return b,r

    def assess(self,out):
        b,r=self.binding()
        return c.assess_terminal(out,b,r,0,"selected",0,c.CONDITIONS[1])

    def exercise(self,allowance,bit=0,model=None):
        b,ref=self.binding(); ops=RuntimeFixture(ref,bit)
        full=EvidenceState(1,1,(ref,replace(ref,evidence_id="other")))
        class Meter:
            @property
            def calls(self): return ops.reads
            @property
            def vectors(self): return ops.reads*64
        binding=NS(source_id=b.source_id,source_sha256="source",index_fingerprint="index",source_path="path",
                   evidence_time=1,revision=1,adapter=Meter())
        emitter=c.live.AuditedEmitter()
        api=NS(Request=lambda **kw:NS(**kw),EvidenceRef=EvidenceRef,Provenance=Provenance,
            OBSERVED=ProvenanceKind.OBSERVED,
            ReadRequest=lambda rid,scope,r,*unused:NS(request_id=rid,scope_id=scope,reference=r),
            WorkingState=WorkingState,BudgetState=BudgetState,Permission=recovery.Permission,
            cycle=recovery.cycle,BoundRequest=c.terminal.BoundRequest,emit=emitter)
        result,out,ref,budget,mutated=c.old.execute_selected("scope","q",
            dict(key="selected",domain="test",schema="test",operations=["READ"]),
            model or LogicalTestRouter(),full,binding,{},c.api_with_acquisition_budget(api,allowance),ops,1-bit)
        condition=c.CONDITIONS[0] if allowance else c.CONDITIONS[1]
        judged=recovery._assess_episode(result,condition,ref,full,bit,budget)
        assessed=c.assess_terminal(out,b,ref,bit,"selected",bit,condition)
        return result,out,judged,assessed,ops,full,budget,mutated,emitter

    def test_factory_constructs_actual_budget_with_one_or_zero(self):
        for n in (1,0):
            b=c.api_with_acquisition_budget(NS(BudgetState=BudgetState),n).BudgetState(3,1)
            self.assertIs(type(b),BudgetState); self.assertEqual(asdict(b),dict(internal_steps_remaining=3,acquisitions_remaining=n))

    def test_factory_preserves_every_other_api_object(self):
        api=NS(BudgetState=BudgetState,Permission=object(),cycle=object(),emit=object(),marker=object())
        wrapped=c.api_with_acquisition_budget(api,0)
        self.assertIsNot(wrapped,api); self.assertIs(api.BudgetState,BudgetState)
        for name in ("Permission","cycle","emit","marker"): self.assertIs(getattr(wrapped,name),getattr(api,name))

    def test_factory_rejects_unregistered_and_boolean_allowances(self):
        for n in (True,False,-1,2,0.,1.,None,"0"):
            with self.assertRaises(ValueError): c.api_with_acquisition_budget(NS(BudgetState=BudgetState),n)

    def test_factory_rejects_base_budget_drift(self):
        make=c.api_with_acquisition_budget(NS(BudgetState=BudgetState),0).BudgetState
        for a,b in ((2,1),(4,1),(3,0),(3,2),(3,True),(3.,1)):
            with self.assertRaises(ValueError): make(a,b)

    def test_factory_has_no_target_or_permission_input(self):
        self.assertEqual(list(inspect.signature(c.api_with_acquisition_budget).parameters),["api","allowance"])

    def test_internal_debit_preserves_zero_acquisition_allowance(self):
        b=c.api_with_acquisition_budget(NS(BudgetState=BudgetState),0).BudgetState(3,1)
        next_b=b.consume_internal_step()
        self.assertEqual(asdict(next_b),dict(internal_steps_remaining=2,acquisitions_remaining=0))
        self.assertEqual(b.internal_steps_remaining,3)

    def test_recovered_zero_and_one_use_actual_cycle(self):
        for bit in (0,1):
            r,out,j,a,ops,_,budget,mutated,_=self.exercise(1,bit)
            self.assertTrue(j["passed"],j); self.assertTrue(a["terminal_correct"])
            self.assertEqual(out.value,bit); self.assertEqual(ops.reads,2)
            self.assertEqual(budget.acquisitions_remaining,1); self.assertFalse(mutated)

    def test_exhausted_zero_and_one_stop_without_payload(self):
        for bit in (0,1):
            r,out,j,a,ops,_,budget,mutated,_=self.exercise(0,bit)
            self.assertTrue(j["passed"],j); self.assertTrue(a["unresolved_without_payload"])
            self.assertEqual((out.status,out.reason),("UNRESOLVED","BUDGET_EXHAUSTED"))
            self.assertEqual([s["action"] for s in r["steps"]],[2,5])
            self.assertTrue(all(c.budget_audit(r,budget).values())); self.assertFalse(mutated)

    def test_exhausted_cycle_never_fetches_admits_publishes_or_rereads(self):
        r,_,_,_,ops,full,budget,_,_=self.exercise(0,1)
        self.assertEqual((ops.fetches,ops.admissions,ops.reads,r["acquisitions"],r["publications"]),(0,0,0,0,0))
        self.assertEqual(len(full.observations),2); self.assertEqual(len(r["final_evidence"]["observations"]),1)
        self.assertEqual(r["final_working"][2:4],[0.,0.]); self.assertEqual(budget.acquisitions_remaining,0)

    def test_actual_initial_budget_is_returned_and_internal_steps_are_paid(self):
        r,_,j,_,_,_,budget,_,_=self.exercise(0)
        self.assertTrue(j["passed"],j)
        self.assertEqual(asdict(budget),dict(internal_steps_remaining=3,acquisitions_remaining=0))
        self.assertEqual(r["final_budget"],dict(internal_steps_remaining=1,acquisitions_remaining=0))
        self.assertEqual(r["final_internal_step"],9)

    def test_exhaustion_is_not_permission_denial(self):
        r,out,*_=self.exercise(0)
        self.assertEqual(r["steps"][0]["authority"],"BUDGET_EXHAUSTED")
        self.assertNotEqual(out.reason,"PERMISSION_DENIED")

    def test_native_control_keeps_original_container_rejection(self):
        *_,emitter=self.exercise(0)
        self.assertEqual(emitter.last["native_output"]["reason"],"MALFORMED_EVIDENCE")
        self.assertTrue(all(emitter.last["checks"].values()))

    def test_wrong_controller_answer_is_not_overridden(self):
        r,out,j,a,*_=self.exercise(0,model=AlwaysRouter(0))
        self.assertEqual(r["steps"][0]["action"],0); self.assertFalse(j["passed"])
        self.assertEqual(out.status,"REJECTED"); self.assertFalse(a["terminal_correct"])

    def test_unresolved_requires_none_not_zero_or_false(self):
        b,_=self.binding(); out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"UNRESOLVED","BUDGET_EXHAUSTED")
        self.assertTrue(self.assess(out)["terminal_correct"])
        for value in (0,1,False,True): self.assertFalse(self.assess(replace(out,value=value))["terminal_correct"])

    def test_unresolved_identity_reason_and_metadata_are_checked(self):
        b,_=self.binding(); out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"UNRESOLVED","BUDGET_EXHAUSTED")
        for k,v in (("schema_version","wrong"),("scope_id","other"),("request_id","other"),("reason","PERMISSION_DENIED"),
                    ("reason","MISSING_DELIVERY"),("record_key","selected"),("source_id",b.source_id),("revision",1),("evidence_time",1)):
            self.assertFalse(self.assess(replace(out,**{k:v}))["terminal_correct"])

    def test_same_bit_wrong_record_is_not_semantically_correct(self):
        b,r=self.binding(); out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"ANSWERED","OBSERVED_VALUE",0,b.record_key,b.source_id,1,1)
        a=c.assess_terminal(out,b,r,0,"other",0,c.CONDITIONS[0])
        self.assertTrue(a["answer_bound"]); self.assertFalse(a["semantic_correct"])

    def test_unknown_evaluator_condition_is_rejected(self):
        with self.assertRaises(ValueError): c.assess_terminal(None,None,None,0,"",0,"OTHER")

    def test_gate_accepts_complete_profile(self):
        self.assertTrue(c.gate(profile()))

    def test_gate_rejects_coverage_and_extra_condition(self):
        s=profile(); s["episodes"]-=1; self.assertFalse(c.gate(s))
        s=profile(); s["conditions"]["EXTRA"]={}; self.assertFalse(c.gate(s))

    def test_gate_rejects_exhausted_acquisition_publication_or_read(self):
        for k in ("acquisitions","publications","retrieval_calls","vectors_scored","answered"):
            s=profile(); s["conditions"][c.CONDITIONS[1]][k]=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_budget_and_authority_audit_failures(self):
        for k in ("budget_exhausted_authority","initial_acquisition_budget_zero","acquisition_budget_preserved","no_overbudget_fetch"):
            s=profile(); s["conditions"][c.CONDITIONS[1]][k]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_unresolved_payload_contract_failure(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["unresolved_without_payload"]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_meter_disagreement(self):
        for k in ("retrieval_calls","vectors_scored","metered_adapter_calls","metered_vectors_scored"):
            s=profile(); s[k]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_router_and_action_imbalance(self):
        for k in ("router_episodes","raw_action_counts"):
            s=profile(); s[k][next(iter(s[k]))]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_nonpositive_and_nonfinite_margins(self):
        for cond in c.CONDITIONS:
            for v in (0.,-1.,float("nan"),float("inf"),True):
                s=profile(); s["conditions"][cond]["minimum_controller_margin"]=v; self.assertFalse(c.gate(s))

    def test_gate_preserves_known_semantic_errors(self):
        s=profile(); s["conditions"][c.CONDITIONS[0]]["arms"][c.ARMS[0]][c.ORDERS[0]]["semantic_correct"]=20736
        self.assertFalse(c.gate(s))

    def test_gate_does_not_score_unresolved_as_semantic_accuracy(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["arms"][c.ARMS[1]][c.ORDERS[0]]["semantic_correct"]=0
        self.assertFalse(c.gate(s))

    def test_gate_rejects_guard_source_mutation_and_wrong_reason(self):
        s=profile(); s["emission"]["guard_control_failed"]=1; self.assertFalse(c.gate(s))
        s=profile(); s["source_codes_preserved"]=False; self.assertFalse(c.gate(s))
        s=profile(); s["emission"]["adapted_reason_counts"]={"OBSERVED_VALUE":82944,"PERMISSION_DENIED":82944}; self.assertFalse(c.gate(s))

    def test_parent_rejects_wrong_identity_before_source_use(self):
        with self.assertRaises(ValueError): c.validate_parent({})

    def test_budget_audit_detects_initial_budget_and_later_fetch(self):
        r=dict(steps=[dict(authority="BUDGET_EXHAUSTED",fetched=None)],final_budget=dict(acquisitions_remaining=0),retrieval_calls=0,acquisitions=0)
        self.assertTrue(all(c.budget_audit(r,BudgetState(3,0)).values()))
        self.assertFalse(c.budget_audit(r,BudgetState(3,1))["initial_acquisition_budget_zero"])
        r["steps"].append(dict(fetched={"key":"hidden"}))
        self.assertFalse(c.budget_audit(r,BudgetState(3,0))["no_overbudget_fetch"])


if __name__=="__main__":
    unittest.main()
