"""C162 helpers use the actual EvidenceState and unchanged C159 emitter API."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fold_lm.v05_benchmarks import gate_e_c162_evidence_container as c


def fixture(bit=0):
    binding = c.terminal.BoundRequest("scope|q", "scope", "selected", "persisted-snapshot:test", 1, 1)
    p = c.Provenance(binding.source_id, c.ProvenanceKind.OBSERVED, 1, 1)
    state = c.EvidenceState(1, 1, (c.EvidenceRef("selected", p), c.EvidenceRef("other", p)))
    final = c.final_state_for(state, "selected")
    slots = [1., 1., 1., float(bit), .125, -.25, .375, -.5]
    step = dict(action=0, status="RESOLVED", value=bit, reference=binding.reference(), working=slots,
                evidence_time=1, revision=1, working_evidence_time=1)
    native = dict(terminal="ANSWER_ACTION", steps=[{"action":2}, step], final_value=bit,
                  final_reference=binding.reference(), final_working=slots, final_evidence=asdict(final))
    saved = asdict(c.terminal.emit_terminal(binding, binding.request_id, native))
    return binding, state, native, saved


def profile():
    n = c.EPISODES
    return dict(episodes=n, pair_passed=n, pair_failed=0, native_reproduced=n,
        native_malformed_evidence=n, list_bound=n, selected_payload_correct=n,
        content_unchanged=n, input_preserved=n, serialization_ok=n, reconstructed_state_matches=n,
        source_state_files=48, source_trace_files=48, pair_emitter_calls=2*n,
        guard_control_cases=768, guard_control_passed=768, guard_control_failed=0,
        guard_record_bindings=128, false_pair_checks={}, router_episodes={str(r):n//3 for r in c.ROUTERS},
        arms={a:{o:dict(cases=20736, list_bound=20736, semantic_correct=20727 if a==c.ARMS[0] else 20736)
              for o in c.ORDERS} for a in c.ARMS}, list_values={"0":40000,"1":42944})


class V05C162EvidenceContainerTests(unittest.TestCase):
    def test_real_state_asdict_retains_tuple(self):
        _, state, native, _ = fixture()
        self.assertIs(type(asdict(state)["observations"]), tuple)
        self.assertIs(type(native["final_evidence"]["observations"]), tuple)

    def test_json_roundtrip_erases_tuple_difference(self):
        _, _, r, _ = fixture()
        loaded = json.loads(c.blob(r))
        self.assertIs(type(loaded["final_evidence"]["observations"]), list)
        self.assertEqual(c.blob(r), c.blob(loaded))

    def test_unchanged_emitter_rejects_native_but_accepts_list_zero(self):
        b, _, r, saved = fixture(0)
        a, out, checks = c.measure_pair(b, r, saved)
        self.assertEqual((a.status,a.reason),("REJECTED","MALFORMED_EVIDENCE"))
        self.assertEqual((out.status,out.value),("ANSWERED",0))
        self.assertTrue(all(checks.values()))

    def test_unchanged_emitter_rejects_native_but_accepts_list_one(self):
        b, _, r, saved = fixture(1)
        _, out, checks = c.measure_pair(b,r,saved)
        self.assertEqual(out.value,1)
        self.assertTrue(all(checks.values()))

    def test_list_only_changes_one_container(self):
        _, _, r, _ = fixture(); q = c.list_only(r)
        self.assertIsNot(r,q)
        for key in r:
            if key != "final_evidence": self.assertIs(r[key],q[key])
        for key in r["final_evidence"]:
            if key != "observations": self.assertIs(r["final_evidence"][key],q["final_evidence"][key])
        self.assertEqual(list(r["final_evidence"]["observations"]),q["final_evidence"]["observations"])
        self.assertEqual(c.blob(r),c.blob(q))

    def test_list_only_does_not_silently_accept_arbitrary_containers(self):
        _, _, r, _ = fixture()
        for value in (None, {}, [], "bad"):
            bad=deepcopy(r);bad["final_evidence"]["observations"]=value
            with self.assertRaises(c.InvalidInput):c.list_only(bad)

    def test_cold_restore_preserves_source_but_appends_selected(self):
        _, state, _, _ = fixture()
        final = c.final_state_for(state,"selected")
        self.assertEqual([r.evidence_id for r in state.observations],["selected","other"])
        self.assertEqual([r.evidence_id for r in final.observations],["other","selected"])

    def test_missing_selected_reference_is_invalid(self):
        _, state, _, _ = fixture()
        with self.assertRaises(c.InvalidInput):c.final_state_for(state,"missing")

    def test_reconstruct_requires_exact_digest_and_reference_order(self):
        _, state, r, _ = fixture()
        final = c.final_state_for(state,"selected")
        compact = {k:deepcopy(v) for k,v in r.items() if k!="final_evidence"}
        compact.update(final_evidence_sha256=hashlib.sha256(c.blob(asdict(final))).hexdigest(),final_reference_count=2)
        self.assertEqual(c.reconstruct_cycle(compact,final),r)
        with self.assertRaises(c.InvalidInput):c.reconstruct_cycle(compact,state)

    def test_reconstruct_rejects_wrong_reference_count(self):
        _, state, r, _=fixture(); final=c.final_state_for(state,"selected")
        compact={k:v for k,v in r.items() if k!="final_evidence"}
        compact.update(final_evidence_sha256=hashlib.sha256(c.blob(asdict(final))).hexdigest(),final_reference_count=3)
        with self.assertRaises(c.InvalidInput):c.reconstruct_cycle(compact,final)

    def test_decode_roundtrip_uses_actual_core_state(self):
        _,state,_,_=fixture()
        self.assertEqual(c.decode_state(json.loads(c.blob(asdict(state)))),state)

    def test_decode_rejects_hypothesis_and_duplicate(self):
        _,state,_,_=fixture(); raw=json.loads(c.blob(asdict(state)))
        wrong=deepcopy(raw);wrong["observations"][0]["provenance"]["kind"]="hypothesis"
        with self.assertRaises(ValueError):c.decode_state(wrong)
        wrong=deepcopy(raw);wrong["observations"].append(wrong["observations"][0])
        with self.assertRaises(ValueError):c.decode_state(wrong)

    def test_decode_rejects_extra_fields_and_wrong_container(self):
        _,state,_,_=fixture(); raw=json.loads(c.blob(asdict(state)))
        for wrong in (dict(raw,extra=1),dict(raw,observations=None)):
            with self.assertRaises(c.InvalidInput):c.decode_state(wrong)

    def test_pair_has_no_semantic_target_interface(self):
        names=set(inspect.signature(c.measure_pair).parameters)
        self.assertEqual(names,{"binding","native","saved_output","emit"})

    def test_pair_preserves_inputs(self):
        b,_,r,saved=fixture(); before=deepcopy(r)
        c.measure_pair(b,r,saved)
        self.assertEqual(r,before)
        self.assertIs(type(r["final_evidence"]["observations"]),tuple)

    def test_measured_rejection_is_retained_as_negative(self):
        b,_,r,saved=fixture()
        def reject(binding,rid,result):
            return c.terminal.TerminalResult(c.terminal.SCHEMA,rid,binding.scope_id,"REJECTED","OTHER")
        a,out,checks=c.measure_pair(b,r,saved,emit=reject)
        self.assertEqual(out.reason,"OTHER");self.assertFalse(checks["list_bound"])
        self.assertFalse(all(checks.values()))

    def test_mutation_is_measured_not_hidden(self):
        b,_,r,saved=fixture()
        def mutate(binding,rid,result):
            out=c.terminal.emit_terminal(binding,rid,result)
            result["steps"][-1]["working"][7]=99.
            return out
        _,_,checks=c.measure_pair(b,r,saved,emit=mutate)
        self.assertFalse(checks["input_preserved"])

    def test_wrong_saved_native_output_is_not_accepted(self):
        b,_,r,saved=fixture();saved["reason"]="OTHER"
        _,_,checks=c.measure_pair(b,r,saved)
        self.assertFalse(checks["native_reproduced"])

    def test_bound_output_rejects_bool_wrong_key_and_value(self):
        b,_,r,_=fixture();out=c.terminal.emit_terminal(b,b.request_id,c.list_only(r))
        self.assertTrue(c.bound_output(out,b,0))
        for bad in (replace(out,value=False),replace(out,value=1),replace(out,record_key="other")):
            self.assertFalse(c.bound_output(bad,b,0))

    def test_all_six_guards_remain_effective_for_both_bits(self):
        for bit in (0,1):
            b,_,r,_=fixture(bit)
            controls=c.fault_controls(b,c.list_only(r))
            self.assertEqual(set(controls),set(c.FAULT_REASONS))
            self.assertTrue(all(x["passed"] for x in controls.values()))

    def test_fault_probes_do_not_mutate_source(self):
        b,_,r,_=fixture();q=c.list_only(r);before=deepcopy(q)
        c.fault_controls(b,q)
        self.assertEqual(q,before)

    def test_gate_accepts_only_full_registered_profile(self):
        self.assertTrue(c.gate(profile()))
        for key in ("episodes","list_bound","selected_payload_correct","guard_control_passed","reconstructed_state_matches"):
            p=profile();p[key]-=1;self.assertFalse(c.gate(p))

    def test_gate_preserves_known_control_errors(self):
        p=profile();p["arms"]["WITHIN_FACTOR"]["CANONICAL"]["semantic_correct"]=20736
        self.assertFalse(c.gate(p))
        p=profile();p["arms"]["GLOBAL_CONCEPT"]["PERMUTED"]["semantic_correct"]-=1
        self.assertFalse(c.gate(p))

    def test_gate_rejects_guard_and_mutation_failure(self):
        for key in ("guard_control_failed","pair_failed"):
            p=profile();p[key]=1;self.assertFalse(c.gate(p))
        p=profile();p["false_pair_checks"]={"input_preserved":1};self.assertFalse(c.gate(p))

    def test_safe_child_rejects_escape(self):
        for name in ("..","../x","a/b",r"a\b",r"C:\x",""):
            with self.assertRaises(c.InvalidInput):c.safe_child(Path("."),name)

    def test_stream_identity_rejects_duplicate_or_missing(self):
        records=[dict(seed=s,arm=a,order=o) for s in c.HEAD_SEEDS for a in c.ARMS for o in c.ORDERS]
        self.assertEqual(len(c.stream_index(records)),48)
        for bad in (records[:-1],records[:-1]+[records[0]]):
            with self.assertRaises(c.InvalidInput):c.stream_index(bad)

    def test_protected_bytes_are_rechecked_at_end(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"a";p.write_bytes(b"a");inputs={};c.protect(p,c.sha(p),inputs)
            c.check_inputs(inputs);p.write_bytes(b"b")
            with self.assertRaises(c.InvalidInput):c.check_inputs(inputs)

    def test_locate_requires_unique_hash_bound_source(self):
        with TemporaryDirectory() as d:
            a=Path(d)/"a"/"summary.json";b=Path(d)/"b"/"summary.json"
            self.assertEqual(c.locate({a:"h"},"h","summary.json"),a.resolve())
            for pins in ({},{a:"h",b:"h"}):
                with self.assertRaises(c.InvalidInput):c.locate(pins,"h","summary.json")

    def test_blob_rejects_nonfinite(self):
        with self.assertRaises(ValueError):c.blob({"value":float("nan")})


class V05C162OfflineRunTests(unittest.TestCase):
    def test_small_synthetic_full_loader_run_saves_valid_negative_and_preserves_inputs(self):
        """48 streams x 3 rows: loader/writer test, not the 82,944-row formal run."""
        import gzip
        from unittest.mock import patch
        with TemporaryDirectory() as directory:
            root=Path(directory);d154=root/"c154";d151=root/"c151";d160=root/"c160";d161=root/"c161"
            for p in (d154,d151,d160,d161):p.mkdir()
            def save(path,value):path.write_bytes(c.blob(value));return c.sha(path)
            descriptors=[f"descriptor-{i}" for i in range(64)]
            keys=["c152-"+hashlib.sha256(d.encode()).hexdigest() for d in descriptors]
            suite=dict(descriptors=descriptors,queries=[dict(case_id=str(i),text=f"text-{i}",expected_address=i) for i in range(3)])
            mh=save(d151/"evaluation-manifest.json",suite)
            ranks=[dict(seed=s,arms={a:dict(results=[dict(predicted_address=i) for i in range(3)]) for a in c.ARMS}) for s in c.HEAD_SEEDS]
            rh=save(d151/"summary.json",dict(records=ranks))
            pinned={str(d151/"evaluation-manifest.json"):mh,str(d151/"summary.json"):rh}
            records154=[];records160=[];pins161={};corpus_hashes={}
            for order in c.ORDERS:
                d=root/order;d.mkdir()
                h=save(d/"records.json",dict(records=[dict(key=k,evidence_value=i%2) for i,k in enumerate(keys)]))
                # Distinct file bytes, as in the two original storage orderings.
                if order=="PERMUTED":
                    h=save(d/"records.json",dict(records=list(reversed([dict(key=k,evidence_value=i%2) for i,k in enumerate(keys)]))))
                corpus_hashes[order]=h;pinned[str(d/"records.json")]=h
            for seed in c.HEAD_SEEDS:
                for arm in c.ARMS:
                    for order in c.ORDERS:
                        p=c.Provenance("persisted-snapshot:"+order,c.ProvenanceKind.OBSERVED,1,1)
                        full=c.EvidenceState(1,1,tuple(c.EvidenceRef(k,p) for k in keys))
                        fn=f"state-{seed}-{arm}-{order}.json";h=save(d154/fn,asdict(full))
                        records154.append(dict(seed=seed,arm=arm,order=order,state_file=fn,state_sha256=h))
                        pinned[str(d154/fn)]=h
                        trace=d160/f"queries-{seed}-{arm}-{order}.jsonl.gz"
                        with gzip.open(trace,"wt",encoding="utf-8") as f:
                            for j in range(3):
                                scope=f"C160|{seed}|{arm}|{order}";b=c.terminal.BoundRequest(scope+"|"+str(j),scope,keys[j],p.source_id,1,1)
                                final=c.final_state_for(full,keys[j]);_,_,r,_=fixture(j%2)
                                r["final_reference"]=b.reference();r["steps"][-1]["reference"]=b.reference();r["final_evidence"]=asdict(final)
                                saved=asdict(c.terminal.emit_terminal(b,b.request_id,r))
                                compact={k:v for k,v in r.items() if k!="final_evidence"}
                                compact.update(final_evidence_sha256=hashlib.sha256(c.blob(asdict(final))).hexdigest(),final_reference_count=64)
                                row=dict(case_id=str(j),text=f"text-{j}",router_seed=c.ROUTERS[j%3],selected_key=keys[j],
                                    cycle=compact,cycle_assessment=dict(passed=True,checks=dict(fixture=True)),
                                    output=saved,output_assessment=dict(bound=False,semantic_correct=False,serialization_ok=True),passed=False)
                                f.write(json.dumps(row)+"\n")
                        h=c.sha(trace);pins161[str(trace)]=h
                        records160.append(dict(seed=seed,arm=arm,order=order,file=trace.name,sha256=h,serialized_bytes=trace.stat().st_size))
            h154=save(d154/"summary.json",dict(records=records154));pinned[str(d154/"summary.json")]=h154
            n=144
            p160=dict(experiment_id="C160-v5e-live-query-to-terminal-result",commit_sha=c.C160_COMMIT,status="FAIL",
                diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
                summary=dict(episodes=n,failed_episodes=n,answered=0),records=records160,input_sha256=pinned)
            h160=save(d160/"summary.json",p160);pins161[str(d160/"summary.json")]=h160
            s161=dict(episodes=n,cycle_passed=n,cycle_failed=0,output_bound=0,output_unbound=n,serialization_ok=n,serialization_bad=0,
                output_status_counts={"REJECTED":n},output_reason_counts={"MALFORMED_EVIDENCE":n},cycle_false_check_counts={},
                boundary_counts={"POST_CYCLE_TERMINAL_REJECTION":n},single_post_cycle_rejection=True,localized_reason="MALFORMED_EVIDENCE",trace_files=48)
            p161=dict(experiment_id="C161-v5e-c160-failure-boundary-localization",stage="V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION",
                commit_sha=c.C161_COMMIT,status="PASS",diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
                C160_summary_sha256=h160,summary=s161,input_sha256=pins161)
            h161=save(d161/"summary.json",p161)
            before={str(p):c.sha(p) for p in root.rglob("*") if p.is_file()}
            settings=dict(EPISODES=n,ROWS=3,C160_SHA=h160,C161_SHA=h161,C154_SHA=h154,C151_SHA=rh,MANIFEST_SHA=mh,CORPUS_SHAS=corpus_hashes)
            def git(args,**kwargs):
                if args[-1].startswith("HEAD:"):return c.SOURCE_BLOBS[args[-1][5:]]+"\n"
                return c.C161_COMMIT+"\n"
            with patch.multiple(c,**settings),patch.object(c.subprocess,"check_output",side_effect=git),patch("builtins.print"):
                result=c.run(c161_summary=d161/"summary.json",c160_summary=d160/"summary.json",output_dir=root/"new")
            self.assertEqual(result["summary"]["episodes"],144)
            self.assertEqual(result["summary"]["pair_passed"],144)
            self.assertEqual(result["summary"]["pair_failed"],0)
            self.assertEqual(result["summary"]["guard_control_passed"],36)
            # Reduced synthetic coverage must never pass the real full-coverage gate.
            self.assertEqual(result["status"],"FAIL")
            self.assertTrue(result["diagnostic_execution_valid"])
            self.assertEqual(len(result["records"]),48)
            self.assertTrue((root/"new"/"summary.json").is_file())
            for path,h in before.items():self.assertEqual(c.sha(path),h)


if __name__ == "__main__":
    unittest.main()
