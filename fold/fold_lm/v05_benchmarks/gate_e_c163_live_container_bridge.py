"""C163: live C160 composition with an explicit tuple-to-list output adapter.

Historical C158/C159/C160/core source remains untouched. Only the diagnostic
terminal handoff changes; raw and adapted outputs share one freshly run cycle.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from types import MappingProxyType, SimpleNamespace

from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as old
from fold_lm.v05_benchmarks import gate_e_c162_evidence_container as diff
from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal

EXPERIMENT_ID = "C163-v5e-live-evidence-container-bridge"
STAGE = "V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE"
C162_SHA = "0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac"
C162_COMMIT = "32c6ceb4dd3748ea0d89a065f8ecd004cc20f117"
EPISODES = 82944
ARMS = old.ARMS
ORDERS = old.ORDERS
ROUTERS = old.ROUTER_SEEDS
# These are the same historical files as C162 plus its diagnosis and C161.
SOURCE_BLOBS = dict(diff.SOURCE_BLOBS, **{
    "fold/fold_lm/v05_benchmarks/gate_e_c161_failure_localization.py": "e3fa0a5881b3998bd1e43e3855636a5e6f6f04f6",
    "fold/fold_lm/v05_benchmarks/gate_e_c162_evidence_container.py": "df0d3fb805685628c6f7299c38995f3cdd382dd6",
})


def normalize_terminal(result):
    """Copy just the observations container. Never repair a value or reference.

    Non-tuple inputs are left unchanged for the original emitter to judge;
    malformed inputs are not silently turned into empty/valid evidence.
    """
    if type(result) is not dict:
        return result
    state = result.get("final_evidence")
    if type(state) is dict and type(state.get("observations")) is tuple:
        return {**result, "final_evidence": {**state,
                "observations": list(state["observations"])}}
    return result


def emit_live(binding, source_request_id, result):
    """Explicit diagnostic adapter, not an override of the historical emitter."""
    return terminal.emit_terminal(binding, source_request_id, normalize_terminal(result))


def live_fault_controls(binding, native):
    """Exercise the same six guards through the NEW native-input adapter."""
    controls = {}
    for name, reason in diff.FAULT_REASONS.items():
        r = deepcopy(native)
        rid = binding.request_id
        if name == "WRONG_REQUEST":
            rid += "|wrong"
        elif name == "WRONG_PROVENANCE":
            r["final_reference"]["provenance"]["source_id"] += "|wrong"
        elif name == "WRONG_PAYLOAD":
            r["final_value"] = 1 - r["final_value"]
        elif name == "UNGROUNDED":
            r["steps"][-1]["status"] = "REFERENCE_UNBOUND"
        elif name == "WRONG_CLOCK":
            r["final_evidence"]["revision"] += 1
        elif name == "DUPLICATE_REFERENCE":
            refs = r["final_evidence"]["observations"]
            r["final_evidence"]["observations"] = tuple(refs) + (deepcopy(r["final_reference"]),)
        before = old.blob(r)
        out = emit_live(binding, rid, r)
        no_payload = all(getattr(out, k) is None for k in
                         ("value", "record_key", "source_id", "evidence_time", "revision"))
        controls[name] = dict(output=asdict(out), passed=bool(
            out.status == "REJECTED" and out.reason == reason and no_payload
            and old.blob(r) == before))
    return controls


class AuditedEmitter:
    """Actual-output callback plus an unadapted negative control on each cycle.

    Control results never replace the adapted output and never feed the cycle.
    Full per-episode checks are retained by the caller. No semantic labels enter.
    """
    def __init__(self):
        self.counts = Counter()
        self.native_reasons = Counter()
        self.adapted_statuses = Counter()
        self.adapted_reasons = Counter()
        self.controls = []
        self.guarded = set()
        self.last = None

    def __call__(self, binding, request_id, result):
        original = old.blob(result)
        converted = normalize_terminal(result)
        checks = {
            "native_tuple": type(result.get("final_evidence", {}).get("observations")) is tuple,
            "adapted_list": type(converted.get("final_evidence", {}).get("observations")) is list,
            "content_unchanged": old.blob(converted) == original,
        }
        native = terminal.emit_terminal(binding, request_id, result)
        # This is the candidate's one output call; no fallback to the native control.
        out = terminal.emit_terminal(binding, request_id, converted)
        checks["native_rejected"] = (native.status, native.reason) == ("REJECTED", "MALFORMED_EVIDENCE")
        checks["input_preserved"] = (old.blob(result) == original and old.blob(converted) == original
            and type(result.get("final_evidence", {}).get("observations")) is tuple)
        self.counts.update(native_emitter_calls=1, adapted_emitter_calls=1)
        self.counts.update({k:int(v) for k,v in checks.items()})
        self.native_reasons[native.reason] += 1
        self.adapted_statuses[out.status] += 1
        self.adapted_reasons[out.reason] += 1
        self.last = dict(native_output=asdict(native), checks=checks)
        identity = (binding.source_id, binding.record_key)
        if identity not in self.guarded:
            self.guarded.add(identity)
            # A finite failed cycle can lack a bit/reference. Save a failed probe
            # set rather than converting that scientific failure into INVALID.
            ready = (type(result.get("final_value")) is int
                     and result["final_value"] in (0,1)
                     and isinstance(result.get("final_reference"), dict)
                     and isinstance(result["final_reference"].get("provenance"), dict)
                     and bool(result.get("steps")))
            if ready:
                probes = live_fault_controls(binding, result)
                self.counts["guard_emitter_calls"] += len(probes)
            else:
                probes = {name:dict(output=None, passed=False, reason="UNSUITABLE_LIVE_TERMINAL")
                          for name in diff.FAULT_REASONS}
            self.controls.append(dict(source_id=binding.source_id, key=binding.record_key,
                                      source_request_id=request_id, probes=probes))
            self.counts["guard_control_cases"] += len(probes)
            self.counts["guard_control_failed"] += sum(not p["passed"] for p in probes.values())
            self.counts["guard_control_passed"] += sum(p["passed"] for p in probes.values())
        return out

    def summary(self):
        return dict(self.counts, guard_record_bindings=len(self.guarded),
                    native_reason_counts=dict(self.native_reasons),
                    adapted_status_counts=dict(self.adapted_statuses),
                    adapted_reason_counts=dict(self.adapted_reasons))


def gate(summary):
    e = summary.get("emission", {})
    expected = dict(native_emitter_calls=EPISODES, adapted_emitter_calls=EPISODES,
        native_tuple=EPISODES, adapted_list=EPISODES, content_unchanged=EPISODES,
        native_rejected=EPISODES, input_preserved=EPISODES,
        guard_emitter_calls=768, guard_control_cases=768, guard_control_failed=0,
        guard_control_passed=768, guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":EPISODES},
        adapted_status_counts={"ANSWERED":EPISODES},
        adapted_reason_counts={"OBSERVED_VALUE":EPISODES})
    return bool(old.gate(summary) and all(e.get(k) == v for k,v in expected.items())
        and summary.get("answer_values") == {"0":34992,"1":47952}
        and summary.get("source_codes_preserved") is True)


def validate_c162(p):
    diff.require(p.get("experiment_id") == diff.EXPERIMENT_ID and p.get("stage") == diff.STAGE
        and p.get("commit_sha") == C162_COMMIT and p.get("status") == "PASS"
        and p.get("diagnostic_execution_valid") is True
        and p.get("production_runtime_modified") is False and p.get("gate_e_candidate") is False
        and p.get("C160_summary_sha256") == diff.C160_SHA
        and p.get("C161_summary_sha256") == diff.C161_SHA
        and diff.gate(p.get("summary", {})), "Expected accepted C162 PASS")
    diff.require(p.get("training_steps") == p.get("fresh_seed_count") == 0
        and all(p.get(k) is False for k in ("model_execution","retrieval_execution","live_cycle_execution"))
        and p.get("emitter_execution") is True, "C162 scope mismatch")
    diff.stream_index(p.get("records"))


def check_source_code():
    for path, wanted in SOURCE_BLOBS.items():
        actual = subprocess.check_output(["git","rev-parse","HEAD:"+path], text=True).strip()
        diff.require(actual == wanted, "Historical source changed: " + path)
    dirty = subprocess.check_output(["git","status","--porcelain","--untracked-files=no"], text=True)
    diff.require(not dirty.strip(), "Tracked tree is not clean")


def load_prerequisites(c162_summary, c160_summary, protected):
    """Validate source bytes, not rerun the C162 differential or reuse its answers."""
    c162_summary = diff.protect(c162_summary, C162_SHA, protected)
    c160_summary = diff.protect(c160_summary, diff.C160_SHA, protected)
    p162 = json.loads(c162_summary.read_text(encoding="utf-8")); validate_c162(p162)
    p160 = json.loads(c160_summary.read_text(encoding="utf-8"))
    from fold_lm.v05_benchmarks.gate_e_c161_failure_localization import validate_c160_report
    validate_c160_report(p160)
    for name, digest in p162["input_sha256"].items():
        diff.protect(name, digest, protected)
    for r in p162["records"]:
        path = diff.safe_child(c162_summary.parent, r["file"])
        diff.require(path.stat().st_size == r["serialized_bytes"], "C162 pair file size mismatch")
        diff.protect(path, r["sha256"], protected)
    for field in ("controls","plan"):
        r = p162[field]
        diff.protect(diff.safe_child(c162_summary.parent,r["file"]),r["sha256"],protected)
    c159 = diff.locate(p160["input_sha256"], old.C159_SHA, "summary.json")
    c151 = diff.locate(p160["input_sha256"], diff.C151_SHA, "summary.json")
    return c159, c151


def run(*, c162_summary, c160_summary, output_dir):
    import torch
    from fold_lm.v05 import state as core
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    from fold_lm.v05_benchmarks import gate_e_c151_cross_split as c151
    from fold_lm.v05_benchmarks import gate_e_c152_persisted_bridge as ranking
    from fold_lm.v05_benchmarks import gate_e_c153_evidence_admission as admission
    from fold_lm.v05_benchmarks import gate_e_c154_evidence_state_projection as projection
    from fold_lm.v05_benchmarks import gate_e_c155_payload_dereference as payload
    from fold_lm.v05_benchmarks import gate_e_c156_request_reobservation as observe
    from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter(); completed = []; extra = {}
    torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    try:
        check_source_code()
        execution_head = subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        c159_summary, c151_summary = load_prerequisites(c162_summary,c160_summary,extra)
        diff.protect(c159_summary,old.C159_SHA,extra)
        prior = json.loads(c159_summary.read_text(encoding="utf-8")); old.header(prior, terminal)
        source = old.ancestor(prior["input_sha256"],terminal.SOURCE_SHA)
        _, old_plan, old_rows, protected, check_files = terminal._load_source(source)
        for name,h in prior["input_sha256"].items():
            p=Path(name); old.require(p not in protected or protected[p]==h,"Conflicting source hashes"); protected[p]=h
        protected[c159_summary]=old.C159_SHA
        replay_outputs=old.validate_outputs(prior,old_rows,old_plan,c159_summary.parent,protected,terminal)
        p153=json.loads(old.ancestor(protected,payload.C153_SHA).read_text(encoding="utf-8"))
        for name,h in p153["input_sha256"].items():
            p=Path(name); old.require(p not in protected or protected[p]==h,"Conflicting C153 hashes"); protected[p]=h
        check_files()
        streams, metadata, _ = payload._load_inputs(old.ancestor(protected,payload.C154_SHA),
                                                    old.ancestor(protected,payload.C153_SHA),protected)
        states={}; bindings={}
        for record,state,_,_ in streams:
            order=record["order"]
            if order in states:
                old.require({r.evidence_id:r for r in states[order].observations} ==
                            {r.evidence_id:r for r in state.observations},"Snapshot state disagreement")
            states[order]=state
        for sid,md in metadata.items():
            b=payload.load_binding(md); bindings[sid]=replace(b,adapter=recovery.MeteredAdapter(b.adapter))
        registry=MappingProxyType(bindings)
        p157_path=old.ancestor(protected,recovery.C157_SHA)
        p157=json.loads(p157_path.read_text(encoding="utf-8")); recovery._header(p157)
        routers=[]
        for record in p157["records"]:
            model,path=recovery._load_router(p157_path.parent,record)
            protected[path]=record["checkpoint"]["sha256"]; routers.append(model)
        router_fingerprints=[recovery._fingerprint(m) for m in routers]
        root=c151_summary.parent
        fixture=Path(old.__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        protected.update({c151_summary:ranking.SOURCE_SHA, root/"evaluation-manifest.json":ranking.MANIFEST_SHA,
                          root/"split-plan.json":ranking.PLAN_SHA,fixture:ranking.QUERY_SHA})
        check_files()
        p151=json.loads(c151_summary.read_text(encoding="utf-8"))
        suite=json.loads((root/"evaluation-manifest.json").read_text(encoding="utf-8"))
        split=json.loads((root/"split-plan.json").read_text(encoding="utf-8"))
        rows=json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        old.require(suite==c143._build_suite(rows) and split==c151._build_plan(rows),"Manifest/generator mismatch")
        ranking._validate_source(p151,suite,split,c151,c146)
        vocabulary=c139._training_vocabulary(rows)
        old.require(len(vocabulary)==49 and c139._fixture_oov_count(rows,vocabulary)==0,"Vocabulary/OOV drift")
        old.require(torch.cuda.is_available(),"CUDA required for frozen ranker arithmetic")
        torch.cuda.set_device(0); device=torch.device("cuda")
        features=lambda texts:c139._collision_free_text_features(list(texts),vocabulary,device=device)
        snapshots={}
        for order,state in states.items():
            b=bindings[state.observations[0].provenance.source_id]; path=Path(b.source_path).parent/"catalog.json"
            old.require(path in protected,"Catalog is not pinned")
            snapshots[order]=ranking._load_snapshot(path,Path(b.source_path),lambda _:b.adapter)
        texts=[q["text"] for q in suite["queries"]]; descriptors=suite["descriptors"]
        labels=[q["expected_address"] for q in suite["queries"]]
        old.require(len({q["case_id"] for q in suite["queries"]})==old.QUERIES,"Unique query identities required")
        old_indices=[texts.index(r["validation"]) for r in rows]
        plan=dict(experiment_id=EXPERIMENT_ID,C160_summary_sha256=diff.C160_SHA,C162_summary_sha256=C162_SHA,
            queries=old.QUERIES,ranker_seeds=list(ranking.SEEDS),arms=ARMS,orders=ORDERS,routers=ROUTERS,
            router_assignment="manifest_query_index_modulo_3",scenario="COLD_RECOVER",episodes=EPISODES,
            query_manifest_sha256=ranking.MANIFEST_SHA,C151_summary_sha256=ranking.SOURCE_SHA,
            C159_summary_sha256=old.C159_SHA,source_blobs=SOURCE_BLOBS,
            ranker_checkpoints=[dict(seed=r["seed"],arm=a,sha256=r["arms"][a]["checkpoint"]["sha256"])
                                for r in p151["records"] for a in ARMS],
            router_checkpoints=[dict(seed=seed,sha256=r["checkpoint"]["sha256"])
                                for seed,r in zip(ROUTERS,p157["records"],strict=True)],
            changed_variable="live final_evidence.observations tuple -> list only",
            native_emitter_controls=EPISODES,guard_emitter_calls=768,training_steps=0,fresh_seeds=0)
        plan_path=output_dir/"live-container-plan.json"; plan_path.write_bytes(old.blob(plan))
        protected[plan_path]=old.sha(plan_path)
        def fetch(req,reg):
            b=reg[payload._source_id(asdict(req))]
            return admission._fetch(req,asdict(b.handles[req.key]),b.adapter)
        def entry_ref(entry):
            raw=asdict(entry); raw["request"]["operations"]=list(raw["request"]["operations"])
            return projection._ref_from_entry(raw)
        ops=SimpleNamespace(reobserve=observe.reobserve,control_inputs=observe.control_inputs,
            resolver=payload.resolve_reference,empty_inbox=admission.State,fetch=fetch,
            admit=admission.admit,entry_ref=entry_ref,project=projection.project_observation)
        emitter=AuditedEmitter()
        api=SimpleNamespace(Request=admission.Request,EvidenceRef=core.EvidenceRef,Provenance=core.Provenance,
            OBSERVED=core.ProvenanceKind.OBSERVED,ReadRequest=observe.ReadRequest,WorkingState=core.WorkingState,
            BudgetState=core.BudgetState,Permission=recovery.Permission,cycle=recovery.cycle,
            BoundRequest=terminal.BoundRequest,emit=emitter)
        groups={a:{o:Counter() for o in ORDERS} for a in ARMS}; totals=Counter(); router_counts=Counter(); values=Counter()
        minimum_margin=math.inf
        print("[C163] source lineage/C159 replay verified; live plan fixed; no training",flush=True)
        torch.cuda.reset_peak_memory_stats()
        for model_i,record in enumerate(p151["records"],1):
            for arm in ARMS:
                head,path=ranking._load_head(root,record,arm,vocabulary,SharedRetrievalContentHead,device)
                protected[path]=record["arms"][arm]["checkpoint"]["sha256"]
                fingerprint=ranking._fingerprint(head)
                encoded,_=c147._compose(head,texts+descriptors,features)
                with torch.inference_mode():
                    qv,dv=encoded[:old.QUERIES],encoded[old.QUERIES:]; replay=[]
                    for i in range(0,old.QUERIES,216):
                        replay.extend(c147._rank(qv[i:i+216]@dv.T,labels[i:i+216]))
                    original=c147._rank(qv[old_indices]@dv[:12].T,list(range(12)))
                ranking._check_replay(replay,record["arms"][arm]["results"])
                ranking._check_replay(original,record["arms"][arm]["original12"])
                totals.update(ranker_replay_cases=old.QUERIES,original12_replay_cases=12)
                for order in ORDERS:
                    snapshot=snapshots[order]; full_state=states[order]
                    binding=bindings[full_state.observations[0].provenance.source_id]
                    positions,scores,cost=old.select_live(head,texts,snapshot.catalog,features,c147._compose)
                    totals.update(ranking_queries=len(positions),candidate_scores=scores.numel())
                    old.require(all(snapshot.catalog[p]["descriptor"]==descriptors[r["predicted_address"]]
                        for p,r in zip(positions,replay,strict=True)),"Live catalog selection changed")
                    scope=f"C163|{record['seed']}|{arm}|{order}"
                    trace=output_dir/f"queries-{record['seed']}-{arm.lower()}-{order.lower()}.jsonl.gz"
                    with gzip.open(trace,"wt",encoding="utf-8",newline="\n") as f:
                        for j,(query,position) in enumerate(zip(suite["queries"],positions,strict=True)):
                            handle=snapshot.catalog[position]; ri=old.router_index(j)
                            result,out,ref,budget,mutated=old.execute_selected(scope,query["case_id"],handle,
                                routers[ri],full_state,binding,registry,api,ops,j%2)
                            # Evaluator-only labels/values, after both terminal emissions.
                            target=ranking._key(descriptors[query["expected_address"]])
                            judged=recovery._assess_episode(result,"COLD_RECOVER",ref,full_state,snapshot.values[handle["key"]],budget)
                            minimum_margin=min(minimum_margin,*judged["margins"])
                            outcheck=old.assess_output(out,scope+"|"+query["case_id"],scope,ref,
                                snapshot.values[handle["key"]],target,snapshot.values[target])
                            emission=emitter.last
                            passed=bool(judged["passed"] and outcheck["bound"] and outcheck["serialization_ok"]
                                and not mutated and all(emission["checks"].values()))
                            groups[arm][order].update(cases=1,binding_correct=int(outcheck["bound"]),semantic_correct=int(outcheck["semantic_correct"]))
                            totals.update(episodes=1,failed_episodes=int(not passed),controller_decisions=len(result["steps"]),
                                acquisitions=result["acquisitions"],publications=result["publications"],answered=int(out.status=="ANSWERED"),
                                output_mutations=int(mutated),serialization_failures=int(not outcheck["serialization_ok"]))
                            router_counts[str(ROUTERS[ri])]+=1
                            if outcheck["bound"]: values[str(out.value)]+=1
                            f.write(json.dumps(dict(case_id=query["case_id"],text=query["text"],router_seed=ROUTERS[ri],
                                selected_position=position,selected_key=handle["key"],output=asdict(out),emission=emission,
                                cycle=old.compact_cycle(result),cycle_assessment=judged,output_assessment=outcheck,passed=passed),
                                sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                            if (j+1)%216==0:
                                print(f"[C163] head {model_i}/12 arm={arm} order={order} queries={j+1}/1728 "
                                    f"failed={totals['failed_episodes']} remaining_queries={1727-j}",flush=True)
                    completed.append(dict(seed=record["seed"],split_id=record["split_id"],arm=arm,order=order,
                        file=trace.name,sha256=old.sha(trace),serialized_bytes=trace.stat().st_size,composition_cost=cost))
                totals["weight_mutations"]+=int(ranking._fingerprint(head)!=fingerprint)
                del head,encoded,qv,dv,scores
        totals["weight_mutations"]+=sum(recovery._fingerprint(m)!=h for m,h in zip(routers,router_fingerprints,strict=True))
        controls_path=output_dir/"live-guard-controls.json"; controls_path.write_bytes(old.blob(emitter.controls))
        check_files(); diff.check_inputs(extra); check_source_code()
        old.require(subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()==execution_head,"Execution HEAD changed")
        summary=dict(totals,retrieval_calls=sum(b.adapter.calls for b in bindings.values()),
            vectors_scored=sum(b.adapter.vectors for b in bindings.values()),router_episodes=dict(router_counts),
            arms={a:{o:dict(v) for o,v in d.items()} for a,d in groups.items()},c159_replay_calls=replay_outputs,
            minimum_controller_margin=minimum_margin,loaded_rankers=24,loaded_routers=3,fresh_seed_count=0,training_steps=0,
            live_query_selection=True,live_cycle_exercised=True,structured_result_exercised=True,answer_generation_exercised=False,
            production_state_commit=False,new_evidence_epoch=False,emission=emitter.summary(),answer_values=dict(values),source_codes_preserved=True,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),
            wall_clock_seconds=time.perf_counter()-started)
        passed=gate(summary); summary["live_container_bridge_gate_passed"]=passed
        all_inputs={}
        for mapping in (protected,extra):
            for path,digest in mapping.items():
                key=str(Path(path).resolve()); old.require(key not in all_inputs or all_inputs[key]==digest,"Input hash collision")
                all_inputs[key]=digest
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,commit_sha=execution_head,C162_summary_sha256=C162_SHA,
            C160_summary_sha256=diff.C160_SHA,C159_summary_sha256=old.C159_SHA,C151_summary_sha256=ranking.SOURCE_SHA,
            input_sha256=all_inputs,source_blobs=SOURCE_BLOBS,plan=dict(file=plan_path.name,sha256=old.sha(plan_path)),
            summary=summary,records=completed,controls=dict(file=controls_path.name,sha256=old.sha(controls_path)),
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,ranker_device=torch.cuda.get_device_name(0),
                controller_device="cpu",precision="float32/highest",threads=2),
            limitations=["Same inspected synthetic closed-set task; no new learning or task/language generalization",
                "Only authorized cold recovery; one manifest-assigned router per query; 63 other references remain",
                "Native control and adapted output share a fresh cycle; controls never feed the cycle",
                "C162 pair-file hashes verified, not independently recomputed in this benchmark",
                "C157 old large action replay not repeated; pinned weights and earlier accepted replay remain separate",
                "Typed output copies observed bits; relevance errors must remain; no learned answer generator",
                "Exact64 acquisition plus exact64 readback; diagnostic timings include controls, not production latency",
                "Diagnostic-only adapter; no production rollout, new epoch, durability or Gate E completion"])
        tmp=output_dir/"summary.partial.json"; tmp.write_bytes(old.blob(report)); tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(old.blob(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_streams=len(completed))))
        raise


def main():
    p=argparse.ArgumentParser(description="C163 live query/result with an explicit container adapter")
    for name in ("c162-summary","c160-summary","output-dir"):
        p.add_argument("--"+name,type=Path,required=True)
    print("C163 live episodes=82944; rankers=24 CUDA; routers=3 CPU; training/fresh_seeds=0",flush=True)
    print("C163 decisions=165888; acquisitions=82944; reads=165888; vectors=10616832",flush=True)
    print("C163 native controls=82944; adapted outputs=82944; guard calls=768; historical source unchanged",flush=True)
    report=run(**vars(p.parse_args())); print("=== C163 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
