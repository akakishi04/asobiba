"""C167: initially bound reference versus cold recovery in the live query path.

Diagnostic only. The selected reference's initial membership is the only change.
A warm read still pays one exact64 dereference; it is not a zero-IO answer cache.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from types import MappingProxyType, SimpleNamespace

from fold_lm.v05_benchmarks import gate_e_c166_live_budget_exhausted as parent
from fold_lm.v05_benchmarks import gate_e_c163_live_container_bridge as live
from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as old
from fold_lm.v05_benchmarks import gate_e_c162_evidence_container as diff
from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal

EXPERIMENT_ID = "C167-v5e-live-query-warm-reference"
STAGE = "V5-E-LIVE-QUERY-WARM-REFERENCE"
C166_SHA = "77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2"
C166_COMMIT = "dc1f315cac66d1963f8e0d08bb897457affbe94a"
PREFIXES = 82944
EPISODES = 2 * PREFIXES
CONDITIONS = ("COLD_RECOVER", "WARM_PRESENT")
ARMS, ORDERS, ROUTERS = old.ARMS, old.ORDERS, old.ROUTER_SEEDS
SOURCE_BLOBS = {**parent.SOURCE_BLOBS,
    "fold/fold_lm/v05_benchmarks/gate_e_c166_live_budget_exhausted.py":
        "8954953256124e90c93945b521dc2f801f425e4b"}


def state_digest(state):
    return hashlib.sha256(old.blob(asdict(state))).hexdigest()


def api_with_reference_presence(api, full_state, present: bool):
    """Substitute only initial selected-reference membership at the cycle boundary.

    C160 still constructs its original cold state. Verify that exact input, then
    pass either it or a fresh immutable copy of the full fixture to C158. No
    payload, expected answer, semantic target or action override enters cycle.
    """
    if type(present) is not bool:
        raise TypeError("Reference-presence condition must be Boolean")
    def cycle(model, request, admission_request, state, working, budget,
              registry, permission, ops, deliver):
        ref = request.reference
        if sum(r == ref for r in full_state.observations) != 1:
            raise ValueError("Selected reference missing or ambiguous in source fixture")
        cold = replace(full_state, observations=tuple(
            r for r in full_state.observations if r.evidence_id != ref.evidence_id))
        if type(state) is not type(full_state) or state != cold:
            raise ValueError("Expected unchanged C160 cold input state")
        effective = replace(full_state) if present else state
        metadata = dict(initial_evidence_sha256=state_digest(effective),
            initial_reference_count=len(effective.observations),
            initial_selected_reference_present=ref in effective.observations)
        result = api.cycle(model, request, admission_request, effective, working,
                           budget, registry, permission, ops, deliver)
        return {**result, **metadata}
    return SimpleNamespace(**{**vars(api), "cycle": cycle})


def presence_audit(result, reference, full_state, initial_budget, present):
    """Post-execution checks. Never fills evidence or rewrites model decisions."""
    if type(present) is not bool:
        raise TypeError("Boolean evaluation condition required")
    expected = full_state if present else replace(full_state, observations=tuple(
        r for r in full_state.observations if r.evidence_id != reference.evidence_id))
    checks = dict(initial_state_verified=(
        result.get("initial_evidence_sha256") == state_digest(expected)
        and result.get("initial_reference_count") == len(expected.observations)
        and result.get("initial_selected_reference_present") is present),
        initial_budget_verified=asdict(initial_budget) == dict(
            internal_steps_remaining=3, acquisitions_remaining=1))
    if present:
        steps = result.get("steps", [])
        checks.update(
            warm_no_reacquisition=(result["acquisitions"] == result["publications"]
                == result["inbox_entries"] == 0 and bool(steps)
                and all(s.get(k) is None for s in steps for k in
                        ("authority", "fetched", "admission", "projection"))),
            warm_budget_preserved=(result["final_budget"] == dict(
                internal_steps_remaining=2, acquisitions_remaining=1)
                and result["final_internal_step"] == 8),
            warm_one_answer=([s["action"] for s in steps] == [0]
                and result["terminal"] == "ANSWER_ACTION"),
            warm_state_unchanged=(hashlib.sha256(old.blob(result["final_evidence"])).hexdigest()
                                   == state_digest(full_state)))
    return checks


def same_observed_output(left, right):
    """Request scopes differ; observed identity, value and status must agree."""
    fields = ("schema_version", "status", "reason", "value", "record_key",
              "source_id", "evidence_time", "revision")
    return bool(left.request_id != right.request_id and left.scope_id != right.scope_id
                and all(getattr(left, k) == getattr(right, k) for k in fields))


def gate(s):
    n = PREFIXES
    expected = dict(episodes=2*n, failed_episodes=0, ranking_queries=n,
        candidate_scores=64*n, ranker_replay_cases=41472, original12_replay_cases=288,
        c159_replay_calls=6528, controller_decisions=3*n, acquisitions=n, publications=n,
        retrieval_calls=3*n, vectors_scored=192*n, metered_adapter_calls=3*n,
        metered_vectors_scored=192*n, answered=2*n, unresolved=0,
        output_mutations=0, serialization_failures=0, weight_mutations=0,
        source_codes_preserved=True, matched_output_pairs=n,
        router_episodes={str(r):2*n//3 for r in ROUTERS},
        raw_action_counts={"2":n,"0":2*n}, answer_values={"0":69984,"1":95904})
    if not all(s.get(k) == v for k,v in expected.items()):
        return False
    by = s.get("conditions", {})
    if set(by) != set(CONDITIONS):
        return False
    for condition in CONDITIONS:
        warm = condition == CONDITIONS[1]
        g = by[condition]
        wanted = dict(episodes=n, failed_episodes=0, controller_decisions=(1 if warm else 2)*n,
            acquisitions=0 if warm else n, publications=0 if warm else n,
            retrieval_calls=(1 if warm else 2)*n, vectors_scored=(64 if warm else 128)*n,
            answered=n, unresolved=0, terminal_correct=n, initial_state_verified=n,
            initial_budget_verified=n, answer_values={"0":34992,"1":47952},
            router_episodes={str(r):n//3 for r in ROUTERS})
        if warm:
            wanted.update(warm_no_reacquisition=n, warm_budget_preserved=n,
                          warm_one_answer=n, warm_state_unchanged=n)
        if not all(g.get(k) == v for k,v in wanted.items()):
            return False
        margin = g.get("minimum_controller_margin", math.nan)
        if type(margin) not in (int,float) or not math.isfinite(margin) or margin <= 0:
            return False
        for arm in ARMS:
            for order in ORDERS:
                if g.get("arms",{}).get(arm,{}).get(order) != dict(cases=20736,
                    binding_correct=20736, semantic_correct=20727 if arm == ARMS[0] else 20736):
                    return False
    # Preserve the entire historical successful cold gate, not just its accuracy.
    if not old.gate({**s, **by[CONDITIONS[0]]}):
        return False
    e = s.get("emission", {})
    expected = dict(native_emitter_calls=2*n, adapted_emitter_calls=2*n, native_tuple=2*n,
        adapted_list=2*n, content_unchanged=2*n, native_rejected=2*n, input_preserved=2*n,
        guard_emitter_calls=768, guard_control_cases=768, guard_control_passed=768,
        guard_control_failed=0, guard_record_bindings=128,
        native_reason_counts={"MALFORMED_EVIDENCE":2*n},
        adapted_status_counts={"ANSWERED":2*n}, adapted_reason_counts={"OBSERVED_VALUE":2*n})
    return all(e.get(k) == v for k,v in expected.items())


def validate_parent(p):
    old.require(p.get("experiment_id") == parent.EXPERIMENT_ID and p.get("stage") == parent.STAGE
        and p.get("commit_sha") == C166_COMMIT and p.get("status") == "PASS"
        and p.get("diagnostic_execution_valid") is True
        and p.get("production_runtime_modified") is False and p.get("gate_e_candidate") is False
        and p.get("C165_summary_sha256") == parent.C165_SHA
        and parent.gate(p.get("summary",{})), "Expected accepted C166 PASS")
    s = p["summary"]
    old.require(s.get("training_steps") == s.get("fresh_seed_count") == 0
        and s.get("budget_exhausted_gate_passed") is True
        and all(s.get(k) is True for k in ("live_query_selection","live_cycle_exercised",
            "structured_result_exercised","acquisition_budget_gate_exercised"))
        and all(s.get(k) is False for k in ("answer_generation_exercised",
            "production_state_commit","new_evidence_epoch")), "C166 scope mismatch")
    diff.stream_index(p.get("records"))
    old.require(all(r.get("rows") == 3456 for r in p["records"]), "C166 trace declarations changed")


def check_source_code():
    parent.check_source_code()
    for path,wanted in SOURCE_BLOBS.items():
        got = subprocess.check_output(["git","rev-parse","HEAD:"+path],text=True).strip()
        old.require(got == wanted, "Historical source changed: " + path)


def load_parent(path, protected):
    path = diff.protect(path,C166_SHA,protected)
    p = json.loads(path.read_text(encoding="utf-8")); validate_parent(p)
    for name,h in p["input_sha256"].items():
        diff.protect(name,h,protected)
    for record in p["records"]:
        trace = diff.safe_child(path.parent,record["file"])
        old.require(trace.stat().st_size == record["serialized_bytes"], "C166 trace size mismatch")
        diff.protect(trace,record["sha256"],protected)
    for field in ("plan","controls"):
        r=p[field]; diff.protect(diff.safe_child(path.parent,r["file"]),r["sha256"],protected)
    return parent.load_parent(diff.locate(p["input_sha256"],parent.C165_SHA,"summary.json"),protected)


def run(*, c166_summary, output_dir):
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
    output_dir = Path(output_dir); output_dir.mkdir(parents=True,exist_ok=False)
    started = time.perf_counter(); completed = []; extra = {}
    torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    try:
        check_source_code()
        head_sha = subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        c159_summary,c151_summary = load_parent(c166_summary,extra)
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
        plan=dict(experiment_id=EXPERIMENT_ID,C166_summary_sha256=C166_SHA,
            conditions=CONDITIONS,queries=old.QUERIES,ranking_prefixes=PREFIXES,episodes=EPISODES,
            ranker_seeds=list(ranking.SEEDS),arms=ARMS,orders=ORDERS,routers=ROUTERS,
            router_assignment="manifest_query_index_modulo_3",query_manifest_sha256=ranking.MANIFEST_SHA,
            prefix_sharing="one fresh ranking; independent cold then warm states; no result reuse",
            C151_summary_sha256=ranking.SOURCE_SHA,C159_summary_sha256=old.C159_SHA,source_blobs=SOURCE_BLOBS,
            ranker_checkpoints=[dict(seed=r["seed"],arm=a,sha256=r["arms"][a]["checkpoint"]["sha256"])
                                for r in p151["records"] for a in ARMS],
            router_checkpoints=[dict(seed=seed,sha256=r["checkpoint"]["sha256"])
                                for seed,r in zip(ROUTERS,p157["records"],strict=True)],
            changed_variable="initial selected-reference membership only; cold63 versus warm64 references",
            training_steps=0,fresh_seeds=0,permission=True,initial_budget=[3,1],delivery="identity",
            stale_bit="manifest_query_index_modulo_2",decisions=3*PREFIXES,acquisitions=PREFIXES,
            publications=PREFIXES,adapter_calls=3*PREFIXES,vectors_scanned=192*PREFIXES,
            native_emitter_calls=EPISODES,adapted_emitter_calls=EPISODES,guard_calls=768)
        plan_path=output_dir/"reference-presence-plan.json"; plan_path.write_bytes(old.blob(plan)); protected[plan_path]=old.sha(plan_path)
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
        totals=Counter(); by={c:Counter() for c in CONDITIONS}; values=Counter(); actions=Counter()
        by_values={c:Counter() for c in CONDITIONS}; router_counts=Counter()
        by_router={c:Counter() for c in CONDITIONS}
        groups={c:{a:{o:Counter() for o in ORDERS} for a in ARMS} for c in CONDITIONS}
        margins={c:math.inf for c in CONDITIONS}
        print("[C167] lineage/replay verified; initial-reference-only plan fixed; training=0",flush=True)
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
                    apis={c:api_with_reference_presence(api,full_state,c==CONDITIONS[1]) for c in CONDITIONS}
                    positions,scores,cost=old.select_live(head,texts,snapshot.catalog,features,c147._compose)
                    totals.update(ranking_queries=len(positions),candidate_scores=scores.numel())
                    old.require(all(snapshot.catalog[p]["descriptor"]==descriptors[r["predicted_address"]]
                        for p,r in zip(positions,replay,strict=True)),"Live selection changed")
                    trace=output_dir/f"queries-{record['seed']}-{arm.lower()}-{order.lower()}.jsonl.gz"
                    with gzip.open(trace,"wt",encoding="utf-8",newline="\n") as f:
                        for j,(query,position) in enumerate(zip(suite["queries"],positions,strict=True)):
                            handle=snapshot.catalog[position]; ri=old.router_index(j); outputs=[]
                            for condition in CONDITIONS:
                                scope=f"C167|{record['seed']}|{arm}|{order}|{condition}"
                                result,out,ref,budget,mutated=old.execute_selected(scope,query["case_id"],handle,
                                    routers[ri],full_state,binding,registry,apis[condition],ops,j%2)
                                outputs.append(out)
                                target=ranking._key(descriptors[query["expected_address"]])
                                judged=recovery._assess_episode(result,condition,ref,full_state,
                                                                snapshot.values[handle["key"]],budget)
                                margins[condition]=min(margins[condition],*judged["margins"])
                                outcheck=old.assess_output(out,scope+"|"+query["case_id"],scope,ref,
                                    snapshot.values[handle["key"]],target,snapshot.values[target])
                                audit=presence_audit(result,ref,full_state,budget,condition==CONDITIONS[1])
                                emission=emitter.last
                                passed=bool(judged["passed"] and outcheck["bound"] and outcheck["serialization_ok"]
                                    and not mutated and all(emission["checks"].values()) and all(audit.values()))
                                counts=dict(episodes=1,failed_episodes=int(not passed),controller_decisions=len(result["steps"]),
                                    acquisitions=result["acquisitions"],publications=result["publications"],
                                    retrieval_calls=result["retrieval_calls"],vectors_scored=result["vectors_scored"],
                                    answered=int(out.status=="ANSWERED"),unresolved=int(out.status=="UNRESOLVED"))
                                totals.update(counts); by[condition].update(counts)
                                by[condition].update(terminal_correct=int(outcheck["bound"]))
                                by[condition].update({k:int(v) for k,v in audit.items()})
                                totals.update(output_mutations=int(mutated),serialization_failures=int(not outcheck["serialization_ok"]))
                                router_counts[str(ROUTERS[ri])]+=1; by_router[condition][str(ROUTERS[ri])]+=1
                                actions.update(str(s["action"]) for s in result["steps"])
                                groups[condition][arm][order].update(cases=1,binding_correct=int(outcheck["bound"]),
                                                                      semantic_correct=int(outcheck["semantic_correct"]))
                                if outcheck["bound"]:
                                    values[str(out.value)]+=1; by_values[condition][str(out.value)]+=1
                                f.write(json.dumps(dict(case_id=query["case_id"],text=query["text"],condition=condition,
                                    router_seed=ROUTERS[ri],selected_position=position,selected_key=handle["key"],
                                    initial_budget=asdict(budget),output=asdict(out),emission=emission,
                                    cycle=old.compact_cycle(result),cycle_assessment=judged,
                                    output_assessment=outcheck,presence_assessment=audit,passed=passed),
                                    sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                            totals["matched_output_pairs"]+=int(same_observed_output(*outputs))
                            if (j+1)%216==0:
                                print(f"[C167] head {model_i}/12 arm={arm} order={order} queries={j+1}/1728 "
                                    f"branch_episodes={totals['episodes']} failed={totals['failed_episodes']} remaining_queries={1727-j}",flush=True)
                    completed.append(dict(seed=record["seed"],split_id=record["split_id"],arm=arm,order=order,
                        file=trace.name,rows=2*old.QUERIES,sha256=old.sha(trace),serialized_bytes=trace.stat().st_size,composition_cost=cost))
                totals["weight_mutations"]+=int(ranking._fingerprint(head)!=fingerprint)
                del head,encoded,qv,dv,scores
        totals["weight_mutations"]+=sum(recovery._fingerprint(m)!=h for m,h in zip(routers,router_fingerprints,strict=True))
        controls_path=output_dir/"live-guard-controls.json"; controls_path.write_bytes(old.blob(emitter.controls))
        check_files(); diff.check_inputs(extra); check_source_code()
        old.require(subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()==head_sha,"HEAD changed")
        condition_summaries={c:dict(by[c],minimum_controller_margin=margins[c],
            router_episodes=dict(by_router[c]),answer_values=dict(by_values[c]),
            arms={a:{o:dict(g) for o,g in d.items()} for a,d in groups[c].items()}) for c in CONDITIONS}
        summary=dict(totals,conditions=condition_summaries,router_episodes=dict(router_counts),
            raw_action_counts=dict(actions),answer_values=dict(values),emission=emitter.summary(),
            c159_replay_calls=replay_outputs,source_codes_preserved=True,
            metered_adapter_calls=sum(b.adapter.calls for b in bindings.values()),
            metered_vectors_scored=sum(b.adapter.vectors for b in bindings.values()),
            loaded_rankers=24,loaded_routers=3,training_steps=0,fresh_seed_count=0,
            live_query_selection=True,live_cycle_exercised=True,structured_result_exercised=True,
            warm_reference_exercised=True,answer_generation_exercised=False,
            production_state_commit=False,new_evidence_epoch=False,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),wall_clock_seconds=time.perf_counter()-started)
        passed=gate(summary); summary["warm_reference_gate_passed"]=passed
        all_inputs={}
        for mapping in (protected,extra):
            for path,h in mapping.items():
                k=str(Path(path).resolve()); old.require(k not in all_inputs or all_inputs[k]==h,"Conflicting inputs"); all_inputs[k]=h
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,commit_sha=head_sha,
            C166_summary_sha256=C166_SHA,input_sha256=all_inputs,source_blobs=SOURCE_BLOBS,
            plan=dict(file=plan_path.name,sha256=old.sha(plan_path)),summary=summary,records=completed,
            controls=dict(file=controls_path.name,sha256=old.sha(controls_path)),
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,ranker_device=torch.cuda.get_device_name(0),
                controller_device="cpu",precision="float32/highest",threads=2),
            limitations=["82944 fresh ranking prefixes, each forked into cold63 and warm64 reference states",
                "Warm state is a fresh copy of the pinned fixture, not the cold branch final state",
                "Warm still pays one real exact64 dereference; not a cached answer or zero-IO memory read",
                "Only initial reference membership changes; no new training, permission or budget changes",
                "Known nine WITHIN_FACTOR errors repeat over two layouts AND two conditions:36 instances, not36 error types",
                "Parent traces are hash-checked; old C151/C159 prerequisite replays are separate",
                "Fixed synthetic task/epoch; no independent task generalization, semantic abstention, durability or production rollout",
                "Not warm language-session prefix reuse, learned answer generation or Gate E completion"])
        tmp=output_dir/"summary.partial.json"; tmp.write_bytes(old.blob(report)); tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(old.blob(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_streams=len(completed))))
        raise


def main():
    parser=argparse.ArgumentParser(description="C167 initial-reference-presence-only live comparison")
    parser.add_argument("--c166-summary",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    print("C167 rankings=82944; independent cold+warm continuations; episodes=165888",flush=True)
    print("C167 decisions=248832; acquisitions=82944; restorations=82944; reads=248832; vectors=15925248",flush=True)
    print("C167 both permission=True/budget=(3,1); warm pays one dereference; training=0; Gate E NOT PASSED",flush=True)
    report=run(**vars(parser.parse_args()))
    print("=== C167 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
