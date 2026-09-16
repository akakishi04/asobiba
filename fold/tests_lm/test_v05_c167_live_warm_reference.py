"""C167 helper contracts. Controlled fixtures are not the formal learned run."""
from copy import deepcopy
from dataclasses import asdict, replace
import inspect
from types import SimpleNamespace as NS
import unittest

from fold_lm.v05_benchmarks import gate_e_c167_live_warm_reference as c
from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind, WorkingState, BudgetState
from tests_lm.test_v05_c158_live_recovery import RuntimeFixture, LogicalTestRouter, AlwaysRouter


def profile():
    n=c.PREFIXES
    s=dict(episodes=2*n,failed_episodes=0,ranking_queries=n,candidate_scores=64*n,
        ranker_replay_cases=41472,original12_replay_cases=288,c159_replay_calls=6528,
        controller_decisions=3*n,acquisitions=n,publications=n,retrieval_calls=3*n,vectors_scored=192*n,
        metered_adapter_calls=3*n,metered_vectors_scored=192*n,answered=2*n,unresolved=0,
        output_mutations=0,serialization_failures=0,weight_mutations=0,source_codes_preserved=True,
        matched_output_pairs=n,router_episodes={str(r):2*n//3 for r in c.ROUTERS},
        raw_action_counts={"2":n,"0":2*n},answer_values={"0":69984,"1":95904},conditions={})
    for cond in c.CONDITIONS:
        warm=cond==c.CONDITIONS[1]
        g=dict(episodes=n,failed_episodes=0,controller_decisions=(1 if warm else 2)*n,
            acquisitions=0 if warm else n,publications=0 if warm else n,
            retrieval_calls=(1 if warm else 2)*n,vectors_scored=(64 if warm else 128)*n,
            answered=n,unresolved=0,terminal_correct=n,initial_state_verified=n,initial_budget_verified=n,
            minimum_controller_margin=5.,router_episodes={str(r):n//3 for r in c.ROUTERS},
            answer_values={"0":34992,"1":47952},
            arms={a:{o:dict(cases=20736,binding_correct=20736,
                semantic_correct=20727 if a==c.ARMS[0] else 20736) for o in c.ORDERS} for a in c.ARMS})
        if warm: g.update(warm_no_reacquisition=n,warm_budget_preserved=n,warm_one_answer=n,warm_state_unchanged=n)
        s["conditions"][cond]=g
    s["emission"]=dict(native_emitter_calls=2*n,adapted_emitter_calls=2*n,native_tuple=2*n,adapted_list=2*n,
        content_unchanged=2*n,native_rejected=2*n,input_preserved=2*n,guard_emitter_calls=768,
        guard_control_cases=768,guard_control_passed=768,guard_control_failed=0,guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":2*n},adapted_status_counts={"ANSWERED":2*n},
        adapted_reason_counts={"OBSERVED_VALUE":2*n})
    return s


class V05C167LiveWarmReferenceTests(unittest.TestCase):
    def setup_case(self):
        b=c.terminal.BoundRequest("scope|q","scope","selected","persisted-snapshot:source",1,1)
        ref=EvidenceRef(b.record_key,Provenance(b.source_id,ProvenanceKind.OBSERVED,1,1))
        full=EvidenceState(1,1,(replace(ref,evidence_id="other"),ref))
        return b,ref,full

    def exercise(self,warm,bit=0,model=None):
        b,ref,full=self.setup_case(); ops=RuntimeFixture(ref,bit)
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
            model or LogicalTestRouter(),full,binding,{},c.api_with_reference_presence(api,full,warm),ops,1-bit)
        judged=recovery._assess_episode(result,c.CONDITIONS[int(warm)],ref,full,bit,budget)
        audit=c.presence_audit(result,ref,full,budget,warm)
        return result,out,judged,audit,ops,full,mutated,emitter

    def call_wrapper(self,present,full=None,state=None):
        _,ref,fixture=self.setup_case(); full=fixture if full is None else full
        cold=replace(fixture,observations=fixture.observations[:1])
        seen=[]; api=NS(cycle=lambda *a:seen.append(a) or {},marker=object())
        args=(object(),NS(reference=ref),object(),cold if state is None else state,
              object(),object(),object(),object(),object(),object())
        wrapped=c.api_with_reference_presence(api,full,present)
        out=wrapped.cycle(*args)
        return args,seen[0],out,api,wrapped,fixture

    def test_cold_wrapper_forwards_original_state_and_other_arguments(self):
        args,seen,out,api,wrapped,_=self.call_wrapper(False)
        self.assertTrue(all(a is b for a,b in zip(args,seen)))
        self.assertIs(api.marker,wrapped.marker); self.assertFalse(out["initial_selected_reference_present"])

    def test_warm_wrapper_changes_only_state_and_preserves_order(self):
        args,seen,out,_,_,full=self.call_wrapper(True)
        for i in range(10):
            if i!=3: self.assertIs(args[i],seen[i])
        self.assertEqual(seen[3],full); self.assertIsNot(seen[3],full)
        self.assertEqual(seen[3].observations,full.observations)
        self.assertTrue(out["initial_selected_reference_present"])

    def test_wrapper_records_actual_initial_digest_and_count(self):
        for present in (False,True):
            _,seen,out,*_=self.call_wrapper(present)
            self.assertEqual(out["initial_evidence_sha256"],c.state_digest(seen[3]))
            self.assertEqual(out["initial_reference_count"],1+int(present))

    def test_wrapper_rejects_nonboolean_presence(self):
        _,_,full=self.setup_case()
        for value in (0,1,None,"warm"):
            with self.assertRaises(TypeError): c.api_with_reference_presence(NS(),full,value)

    def test_wrapper_rejects_missing_source_reference(self):
        _,_,full=self.setup_case()
        with self.assertRaises(ValueError): self.call_wrapper(True,full=replace(full,observations=full.observations[:1]))

    def test_wrapper_rejects_base_state_or_clock_drift(self):
        _,_,full=self.setup_case()
        for state in (full,replace(full,observations=(),evidence_time=2)):
            with self.assertRaises(ValueError): self.call_wrapper(True,state=state)

    def test_wrapper_interface_has_no_payload_target_or_action(self):
        self.assertEqual(list(inspect.signature(c.api_with_reference_presence).parameters),["api","full_state","present"])

    def test_warm_zero_and_one_answer_after_one_real_cycle_decision(self):
        for bit in (0,1):
            r,out,j,a,ops,full,mutated,e=self.exercise(True,bit)
            self.assertTrue(j["passed"],j); self.assertTrue(all(a.values()),a)
            self.assertEqual(out.value,bit); self.assertEqual([s["action"] for s in r["steps"]],[0])
            self.assertFalse(mutated)

    def test_warm_reads_once_without_fetch_admission_or_publication(self):
        r,out,j,a,ops,*_=self.exercise(True,1)
        self.assertEqual((ops.reads,ops.fetches,ops.admissions),(1,0,0))
        self.assertEqual((r["acquisitions"],r["publications"],r["inbox_entries"]),(0,0,0))
        self.assertEqual((r["retrieval_calls"],r["vectors_scored"]),(1,64))

    def test_warm_keeps_acquisition_budget_and_pays_internal_step(self):
        r,*_=self.exercise(True)
        self.assertEqual(r["final_budget"],dict(internal_steps_remaining=2,acquisitions_remaining=1))
        self.assertEqual(r["final_internal_step"],8)

    def test_cold_zero_and_one_keep_original_recovery_contract(self):
        for bit in (0,1):
            r,out,j,a,ops,*_=self.exercise(False,bit)
            self.assertTrue(j["passed"],j); self.assertTrue(all(a.values()),a)
            self.assertEqual((ops.reads,ops.fetches),(2,1)); self.assertEqual(out.value,bit)

    def test_warm_state_not_built_from_cold_final_state(self):
        _,_,full=self.setup_case(); before=c.state_digest(full)
        self.exercise(False)
        _,seen,out,_,_,_=self.call_wrapper(True,full=full)
        self.assertEqual(c.state_digest(full),before); self.assertEqual(seen[3],full)
        self.assertIsNot(seen[3],full)

    def test_native_control_still_rejects_on_warm_result(self):
        *_,e=self.exercise(True)
        self.assertEqual(e.last["native_output"]["reason"],"MALFORMED_EVIDENCE")
        self.assertTrue(all(e.last["checks"].values()))

    def test_wrong_controller_stop_is_not_overridden(self):
        r,out,j,a,*_=self.exercise(True,model=AlwaysRouter(5))
        self.assertEqual(r["steps"][0]["action"],5); self.assertFalse(j["passed"])
        self.assertEqual(out.status,"REJECTED"); self.assertFalse(a["warm_one_answer"])

    def test_warm_audit_detects_reacquisition_or_state_change(self):
        r,_,_,_,_,full,*_=self.exercise(True)
        ref=full.observations[-1]; budget=BudgetState(3,1)
        bad=deepcopy(r); bad["acquisitions"]=1
        self.assertFalse(c.presence_audit(bad,ref,full,budget,True)["warm_no_reacquisition"])
        bad=deepcopy(r); bad["final_evidence"]["observations"]=()
        self.assertFalse(c.presence_audit(bad,ref,full,budget,True)["warm_state_unchanged"])

    def test_same_bit_wrong_record_is_still_semantically_wrong(self):
        b,ref,_=self.setup_case()
        out=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"ANSWERED","OBSERVED_VALUE",0,ref.evidence_id,b.source_id,1,1)
        a=c.old.assess_output(out,b.request_id,b.scope_id,ref,0,"different",0)
        self.assertTrue(a["bound"]); self.assertFalse(a["semantic_correct"])

    def test_pair_check_requires_distinct_requests_and_matching_identity(self):
        b,ref,_=self.setup_case()
        a=c.terminal.TerminalResult(c.terminal.SCHEMA,b.request_id,b.scope_id,"ANSWERED","OBSERVED_VALUE",0,ref.evidence_id,b.source_id,1,1)
        other=replace(a,request_id="warm|q",scope_id="warm")
        self.assertTrue(c.same_observed_output(a,other)); self.assertFalse(c.same_observed_output(a,a))
        self.assertFalse(c.same_observed_output(a,replace(other,record_key="wrong")))

    def test_state_digest_is_deterministic_and_membership_sensitive(self):
        _,_,full=self.setup_case()
        self.assertEqual(c.state_digest(full),c.state_digest(replace(full)))
        self.assertNotEqual(c.state_digest(full),c.state_digest(replace(full,observations=full.observations[:1])))

    def test_gate_accepts_only_complete_profile(self):
        self.assertTrue(c.gate(profile()))
        s=profile(); s["episodes"]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_extra_or_missing_condition(self):
        s=profile(); s["conditions"]["OTHER"]={}; self.assertFalse(c.gate(s))
        s=profile(); del s["conditions"][c.CONDITIONS[1]]; self.assertFalse(c.gate(s))

    def test_gate_rejects_warm_acquisition_and_publication(self):
        for k in ("acquisitions","publications"):
            s=profile(); s["conditions"][c.CONDITIONS[1]][k]=1; self.assertFalse(c.gate(s))

    def test_gate_requires_paid_warm_read_and_independent_meter(self):
        s=profile(); s["conditions"][c.CONDITIONS[1]]["retrieval_calls"]=0; self.assertFalse(c.gate(s))
        for k in ("metered_adapter_calls","metered_vectors_scored"):
            s=profile(); s[k]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_warm_extra_decision_or_budget_audit_failure(self):
        for k in ("controller_decisions","warm_budget_preserved","warm_one_answer"):
            s=profile(); s["conditions"][c.CONDITIONS[1]][k]-=1; self.assertFalse(c.gate(s))

    def test_gate_checks_actual_initial_state_and_unchanged_warm_state(self):
        for k in ("initial_state_verified","initial_budget_verified","warm_state_unchanged"):
            s=profile(); s["conditions"][c.CONDITIONS[1]][k]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_nonpositive_nonfinite_and_boolean_margin(self):
        for value in (0,-1,float("nan"),float("inf"),True):
            s=profile(); s["conditions"][c.CONDITIONS[1]]["minimum_controller_margin"]=value
            self.assertFalse(c.gate(s))

    def test_gate_preserves_known_semantic_errors_in_both_conditions(self):
        for cond in c.CONDITIONS:
            s=profile(); s["conditions"][cond]["arms"][c.ARMS[0]][c.ORDERS[0]]["semantic_correct"]=20736
            self.assertFalse(c.gate(s))

    def test_gate_rejects_zero_one_distribution_and_pair_mismatch(self):
        s=profile(); s["answer_values"]["0"]-=1; self.assertFalse(c.gate(s))
        s=profile(); s["conditions"][c.CONDITIONS[1]]["answer_values"]["1"]-=1; self.assertFalse(c.gate(s))
        s=profile(); s["matched_output_pairs"]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_raw_action_and_router_imbalance(self):
        for k in ("raw_action_counts","router_episodes"):
            s=profile(); s[k][next(iter(s[k]))]-=1; self.assertFalse(c.gate(s))

    def test_gate_rejects_guard_mutation_and_source_failure(self):
        s=profile(); s["emission"]["guard_control_failed"]=1; self.assertFalse(c.gate(s))
        for k in ("output_mutations","weight_mutations","serialization_failures"):
            s=profile(); s[k]=1; self.assertFalse(c.gate(s))
        s=profile(); s["source_codes_preserved"]=False; self.assertFalse(c.gate(s))

    def test_parent_rejects_wrong_identity_before_use(self):
        with self.assertRaises(ValueError): c.validate_parent({})


if __name__=="__main__":
    unittest.main()
