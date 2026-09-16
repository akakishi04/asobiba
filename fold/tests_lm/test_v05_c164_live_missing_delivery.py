"""C164 helper contracts. Controlled callbacks are not the formal artifact run."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import inspect
from types import SimpleNamespace as NS
import unittest

from fold_lm.v05_benchmarks import gate_e_c164_live_missing_delivery as c
from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind, WorkingState, BudgetState
from tests_lm.test_v05_c158_live_recovery import RuntimeFixture, LogicalTestRouter, AlwaysRouter


@dataclass(frozen=True)
class Packet:
    evidence: object
    request_id: str = "scope|q"
    stats: str = "unchanged"


def profile():
    n=c.PREFIXES
    s=dict(episodes=2*n,failed_episodes=0,ranking_queries=n,candidate_scores=64*n,
        ranker_replay_cases=41472,original12_replay_cases=288,c159_replay_calls=6528,
        controller_decisions=4*n,acquisitions=2*n,publications=n,retrieval_calls=3*n,vectors_scored=192*n,
        metered_adapter_calls=3*n,metered_vectors_scored=192*n,
        answered=n,unresolved=n,output_mutations=0,serialization_failures=0,weight_mutations=0,
        source_codes_preserved=True,router_episodes={str(r):2*n//3 for r in c.ROUTERS},
        raw_action_counts={"2":2*n,"0":n,"5":n},answer_values={"0":34992,"1":47952},conditions={})
    for cond,reads,pub,answer in ((c.CONDITIONS[0],2,1,1),(c.CONDITIONS[1],1,0,0)):
        s["conditions"][cond]=dict(episodes=n,failed_episodes=0,controller_decisions=2*n,
            acquisitions=n,publications=pub*n,retrieval_calls=reads*n,vectors_scored=reads*64*n,
            answered=answer*n,unresolved=(1-answer)*n,terminal_correct=n,unresolved_without_payload=(1-answer)*n,
            minimum_controller_margin=5.,router_episodes={str(r):n//3 for r in c.ROUTERS},
            arms={a:{o:dict(cases=20736,terminal_correct=20736,answer_bound=20736 if answer else 0,
                unresolved_without_payload=0 if answer else 20736,
                semantic_correct=(20727 if a==c.ARMS[0] else 20736) if answer else None)
                for o in c.ORDERS} for a in c.ARMS})
    s["emission"]=dict(native_emitter_calls=2*n,adapted_emitter_calls=2*n,native_tuple=2*n,adapted_list=2*n,
        content_unchanged=2*n,native_rejected=2*n,input_preserved=2*n,guard_emitter_calls=768,
        guard_control_cases=768,guard_control_passed=768,guard_control_failed=0,guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":2*n},adapted_status_counts={"ANSWERED":n,"UNRESOLVED":n},
        adapted_reason_counts={"OBSERVED_VALUE":n,"MISSING_DELIVERY":n})
    return s


class V05C164LiveMissingDeliveryTests(unittest.TestCase):
    def binding(self):
        b=c.terminal.BoundRequest("scope|q","scope","selected","persisted-snapshot:source",1,1)
        ref=EvidenceRef(b.record_key,Provenance(b.source_id,ProvenanceKind.OBSERVED,1,1))
        return b,ref

    def assess(self,out,condition=None):
        b,r=self.binding()
        return c.assess_terminal(out,b,r,0,"selected",0,condition or c.CONDITIONS[1])

    def exercise(self,condition,bit=0,model=None):
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
        deliver=c.deliver_present if condition==c.CONDITIONS[0] else c.deliver_missing
        result,out,ref,budget,mutated=c.old.execute_selected("scope","q",
            dict(key="selected",domain="test",schema="test",operations=["READ"]),
            model or LogicalTestRouter(),full,binding,{},c.api_with_delivery(api,deliver),ops,1-bit)
        judged=recovery._assess_episode(result,condition,ref,full,bit,budget)
        assessed=c.assess_terminal(out,b,ref,bit,"selected",bit,condition)
        return result,out,judged,assessed,ops,full,mutated,emitter

    def test_present_delivery_returns_exact_object(self):
        p=Packet(object()); self.assertIs(c.deliver_present(p),p)

    def test_missing_delivery_keeps_envelope_and_drops_only_evidence(self):
        p=Packet(object()); q=c.deliver_missing(p)
        self.assertIsNone(q.evidence); self.assertIsNotNone(p.evidence)
        self.assertEqual((q.request_id,q.stats),(p.request_id,p.stats)); self.assertIsNot(q,p)

    def test_delivery_wrapper_forwards_every_nontransport_argument(self):
        seen=[]; api=NS(cycle=lambda *a:seen.append(a) or "actual",marker=object())
        wrapped=c.api_with_delivery(api,c.deliver_missing); args=tuple(object() for _ in range(10))
        self.assertEqual(wrapped.cycle(*args),"actual"); self.assertEqual(seen[0][:-1],args[:-1])
        self.assertIs(seen[0][-1],c.deliver_missing); self.assertIs(wrapped.marker,api.marker)
        self.assertIsNot(wrapped,api)

    def test_wrapper_rejects_noncallable_transport(self):
        with self.assertRaises(TypeError): c.api_with_delivery(NS(),None)

    def test_transport_interface_has_no_expected_value_or_condition(self):
        self.assertEqual(list(inspect.signature(c.api_with_delivery).parameters),["api","deliver"])
        self.assertEqual(list(inspect.signature(c.deliver_missing).parameters),["fetched"])

    def test_recovered_zero_and_one_use_actual_cycle_and_adapter(self):
        for bit in (0,1):
            r,out,j,a,ops,full,mutated,e=self.exercise(c.CONDITIONS[0],bit)
            self.assertTrue(j["passed"],j); self.assertTrue(a["terminal_correct"])
            self.assertEqual(out.value,bit); self.assertEqual(ops.reads,2)
            self.assertEqual([s["action"] for s in r["steps"]],[2,0]); self.assertFalse(mutated)

    def test_missing_delivery_zero_and_one_stop_without_payload(self):
        for bit in (0,1):
            r,out,j,a,ops,full,mutated,e=self.exercise(c.CONDITIONS[1],bit)
            self.assertTrue(j["passed"],j); self.assertTrue(a["unresolved_without_payload"])
            self.assertEqual((out.status,out.reason),("UNRESOLVED","MISSING_DELIVERY"))
            self.assertIsNone(out.value); self.assertIsNone(a["semantic_correct"])
            self.assertEqual([s["action"] for s in r["steps"]],[2,5]); self.assertFalse(mutated)

    def test_missing_branch_fetches_once_but_never_publishes_or_rereads(self):
        r,out,j,a,ops,full,_,_=self.exercise(c.CONDITIONS[1],1)
        self.assertEqual((ops.fetches,ops.reads,r["acquisitions"],r["publications"]),(1,1,1,0))
        self.assertEqual(r["steps"][0]["fetched"]["evidence_value"],1)
        self.assertEqual(r["final_budget"],dict(internal_steps_remaining=1,acquisitions_remaining=0))
        self.assertEqual(len(full.observations),2); self.assertEqual(len(r["final_evidence"]["observations"]),1)
        self.assertEqual(r["final_working"][2:4],[0.,0.])

    def test_missing_branch_native_control_still_rejects(self):
        *_,e=self.exercise(c.CONDITIONS[1])
        self.assertEqual(e.last["native_output"]["reason"],"MALFORMED_EVIDENCE")
        self.assertTrue(all(e.last["checks"].values()))

    def test_wrong_controller_answer_is_not_overridden(self):
        r,out,j,a,*_=self.exercise(c.CONDITIONS[1],model=AlwaysRouter(0))
        self.assertEqual(r["steps"][0]["action"],0); self.assertFalse(j["passed"])
        self.assertEqual(out.status,"REJECTED"); self.assertFalse(a["terminal_correct"])

    def test_unresolved_contract_accepts_none_not_zero_or_false(self):
        b,_=self.binding(); good=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"UNRESOLVED","MISSING_DELIVERY")
        self.assertTrue(self.assess(good)["terminal_correct"])
        for value in (0,1,False,True): self.assertFalse(self.assess(replace(good,value=value))["terminal_correct"])

    def test_unresolved_wrong_identity_reason_or_metadata_is_rejected(self):
        b,_=self.binding(); out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"UNRESOLVED","MISSING_DELIVERY")
        for k,v in (("scope_id","other"),("request_id","other"),("reason","PERMISSION_DENIED"),("record_key","selected"),("source_id",b.source_id)):
            self.assertFalse(self.assess(replace(out,**{k:v}))["terminal_correct"])

    def test_semantic_same_bit_wrong_record_is_not_repaired(self):
        b,r=self.binding(); out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"ANSWERED","OBSERVED_VALUE",0,b.record_key,b.source_id,1,1)
        a=c.assess_terminal(out,b,r,0,"different-target",0,c.CONDITIONS[0])
        self.assertTrue(a["answer_bound"]); self.assertFalse(a["semantic_correct"])

    def test_unknown_evaluator_condition_rejected(self):
        with self.assertRaises(ValueError): c.assess_terminal(None,None,None,0,"",0,"OTHER")

    def test_gate_accepts_only_complete_profile(self):
        self.assertTrue(c.gate(profile()))
        s=profile(); s["episodes"]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_unresolved_payload_contract_failure(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["unresolved_without_payload"]-=1
        self.assertFalse(c.gate(s))

    def test_gate_rejects_wrong_calls_and_meter_disagreement(self):
        for k in ("retrieval_calls","vectors_scored","metered_adapter_calls","metered_vectors_scored"):
            s=profile(); s[k]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_missing_branch_publication(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["publications"]=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_router_or_raw_action_imbalance(self):
        for k in ("router_episodes","raw_action_counts"):
            s=profile(); s[k][next(iter(s[k]))]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_nonpositive_or_nonfinite_margin(self):
        for v in (0.,-1.,float("nan"),float("inf")):
            s=profile(); s["conditions"][c.CONDITIONS[1]]["minimum_controller_margin"]=v; self.assertFalse(c.gate(s))

    def test_gate_preserves_known_semantic_errors(self):
        s=profile(); s["conditions"][c.CONDITIONS[0]]["arms"][c.ARMS[0]][c.ORDERS[0]]["semantic_correct"]=20736
        self.assertFalse(c.gate(s))

    def test_gate_does_not_count_unresolved_as_semantic_accuracy(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["arms"][c.ARMS[1]][c.ORDERS[0]]["semantic_correct"]=0
        self.assertFalse(c.gate(s))

    def test_gate_rejects_guard_failure_and_source_mutation(self):
        s=profile(); s["emission"]["guard_control_failed"]=1; self.assertFalse(c.gate(s))
        s=profile(); s["source_codes_preserved"]=False; self.assertFalse(c.gate(s))

    def test_parent_rejects_wrong_identity_before_source_use(self):
        with self.assertRaises(ValueError): c.validate_parent({})


if __name__=="__main__":
    unittest.main()
