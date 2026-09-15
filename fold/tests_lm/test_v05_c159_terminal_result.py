from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError, replace
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as c


def plan_row(index=0, order="CANONICAL"):
    key=f"record-{index:02}"
    scope=f"C153|20261721|GLOBAL_CONCEPT|{order}"
    request=dict(request_id=scope+"|"+key,scope_id=scope,key=key,domain="test",schema="bit",
        operations=["read"],source_path="/snapshot/"+order,source_sha256="a"*64,index_fingerprint="b"*64,
        request_epoch=1,provider_generation=1)
    md={k:request[k] for k in ("source_sha256","index_fingerprint","source_path")}
    sid="persisted-snapshot:"+hashlib.sha256(json.dumps(md,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    ref=dict(evidence_id=key,provenance=dict(source_id=sid,kind="observed",evidence_time=1,revision=1))
    return dict(order=order,key=key,request=request,reference=ref)


def episode(p=None, scenario="WARM_PRESENT", value=0, refs=None, seed=c.SEEDS[0]):
    p=plan_row() if p is None else p; ref=p["reference"]
    refs={p["key"]:ref} if refs is None else refs
    warm=scenario == c.SCENARIOS[0]; recovered=scenario == c.SCENARIOS[1]; success=warm or recovered
    acq=int(scenario in c.SCENARIOS[1:3]); initial=int(scenario != c.SCENARIOS[4])
    actions=[0] if warm else [2,0 if recovered else 5]
    statuses=["RESOLVED"] if warm else ["REFERENCE_UNBOUND","RESOLVED" if recovered else "REFERENCE_UNBOUND"]
    steps=[]
    for i,(a,status) in enumerate(zip(actions,statuses)):
        present=warm or (recovered and i == 1)
        logits=[-2.]*6;logits[a]=3.
        step=dict(action=a,status=status,value=value if present else None,reference=deepcopy(ref) if present else None,
            logits=logits,available=i == 0,working=[1.,1.,float(present),float(value) if present else 0.,.125,-.25,.375,-.5],
            internal_step=8+i,internal_remaining=2-i,acquisition_remaining=initial-(acq if i else 0),
            evidence_time=1,revision=1,working_evidence_time=1,authority=None,admission=None,projection=None,fetched=None)
        if i == 0 and not warm:
            step["authority"]="PERMISSION_DENIED" if scenario == c.SCENARIOS[3] else "BUDGET_EXHAUSTED" if scenario == c.SCENARIOS[4] else "AUTHORIZED"
            step["admission"]="COMMITTED" if recovered else "MISSING" if scenario == c.SCENARIOS[2] else None
            step["projection"]="ADDED" if recovered else None
            if acq: step["fetched"]={"key":p["key"],"evidence_value":value}
        steps.append(step)
    wanted=deepcopy(refs)
    if not success: del wanted[p["key"]]
    result=dict(terminal="ANSWER_ACTION" if success else "STOP_UNRESOLVED",steps=steps,
        final_value=value if success else None,final_reference=deepcopy(ref) if success else None,
        final_evidence=dict(evidence_time=1,revision=1,observations=list(wanted.values())),
        final_budget=dict(internal_steps_remaining=3-len(actions),acquisitions_remaining=initial-acq),
        final_internal_step=7+len(actions),final_working=steps[-1]["working"].copy(),acquisitions=acq,
        publications=int(recovered),inbox_entries=int(recovered),input_mutations=0,original_state_preserved=True,
        original_working_preserved=True,retrieval_calls=(1,2,1,0,0)[c.SCENARIOS.index(scenario)],
        vectors_scored=64*(1,2,1,0,0)[c.SCENARIOS.index(scenario)])
    return dict(router_seed=seed,order=p["order"],key=p["key"],source_request_id=p["request"]["request_id"],
        scenario=scenario,result=result,assessment=dict(passed=True,checks={"fabricated":True},expected_actions=actions,margins=[5.]*len(actions)))


class V05C159TerminalResultTests(unittest.TestCase):
    def setUp(self):
        self.p=plan_row();self.b=c._binding(self.p);self.row=episode(self.p)

    def emit(self,row=None,binding=None,rid=None):
        row=self.row if row is None else row
        return c.emit_terminal(self.b if binding is None else binding,
            row["source_request_id"] if rid is None else rid,row["result"])

    def test_zero_is_answered_not_unresolved(self):
        out=self.emit();self.assertEqual((out.status,out.value),("ANSWERED",0))
        self.assertIs(type(out.value),int)

    def test_one_is_copied_from_final_working(self):
        self.assertEqual(self.emit(episode(value=1)).value,1)

    def test_cold_recovered_value_emits_answer(self):
        self.assertEqual(self.emit(episode(scenario="COLD_RECOVER")).status,"ANSWERED")

    def test_missing_delivery_returns_none_without_fetched_payload(self):
        row=episode(scenario="COLD_MISSING_DELIVERY",value=1);out=self.emit(row)
        self.assertEqual((out.status,out.reason),("UNRESOLVED","MISSING_DELIVERY"))
        self.assertTrue(c._no_payload(out));self.assertNotIn("fetched",c._bytes(asdict(out)).decode())
        self.assertEqual(row["result"]["steps"][0]["fetched"]["evidence_value"],1)

    def test_permission_denied_reason_comes_from_runtime(self):
        out=self.emit(episode(scenario="COLD_PERMISSION_DENIED"))
        self.assertEqual(out.reason,"PERMISSION_DENIED");self.assertTrue(c._no_payload(out))

    def test_budget_exhaustion_has_no_answer(self):
        out=self.emit(episode(scenario="COLD_BUDGET_EXHAUSTED"))
        self.assertEqual(out.reason,"BUDGET_EXHAUSTED");self.assertIsNone(out.value)

    def test_wrong_request_rejected_for_both_terminal_types(self):
        for scenario in c.SCENARIOS:
            out=self.emit(episode(scenario=scenario),rid="other")
            self.assertEqual(out.reason,"REQUEST_MISMATCH");self.assertTrue(c._no_payload(out))

    def test_wrong_provenance_with_same_payload_rejected(self):
        self.row["result"]["final_reference"]["provenance"]["source_id"]="persisted-snapshot:other"
        self.assertEqual(self.emit().reason,"REFERENCE_MISMATCH")

    def test_other_present_record_cannot_replace_selected_reference(self):
        other=plan_row(1)["reference"]
        r=self.row["result"];r["final_reference"]=other;r["steps"][-1]["reference"]=other
        r["final_evidence"]["observations"]=[other]
        self.assertEqual(self.emit().reason,"REFERENCE_MISMATCH")

    def test_missing_final_state_reference_rejected(self):
        self.row["result"]["final_evidence"]["observations"]=[]
        self.assertEqual(self.emit().reason,"REFERENCE_MISMATCH")

    def test_duplicate_record_ids_rejected(self):
        refs=self.row["result"]["final_evidence"]["observations"];refs.append(deepcopy(refs[0]))
        self.assertEqual(self.emit().reason,"REFERENCE_MISMATCH")

    def test_hypothesis_cannot_be_output_as_observation(self):
        r=self.row["result"]
        for ref in [r["final_reference"],r["steps"][-1]["reference"],r["final_evidence"]["observations"][0]]:
            ref["provenance"]["kind"]="hypothesis"
        self.assertEqual(self.emit().status,"REJECTED")

    def test_final_value_disagreement_rejected(self):
        self.row["result"]["final_value"]=1
        self.assertEqual(self.emit().reason,"PAYLOAD_MISMATCH")

    def test_bool_and_non_bit_values_rejected(self):
        for value in (False,True,2,-1,.5,float("nan")):
            row=episode();row["result"]["final_value"]=value
            self.assertEqual(self.emit(row).reason,"PAYLOAD_MISMATCH")

    def test_last_step_value_disagreement_rejected(self):
        self.row["result"]["steps"][-1]["value"]=1
        self.assertEqual(self.emit().reason,"PAYLOAD_MISMATCH")

    def test_nonfinite_or_wrong_width_working_rejected(self):
        for slots in ([1.]*7,[float("nan")]*8,[True]*8):
            row=episode();row["result"]["final_working"]=slots
            self.assertEqual(self.emit(row).reason,"WORKING_MISMATCH")

    def test_changed_final_working_rejected(self):
        self.row["result"]["final_working"][3]=1.
        self.assertEqual(self.emit().reason,"WORKING_MISMATCH")

    def test_clock_mismatch_rejected(self):
        self.row["result"]["final_evidence"]["revision"]=2
        self.assertEqual(self.emit().reason,"CLOCK_MISMATCH")

    def test_forced_answer_without_presence_rejected(self):
        row=episode(scenario="COLD_MISSING_DELIVERY")
        row["result"]["terminal"]="ANSWER_ACTION";row["result"]["steps"][-1]["action"]=0
        self.assertEqual(self.emit(row).reason,"ANSWER_NOT_GROUNDED")

    def test_unresolved_stale_value_is_not_zero_answer(self):
        row=episode(scenario="COLD_PERMISSION_DENIED");row["result"]["final_value"]=0
        self.assertEqual(self.emit(row).reason,"UNRESOLVED_PAYLOAD_LEAK")

    def test_terminal_action_mismatch_and_other_actions_rejected(self):
        for action in (1,2,3,4,5,True):
            row=episode();row["result"]["steps"][-1]["action"]=action
            self.assertEqual(self.emit(row).reason,"TERMINAL_ACTION_MISMATCH")

    def test_malformed_terminal_returns_rejected_not_payload(self):
        for result in ({},None,{"steps":[]},{"steps":[None]}):
            out=c.emit_terminal(self.b,self.b.request_id,result)
            self.assertEqual(out.status,"REJECTED");self.assertTrue(c._no_payload(out))

    def test_output_and_binding_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):self.emit().value=1
        with self.assertRaises(FrozenInstanceError):self.b.request_id="other"

    def test_emitter_does_not_mutate_or_consume_source(self):
        before=deepcopy(self.row);a=self.emit();b=self.emit()
        self.assertEqual(a,b);self.assertEqual(before,self.row)

    def test_json_roundtrip_preserves_zero_and_none(self):
        for row in (episode(),episode(value=1),episode(scenario="COLD_PERMISSION_DENIED")):
            out=asdict(self.emit(row));self.assertEqual(json.loads(c._bytes(out)),out)

    def test_emitter_interface_has_no_scenario_or_expected_value(self):
        self.assertEqual(list(inspect.signature(c.emit_terminal).parameters),["binding","source_request_id","result"])

    def test_bound_request_and_source_digest_validation(self):
        with self.assertRaises(ValueError):replace(self.b,scope_id="wrong")
        with self.assertRaises(ValueError):replace(self.b,evidence_time=True)
        p=deepcopy(self.p);p["request"]["source_path"]="/different"
        with self.assertRaises(c.InvalidInput):c._binding(p)

    def test_safe_paths_reject_windows_and_posix_escapes(self):
        for name in ("../x","..\\x","/x","C:\\x",".","..",""):
            with self.assertRaises(c.InvalidInput):c._safe_file(Path("/tmp"),name)

    def test_all_registered_fault_variants_are_rejected(self):
        for scenario in c.SCENARIOS:
            row=episode(scenario=scenario);before=deepcopy(row)
            for _,rid,result,reason in c._variants(row):
                out=c.emit_terminal(self.b,rid,result)
                self.assertEqual((out.status,out.reason),("REJECTED",reason));self.assertTrue(c._no_payload(out))
            self.assertEqual(row,before)

    def test_valid_source_rows_reaggregate_all_scenarios(self):
        refs={self.p["key"]:self.p["reference"]};known={}
        for scenario in c.SCENARIOS:
            row=episode(scenario=scenario)
            c._validate_row(row,self.p,c.SEEDS[0],scenario,refs,known)
        self.assertEqual(len(known),1)

    def test_source_row_rejects_changed_id_action_value_margin_or_cost(self):
        refs={self.p["key"]:self.p["reference"]}
        for field,value in (("source_request_id","wrong"),("key","wrong")):
            row=episode();row[field]=value
            with self.assertRaises(c.InvalidInput):c._validate_row(row,self.p,c.SEEDS[0],c.SCENARIOS[0],refs,{})
        for field,value in (("retrieval_calls",2),("final_value",True),("final_internal_step",20)):
            row=episode();row["result"][field]=value
            with self.assertRaises(c.InvalidInput):c._validate_row(row,self.p,c.SEEDS[0],c.SCENARIOS[0],refs,{})
        row=episode();row["assessment"]["margins"]=[1.]
        with self.assertRaises(c.InvalidInput):c._validate_row(row,self.p,c.SEEDS[0],c.SCENARIOS[0],refs,{})

    def test_source_header_rejects_wrong_identity(self):
        for header in ({},{"experiment_id":c.SOURCE_ID,"status":"FAIL"}):
            with self.assertRaises(c.InvalidInput):c._header(header)

    def test_gate_keeps_exact_counts_and_zero_failures(self):
        s=dict(source_episodes=1920,emitter_calls=6528,base_status_counts={"ANSWERED":768,"UNRESOLVED":1152},
            answer_values={"0":324,"1":444},rejected_controls=c.REJECTION_COUNTS.copy(),failed_cases=0,input_mutations=0,serialization_failures=0)
        self.assertTrue(c._gate(s))
        for field in ("emitter_calls","failed_cases","input_mutations","serialization_failures"):
            bad=deepcopy(s);bad[field]+=1;self.assertFalse(c._gate(bad))


if __name__ == "__main__":unittest.main()
