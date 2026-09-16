"""C165: query-originating runtime permission denial with typed UNRESOLVED.

Diagnostic only. One fresh live ranking prefix feeds two independent cold cycles;
only the runtime Permission.allowed value differs. Historical code is untouched.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import gzip
import json
import math
from pathlib import Path
import subprocess
import time
from types import MappingProxyType, SimpleNamespace

from fold_lm.v05_benchmarks import gate_e_c164_live_missing_delivery as parent
from fold_lm.v05_benchmarks import gate_e_c163_live_container_bridge as live
from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as old
from fold_lm.v05_benchmarks import gate_e_c162_evidence_container as diff
from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal

EXPERIMENT_ID = "C165-v5e-live-query-permission-denied"
STAGE = "V5-E-LIVE-QUERY-PERMISSION-DENIED"
C164_SHA = "42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2"
C164_COMMIT = "c3ee72d7ad7b7112fb45c6601899b69a96cf4969"
PREFIXES = 82944
EPISODES = 2 * PREFIXES
CONDITIONS = ("COLD_RECOVER", "COLD_PERMISSION_DENIED")
ARMS, ORDERS, ROUTERS = old.ARMS, old.ORDERS, old.ROUTER_SEEDS
SOURCE_BLOBS = {**parent.SOURCE_BLOBS,
    "fold/fold_lm/v05_benchmarks/gate_e_c164_live_missing_delivery.py":
        "a2bbb68291590f71e6fc190c0158c295b568a8f4"}


def api_with_permission(api, allowed: bool):
    """Override only runtime permission while forwarding every other cycle input."""
    if type(allowed) is not bool:
        raise TypeError("Permission condition must be Boolean")
    def cycle(model, request, admission_request, state, working, budget,
              registry, permission, ops, deliver):
        if not isinstance(permission, api.Permission) or permission.allowed is not True:
            raise ValueError("Expected unchanged base permission before registered override")
        return api.cycle(model, request, admission_request, state, working, budget,
                         registry, api.Permission(allowed), ops, deliver)
    return SimpleNamespace(**{**vars(api), "cycle": cycle})


def assess_terminal(output, binding, reference, selected_value, target_key,
                    target_value, condition):
    """Post-emission evaluation only; denied UNRESOLVED has no semantic score."""
    if condition not in CONDITIONS:
        raise ValueError("Unregistered evaluation condition")
    serial = json.loads(old.blob(asdict(output))) == asdict(output)
    if condition == CONDITIONS[0]:
        scored = old.assess_output(output, binding.request_id, binding.scope_id,
                                   reference, selected_value, target_key, target_value)
        return dict(terminal_correct=scored["bound"], answer_bound=scored["bound"],
                    unresolved_without_payload=False, semantic_correct=scored["semantic_correct"],
                    serialization_ok=serial and scored["serialization_ok"])
    wanted = terminal.TerminalResult(terminal.SCHEMA, binding.request_id, binding.scope_id,
                                     "UNRESOLVED", "PERMISSION_DENIED")
    no_payload = all(getattr(output, k) is None for k in
                    ("value", "record_key", "source_id", "evidence_time", "revision"))
    correct = asdict(output) == asdict(wanted) and no_payload
    return dict(terminal_correct=correct, answer_bound=False,
                unresolved_without_payload=correct, semantic_correct=None,
                serialization_ok=serial)


def gate(s):
    n = PREFIXES
    required = dict(episodes=2*n, failed_episodes=0, ranking_queries=n,
        candidate_scores=64*n, ranker_replay_cases=41472, original12_replay_cases=288,
        c159_replay_calls=6528, controller_decisions=4*n, acquisitions=n,
        publications=n, retrieval_calls=2*n, vectors_scored=128*n,
        metered_adapter_calls=2*n, metered_vectors_scored=128*n,
        answered=n, unresolved=n, output_mutations=0, serialization_failures=0,
        weight_mutations=0, source_codes_preserved=True,
        router_episodes={str(r):2*n//3 for r in ROUTERS},
        raw_action_counts={"2":2*n,"0":n,"5":n},
        answer_values={"0":34992,"1":47952})
    if not all(s.get(k) == v for k,v in required.items()):
        return False
    by = s.get("conditions", {})
    specs = {
        CONDITIONS[0]: dict(acquisitions=n, publications=n, retrieval_calls=2*n,
            vectors_scored=128*n, answered=n, unresolved=0,
            unresolved_without_payload=0),
        CONDITIONS[1]: dict(acquisitions=0, publications=0, retrieval_calls=0,
            vectors_scored=0, answered=0, unresolved=n,
            unresolved_without_payload=n, permission_denied_authority=n,
            acquisition_budget_preserved=n, no_unpermitted_fetch=n),
    }
    for condition in CONDITIONS:
        g = by.get(condition, {})
        common = dict(episodes=n, failed_episodes=0, controller_decisions=2*n,
                      terminal_correct=n)
        if not all(g.get(k) == v for k,v in {**common, **specs[condition]}.items()):
            return False
        margin = g.get("minimum_controller_margin", math.nan)
        if type(margin) not in (float,int) or not math.isfinite(margin) or margin <= 0:
            return False
        if g.get("router_episodes") != {str(r):n//3 for r in ROUTERS}:
            return False
        answered = condition == CONDITIONS[0]
        for a in ARMS:
            for o in ORDERS:
                wanted = dict(cases=20736, terminal_correct=20736,
                    answer_bound=20736 if answered else 0,
                    unresolved_without_payload=0 if answered else 20736,
                    semantic_correct=(20727 if a==ARMS[0] else 20736) if answered else None)
                if g.get("arms",{}).get(a,{}).get(o) != wanted:
                    return False
    success = {**s, **by[CONDITIONS[0]], "router_episodes":{str(r):n//3 for r in ROUTERS},
        "arms":{a:{o:dict(cases=20736,binding_correct=20736,
                    semantic_correct=by[CONDITIONS[0]]["arms"][a][o]["semantic_correct"])
                   for o in ORDERS} for a in ARMS}}
    if not old.gate(success):
        return False
    e = s.get("emission",{})
    wanted = dict(native_emitter_calls=2*n, adapted_emitter_calls=2*n,
        native_tuple=2*n, adapted_list=2*n, content_unchanged=2*n,
        native_rejected=2*n, input_preserved=2*n,
        guard_emitter_calls=768, guard_control_cases=768, guard_control_passed=768,
        guard_control_failed=0, guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":2*n},
        adapted_status_counts={"ANSWERED":n,"UNRESOLVED":n},
        adapted_reason_counts={"OBSERVED_VALUE":n,"PERMISSION_DENIED":n})
    return all(e.get(k) == v for k,v in wanted.items())


def validate_parent(p):
    old.require(p.get("experiment_id")==parent.EXPERIMENT_ID and p.get("stage")==parent.STAGE
        and p.get("commit_sha")==C164_COMMIT and p.get("status")=="PASS"
        and p.get("diagnostic_execution_valid") is True
        and p.get("production_runtime_modified") is False and p.get("gate_e_candidate") is False
        and p.get("C163_summary_sha256")==parent.C163_SHA
        and parent.gate(p.get("summary",{})), "Expected accepted C164 PASS")
    s=p["summary"]
    old.require(s.get("training_steps")==s.get("fresh_seed_count")==0
        and all(s.get(k) is True for k in ("live_query_selection","live_cycle_exercised","structured_result_exercised"))
        and all(s.get(k) is False for k in ("answer_generation_exercised","production_state_commit","new_evidence_epoch")),
        "C164 scope mismatch")
    diff.stream_index(p.get("records"))


def check_source_code():
    parent.check_source_code()
    for path,wanted in SOURCE_BLOBS.items():
        got=subprocess.check_output(["git","rev-parse","HEAD:"+path],text=True).strip()
        old.require(got==wanted,"Historical source changed: "+path)


def load_parent(path, protected):
    path=diff.protect(path,C164_SHA,protected)
    p=json.loads(path.read_text(encoding="utf-8")); validate_parent(p)
    for name,h in p["input_sha256"].items(): diff.protect(name,h,protected)
    for record in p["records"]:
        trace=diff.safe_child(path.parent,record["file"])
        old.require(trace.stat().st_size==record["serialized_bytes"],"C164 trace size mismatch")
        diff.protect(trace,record["sha256"],protected)
    for field in ("plan","controls"):
        r=p[field]; diff.protect(diff.safe_child(path.parent,r["file"]),r["sha256"],protected)
    c163=diff.locate(p["input_sha256"],parent.C163_SHA,"summary.json")
    return parent.load_parent(c163,protected)


def run(*, c164_summary, output_dir):
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
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter(); completed=[]; extra={}
    torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    try:
        check_source_code()
        head_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        c159_summary,c151_summary=load_parent(c164_summary,extra)
        diff.protect(c159_summary,old.C159_SHA,extra)
        prior=json.loads(c159_summary.read_text(encoding="utf-8")); old.header(prior,terminal)
        source=old.ancestor(prior["input_sha256"],terminal.SOURCE_SHA)
        _,old_plan,old_rows,protected,check_files=terminal._load_source(source)
        for name,h in prior["input_sha256"].items():
            p=Path(name); old.require(p not in protected or protected[p]==h,"Conflicting source hashes"); protected[p]=h
        protected[c159_summary]=old.C159_SHA
        replay_outputs=old.validate_outputs(prior,old_rows,old_plan,c159_summary.parent,protected,terminal)
        p153=json.loads(old.ancestor(protected,payload.C153_SHA).read_text(encoding="utf-8"))
        for name,h in p153["input_sha256"].items():
            p=Path(name); old.require(p not in protected or protected[p]==h,"Conflicting C153 hashes"); protected[p]=h
        check_files()
        streams,metadata,_=payload._load_inputs(old.ancestor(protected,payload.C154_SHA),
                                              old.ancestor(protected,payload.C153_SHA),protected)
        states={}; bindings={}
        for record,state,_,_ in streams:
            order=record["order"]
            if order in states:
                old.require({r.evidence_id:r for r in states[order].observations}==
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
        fixture=Path(old.__file__).parent/"fixtures/c138_compositional_alias_queries.json"
        protected.update({c151_summary:ranking.SOURCE_SHA,root/"evaluation-manifest.json":ranking.MANIFEST_SHA,
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
        old.require(len({q["case_id"] for q in suite["queries"]})==old.QUERIES,"Unique queries required")
        old_indices=[texts.index(r["validation"]) for r in rows]
        plan=dict(experiment_id=EXPERIMENT_ID,C164_summary_sha256=C164_SHA,
            conditions=CONDITIONS,queries=old.QUERIES,ranking_prefixes=PREFIXES,episodes=EPISODES,
            ranker_seeds=list(ranking.SEEDS),arms=ARMS,orders=ORDERS,routers=ROUTERS,
            router_assignment="manifest_query_index_modulo_3",query_manifest_sha256=ranking.MANIFEST_SHA,
            prefix_sharing="one fresh ranking; two independent cold continuations; no result reuse",
            C151_summary_sha256=ranking.SOURCE_SHA,C159_summary_sha256=old.C159_SHA,source_blobs=SOURCE_BLOBS,
            ranker_checkpoints=[dict(seed=r["seed"],arm=a,sha256=r["arms"][a]["checkpoint"]["sha256"])
                                for r in p151["records"] for a in ARMS],
            router_checkpoints=[dict(seed=seed,sha256=r["checkpoint"]["sha256"])
                                for seed,r in zip(ROUTERS,p157["records"],strict=True)],
            changed_variable="runtime Permission.allowed true versus false only",
            training_steps=0,fresh_seeds=0,initial_budget=[3,1],delivery="identity",
            decisions=4*PREFIXES,acquisitions=PREFIXES,publications=PREFIXES,
            adapter_calls=2*PREFIXES,vectors_scanned=128*PREFIXES,
            native_emitter_calls=EPISODES,adapted_emitter_calls=EPISODES,guard_calls=768)
        plan_path=output_dir/"permission-plan.json"; plan_path.write_bytes(old.blob(plan)); protected[plan_path]=old.sha(plan_path)
        def fetch(req,reg):
            b=reg[payload._source_id(asdict(req))]
            return admission._fetch(req,asdict(b.handles[req.key]),b.adapter)
        def entry_ref(entry):
            raw=asdict(entry); raw["request"]["operations"]=list(raw["request"]["operations"])
            return projection._ref_from_entry(raw)
        ops=SimpleNamespace(reobserve=observe.reobserve,control_inputs=observe.control_inputs,
            resolver=payload.resolve_reference,empty_inbox=admission.State,fetch=fetch,
            admit=admission.admit,entry_ref=entry_ref,project=projection.project_observation)
        emitter=live.AuditedEmitter()
        api=SimpleNamespace(Request=admission.Request,EvidenceRef=core.EvidenceRef,Provenance=core.Provenance,
            OBSERVED=core.ProvenanceKind.OBSERVED,ReadRequest=observe.ReadRequest,WorkingState=core.WorkingState,
            BudgetState=core.BudgetState,Permission=recovery.Permission,cycle=recovery.cycle,
            BoundRequest=terminal.BoundRequest,emit=emitter)
        apis={CONDITIONS[0]:api_with_permission(api,True),
              CONDITIONS[1]:api_with_permission(api,False)}
        totals=Counter(); by={c:Counter() for c in CONDITIONS}; values=Counter(); actions=Counter()
        router_counts=Counter(); by_router={c:Counter() for c in CONDITIONS}
        groups={c:{a:{o:Counter() for o in ORDERS} for a in ARMS} for c in CONDITIONS}
        margins={c:math.inf for c in CONDITIONS}
        print("[C165] lineage/replay verified; permission-only plan fixed; training=0",flush=True)
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
                        for p,r in zip(positions,replay,strict=True)),"Live selection changed")
                    trace=output_dir/f"queries-{record['seed']}-{arm.lower()}-{order.lower()}.jsonl.gz"
                    with gzip.open(trace,"wt",encoding="utf-8",newline="\n") as f:
                        for j,(query,position) in enumerate(zip(suite["queries"],positions,strict=True)):
                            handle=snapshot.catalog[position]; ri=old.router_index(j)
                            for condition in CONDITIONS:
                                scope=f"C165|{record['seed']}|{arm}|{order}|{condition}"
                                result,out,ref,budget,mutated=old.execute_selected(scope,query["case_id"],handle,
                                    routers[ri],full_state,binding,registry,apis[condition],ops,j%2)
                                bound=terminal.BoundRequest(scope+"|"+query["case_id"],scope,ref.evidence_id,
                                    ref.provenance.source_id,ref.provenance.evidence_time,ref.provenance.revision)
                                target=ranking._key(descriptors[query["expected_address"]])
                                judged=recovery._assess_episode(result,condition,ref,full_state,
                                                                snapshot.values[handle["key"]],budget)
                                margins[condition]=min(margins[condition],*judged["margins"])
                                outcheck=assess_terminal(out,bound,ref,snapshot.values[handle["key"]],
                                                        target,snapshot.values[target],condition)
                                emission=emitter.last
                                passed=bool(judged["passed"] and outcheck["terminal_correct"]
                                    and outcheck["serialization_ok"] and not mutated and all(emission["checks"].values()))
                                counts=dict(episodes=1,failed_episodes=int(not passed),controller_decisions=len(result["steps"]),
                                    acquisitions=result["acquisitions"],publications=result["publications"],
                                    retrieval_calls=result["retrieval_calls"],vectors_scored=result["vectors_scored"],
                                    answered=int(out.status=="ANSWERED"),unresolved=int(out.status=="UNRESOLVED"))
                                totals.update(counts); by[condition].update(counts)
                                by[condition].update(terminal_correct=int(outcheck["terminal_correct"]),
                                    unresolved_without_payload=int(outcheck["unresolved_without_payload"]))
                                if condition==CONDITIONS[1]:
                                    first=result["steps"][0]
                                    by[condition].update(
                                        permission_denied_authority=int(first.get("authority")=="PERMISSION_DENIED"),
                                        acquisition_budget_preserved=int(result["final_budget"]["acquisitions_remaining"]==budget.acquisitions_remaining),
                                        no_unpermitted_fetch=int(result["retrieval_calls"]==0 and first.get("fetched") is None))
                                totals.update(output_mutations=int(mutated),serialization_failures=int(not outcheck["serialization_ok"]))
                                router_counts[str(ROUTERS[ri])]+=1; by_router[condition][str(ROUTERS[ri])]+=1
                                actions.update(str(s["action"]) for s in result["steps"])
                                g=groups[condition][arm][order]
                                g.update(cases=1,terminal_correct=int(outcheck["terminal_correct"]),
                                    answer_bound=int(outcheck["answer_bound"]),unresolved_without_payload=int(outcheck["unresolved_without_payload"]))
                                if condition==CONDITIONS[0]:
                                    g.update(semantic_correct=int(outcheck["semantic_correct"]))
                                    if outcheck["answer_bound"]: values[str(out.value)]+=1
                                f.write(json.dumps(dict(case_id=query["case_id"],text=query["text"],condition=condition,
                                    router_seed=ROUTERS[ri],selected_position=position,selected_key=handle["key"],
                                    output=asdict(out),emission=emission,cycle=old.compact_cycle(result),
                                    cycle_assessment=judged,output_assessment=outcheck,passed=passed),
                                    sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                            if (j+1)%216==0:
                                print(f"[C165] head {model_i}/12 arm={arm} order={order} queries={j+1}/1728 "
                                    f"branch_episodes={totals['episodes']} failed={totals['failed_episodes']} remaining_queries={1727-j}",flush=True)
                    completed.append(dict(seed=record["seed"],split_id=record["split_id"],arm=arm,order=order,
                        file=trace.name,rows=2*old.QUERIES,sha256=old.sha(trace),serialized_bytes=trace.stat().st_size,composition_cost=cost))
                totals["weight_mutations"]+=int(ranking._fingerprint(head)!=fingerprint)
                del head,encoded,qv,dv,scores
        totals["weight_mutations"]+=sum(recovery._fingerprint(m)!=h for m,h in zip(routers,router_fingerprints,strict=True))
        controls_path=output_dir/"live-guard-controls.json"; controls_path.write_bytes(old.blob(emitter.controls))
        check_files(); diff.check_inputs(extra); check_source_code()
        old.require(subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()==head_sha,"HEAD changed")
        condition_summaries={}
        for c in CONDITIONS:
            arm_groups={a:{o:dict(g) for o,g in d.items()} for a,d in groups[c].items()}
            if c==CONDITIONS[1]:
                for d in arm_groups.values():
                    for g in d.values(): g["semantic_correct"]=None
            condition_summaries[c]=dict(by[c],minimum_controller_margin=margins[c],
                                        router_episodes=dict(by_router[c]),arms=arm_groups)
        summary=dict(totals,conditions=condition_summaries,router_episodes=dict(router_counts),
            raw_action_counts=dict(actions),answer_values=dict(values),emission=emitter.summary(),
            c159_replay_calls=replay_outputs,source_codes_preserved=True,
            metered_adapter_calls=sum(b.adapter.calls for b in bindings.values()),
            metered_vectors_scored=sum(b.adapter.vectors for b in bindings.values()),
            loaded_rankers=24,loaded_routers=3,training_steps=0,fresh_seed_count=0,
            live_query_selection=True,live_cycle_exercised=True,structured_result_exercised=True,
            permission_gate_exercised=True,answer_generation_exercised=False,
            production_state_commit=False,new_evidence_epoch=False,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),wall_clock_seconds=time.perf_counter()-started)
        passed=gate(summary); summary["permission_denied_gate_passed"]=passed
        all_inputs={}
        for mapping in (protected,extra):
            for path,h in mapping.items():
                k=str(Path(path).resolve()); old.require(k not in all_inputs or all_inputs[k]==h,"Conflicting inputs"); all_inputs[k]=h
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,commit_sha=head_sha,
            C164_summary_sha256=C164_SHA,input_sha256=all_inputs,source_blobs=SOURCE_BLOBS,
            plan=dict(file=plan_path.name,sha256=old.sha(plan_path)),summary=summary,records=completed,
            controls=dict(file=controls_path.name,sha256=old.sha(controls_path)),
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,ranker_device=torch.cuda.get_device_name(0),
                controller_device="cpu",precision="float32/highest",threads=2),
            limitations=["82944 fresh ranking prefixes, each forked into allowed and permission-denied cold cycles",
                "Permission denial is runtime authority only; it is not target absence, retrieval miss, transport loss or semantic abstention",
                "Denied branch must pay zero adapter search/readback cost and preserve acquisition budget",
                "Same synthetic task, checkpoints, clocks and 63 other references; no learning or new task generalization",
                "UNRESOLVED has no payload or semantic accuracy; it does not prove nonexistence",
                "Existing C163 output adapter/C159 emitter and C158 Controller cycle remain unchanged; no production rollout",
                "Diagnostic timing/allocator peaks include validation, replay, controls and serialization; Gate E NOT PASSED"])
        tmp=output_dir/"summary.partial.json"; tmp.write_bytes(old.blob(report)); tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(old.blob(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_streams=len(completed))))
        raise


def main():
    parser=argparse.ArgumentParser(description="C165 runtime-permission query-to-UNRESOLVED diagnostic")
    parser.add_argument("--c164-summary",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    print("C165 rankings=82944; allowed+permission-denied cold continuations; live episodes=165888",flush=True)
    print("C165 decisions=331776; acquisitions=82944; restorations=82944; reads=165888; vectors=10616832",flush=True)
    print("C165 changed variable=Permission.allowed only; training/fresh_seeds=0; Gate E NOT PASSED",flush=True)
    report=run(**vars(parser.parse_args()))
    print("=== C165 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
