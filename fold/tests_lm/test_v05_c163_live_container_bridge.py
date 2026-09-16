"""C163 adapter/guard tests; formal CUDA/artifact-chain execution is separate."""
from copy import deepcopy
from dataclasses import asdict, replace
import inspect
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from fold_lm.v05.state import EvidenceState, EvidenceRef, Provenance, ProvenanceKind
from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal
from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as old
from fold_lm.v05_benchmarks import gate_e_c162_evidence_container as diff
from fold_lm.v05_benchmarks import gate_e_c163_live_container_bridge as c


def fixture(bit=0, source="persisted-snapshot:test", key="selected"):
    b=terminal.BoundRequest("scope|q","scope",key,source,1,1)
    ref=EvidenceRef(key,Provenance(source,ProvenanceKind.OBSERVED,1,1))
    state=EvidenceState(1,1,(ref,))
    working=[1.,1.,1.,float(bit),.125,-.25,.375,-.5]
    last=dict(action=0,status="RESOLVED",value=bit,reference=asdict(ref),working=working,
              evidence_time=1,revision=1,working_evidence_time=1)
    result=dict(terminal="ANSWER_ACTION",steps=[dict(action=2),last],final_value=bit,
                final_reference=asdict(ref),final_evidence=asdict(state),final_working=working)
    return b, result


def profile():
    n=c.EPISODES
    s=dict(episodes=n,failed_episodes=0,ranking_queries=n,candidate_scores=64*n,
        controller_decisions=2*n,acquisitions=n,publications=n,retrieval_calls=2*n,vectors_scored=128*n,
        answered=n,weight_mutations=0,output_mutations=0,serialization_failures=0,
        router_episodes={str(k):n//3 for k in c.ROUTERS},ranker_replay_cases=41472,
        original12_replay_cases=288,c159_replay_calls=6528,minimum_controller_margin=6.,
        arms={a:{o:dict(cases=20736,binding_correct=20736,semantic_correct=20727 if a==c.ARMS[0] else 20736)
                 for o in c.ORDERS} for a in c.ARMS},answer_values={"0":34992,"1":47952},source_codes_preserved=True)
    s["emission"]=dict(native_emitter_calls=n,adapted_emitter_calls=n,native_tuple=n,adapted_list=n,
        content_unchanged=n,native_rejected=n,input_preserved=n,guard_emitter_calls=768,
        guard_control_cases=768,guard_control_failed=0,guard_control_passed=768,guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":n},adapted_status_counts={"ANSWERED":n},
        adapted_reason_counts={"OBSERVED_VALUE":n})
    return s


class V05C163LiveContainerBridgeTests(unittest.TestCase):
    def test_only_native_observations_container_changes(self):
        _,r=fixture();before=deepcopy(r);converted=c.normalize_terminal(r)
        self.assertEqual(r,before);self.assertIsNot(converted,r)
        self.assertIsInstance(r["final_evidence"]["observations"],tuple)
        self.assertIsInstance(converted["final_evidence"]["observations"],list)
        self.assertEqual(old.blob(converted),old.blob(r))
        self.assertIs(converted["steps"],r["steps"])

    def test_list_input_is_not_rewritten(self):
        _,r=fixture();r=c.normalize_terminal(r)
        self.assertIs(c.normalize_terminal(r),r)

    def test_missing_or_bad_container_is_not_repaired(self):
        b,r=fixture()
        for value in (None,{},"bad",3):
            q=deepcopy(r);q["final_evidence"]["observations"]=value
            self.assertIs(c.normalize_terminal(q),q)
            self.assertEqual(c.emit_live(b,b.request_id,q).reason,"MALFORMED_EVIDENCE")

    def test_bad_terminal_is_delegated_to_old_emitter(self):
        b,_=fixture()
        for value in (None,[],{},"bad"):
            self.assertEqual(c.emit_live(b,b.request_id,value).status,"REJECTED")

    def test_native_control_rejects_but_live_zero_is_answered(self):
        b,r=fixture(0)
        self.assertEqual(terminal.emit_terminal(b,b.request_id,r).reason,"MALFORMED_EVIDENCE")
        self.assertTrue(diff.bound_output(c.emit_live(b,b.request_id,r),b,0))

    def test_native_control_rejects_but_live_one_is_answered(self):
        b,r=fixture(1)
        self.assertEqual(terminal.emit_terminal(b,b.request_id,r).reason,"MALFORMED_EVIDENCE")
        self.assertTrue(diff.bound_output(c.emit_live(b,b.request_id,r),b,1))

    def test_wrong_request_still_rejected(self):
        b,r=fixture();out=c.emit_live(b,b.request_id+"x",r)
        self.assertEqual((out.status,out.reason),("REJECTED","REQUEST_MISMATCH"));self.assertIsNone(out.value)

    def test_all_six_guards_through_native_adapter(self):
        for bit in (0,1):
            b,r=fixture(bit);probes=c.live_fault_controls(b,r)
            self.assertEqual(set(probes),set(diff.FAULT_REASONS))
            self.assertTrue(all(p["passed"] for p in probes.values()))

    def test_guard_controls_preserve_native_source(self):
        b,r=fixture();before=deepcopy(r);c.live_fault_controls(b,r);self.assertEqual(r,before)

    def test_boolean_value_is_not_coerced_into_bit(self):
        b,r=fixture();r["final_value"]=False;r["steps"][-1]["value"]=False
        self.assertEqual(c.emit_live(b,b.request_id,r).reason,"PAYLOAD_MISMATCH")

    def test_reference_provenance_is_not_corrected(self):
        b,r=fixture();r["final_reference"]["provenance"]["kind"]="hypothesis"
        self.assertEqual(c.emit_live(b,b.request_id,r).reason,"REFERENCE_MISMATCH")

    def test_audit_records_native_and_adapted_calls_separately(self):
        b,r=fixture();audit=c.AuditedEmitter();out=audit(b,b.request_id,r);s=audit.summary()
        self.assertEqual(out.status,"ANSWERED");self.assertTrue(all(audit.last["checks"].values()))
        self.assertEqual((s["native_emitter_calls"],s["adapted_emitter_calls"],s["guard_emitter_calls"]),(1,1,6))

    def test_guard_selection_is_once_per_source_key_not_per_bit(self):
        audit=c.AuditedEmitter()
        for bit in (0,1):
            b,r=fixture(bit);audit(b,b.request_id,r)
        self.assertEqual(audit.summary()["guard_emitter_calls"],6)
        b,r=fixture(source="persisted-snapshot:other");audit(b,b.request_id,r)
        self.assertEqual(audit.summary()["guard_emitter_calls"],12)

    def test_finite_ungrounded_result_remains_rejected(self):
        b,r=fixture();r["steps"][-1]["status"]="REFERENCE_UNBOUND"
        out=c.AuditedEmitter()(b,b.request_id,r)
        self.assertEqual(out.reason,"ANSWER_NOT_GROUNDED");self.assertIsNone(out.value)

    def test_missing_payload_probe_is_saved_not_invalid(self):
        b,r=fixture();r["final_value"]=None;r["steps"][-1]["value"]=None
        audit=c.AuditedEmitter();out=audit(b,b.request_id,r)
        self.assertEqual(out.status,"REJECTED");self.assertEqual(audit.summary()["guard_control_failed"],6)

    def test_normalizer_has_no_label_value_or_scope_interface(self):
        self.assertEqual(list(inspect.signature(c.normalize_terminal).parameters),["result"])
        self.assertEqual(list(inspect.signature(c.emit_live).parameters),["binding","source_request_id","result"])

    def test_gate_accepts_full_registered_profile(self):
        self.assertTrue(c.gate(profile()))

    def test_gate_rejects_dropped_episode(self):
        s=profile();s["episodes"]-=1;self.assertFalse(c.gate(s))

    def test_gate_does_not_repair_known_semantic_errors(self):
        s=profile();s["arms"]["WITHIN_FACTOR"]["CANONICAL"]["semantic_correct"]=20736
        self.assertFalse(c.gate(s))

    def test_gate_rejects_wrong_cost_or_router_coverage(self):
        for key in ("retrieval_calls","vectors_scored","controller_decisions"):
            s=profile();s[key]-=1;self.assertFalse(c.gate(s))
        s=profile();s["router_episodes"][str(c.ROUTERS[0])]-=1;self.assertFalse(c.gate(s))

    def test_gate_rejects_guard_mutation_or_missing_native_control(self):
        for key in ("native_rejected","input_preserved","guard_control_passed","native_emitter_calls"):
            s=profile();s["emission"][key]-=1;self.assertFalse(c.gate(s))

    def test_gate_rejects_tie_nonfinite_or_wrong_values(self):
        for value in (0,float("nan"),float("inf")):
            s=profile();s["minimum_controller_margin"]=value;self.assertFalse(c.gate(s))
        s=profile();s["answer_values"]["0"]-=1;self.assertFalse(c.gate(s))

    def test_gate_requires_historical_source_preservation(self):
        s=profile();s["source_codes_preserved"]=False;self.assertFalse(c.gate(s))

    def test_adapted_guard_rejection_is_not_replaced_by_native(self):
        b,r=fixture();r["final_reference"]["evidence_id"]="wrong"
        out=c.AuditedEmitter()(b,b.request_id,r)
        self.assertEqual(out.reason,"REFERENCE_MISMATCH")

    def test_native_execute_selected_wires_actual_state_to_new_adapter(self):
        # Actual C160 execute_selected + core state + C159 emitter; cycle callback
        # is controlled. This specifically covers the tuple boundary missed before.
        from fold_lm.v05.state import WorkingState, BudgetState
        ref=EvidenceRef("selected",Provenance("persisted-snapshot:test",ProvenanceKind.OBSERVED,1,1))
        full=EvidenceState(1,1,(ref,))
        binding=NS(source_id=ref.provenance.source_id,source_sha256="h",index_fingerprint="i",source_path="p",
                   evidence_time=1,revision=1,adapter=NS(calls=0,vectors=0))
        def cycle(router,read,request,state,working,budget,registry,permission,ops,deliver):
            self.assertEqual(state.observations,());self.assertIsInstance(working,WorkingState)
            binding.adapter.calls+=2;binding.adapter.vectors+=128
            _,r=fixture();return r
        audit=c.AuditedEmitter()
        api=NS(Request=lambda **kw:NS(**kw),EvidenceRef=EvidenceRef,Provenance=Provenance,OBSERVED=ProvenanceKind.OBSERVED,
               ReadRequest=lambda *a:NS(args=a),WorkingState=WorkingState,BudgetState=BudgetState,
               Permission=lambda value:NS(allowed=value),cycle=cycle,BoundRequest=terminal.BoundRequest,emit=audit)
        r,out,_,_,mutated=old.execute_selected("scope","q",dict(key="selected",domain="d",schema="s",operations=["READ"]),
                                            None,full,binding,{},api,None,1)
        self.assertEqual(out.status,"ANSWERED");self.assertEqual(out.value,0);self.assertFalse(mutated)
        self.assertEqual((r["retrieval_calls"],r["vectors_scored"]),(2,128))
        self.assertEqual(full.observations,(ref,))

    def test_measured_input_mutation_is_not_hidden(self):
        b,r=fixture();original=terminal.emit_terminal
        def bad(binding,rid,result):
            out=original(binding,rid,result)
            if isinstance(result["final_evidence"]["observations"],list):
                result["final_working"][4]=123.
            return out
        audit=c.AuditedEmitter()
        with patch.object(terminal,"emit_terminal",side_effect=bad):
            audit(b,b.request_id,r)
        self.assertFalse(audit.last["checks"]["input_preserved"])


if __name__ == "__main__":
    unittest.main()
