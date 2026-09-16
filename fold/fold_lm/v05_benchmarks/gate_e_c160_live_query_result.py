"""C160: frozen query ranking -> live C158 recovery -> C159 typed result.

Same synthetic task and pinned observation epoch. One authorized cold recovery
per query; no new training, open-set detector, language answer or production API.
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

EXPERIMENT_ID = "C160-v5e-live-query-to-terminal-result"
STAGE = "V5-E-LIVE-QUERY-TO-TERMINAL-RESULT"
C159_SHA = "522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6"
C159_COMMIT = "741ca66e93e389ffc7e90688dc924e04695da778"
ROUTER_SEEDS = (20261741, 20261742, 20261743)
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
QUERIES = 1728
EPISODES = 82944


class InvalidInput(ValueError):
    """Source/setup invalidity, not a finite incorrect measured output."""


def require(ok, message):
    if not ok:
        raise InvalidInput(message)


def blob(data):
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def ancestor(protected, digest):
    paths = {Path(p).resolve() for p, h in protected.items()
             if h == digest and Path(p).name == "summary.json"}
    require(len(paths) == 1, "Expected one pinned ancestor report")
    return paths.pop()


def router_index(query_index):
    if type(query_index) is not int or not 0 <= query_index < QUERIES:
        raise ValueError("Registered manifest index required")
    return query_index % 3


def header(prior, old):
    require(prior.get("experiment_id") == "C159-v5e-evidence-bound-terminal-result"
            and prior.get("commit_sha") == C159_COMMIT and prior.get("status") == "PASS"
            and prior.get("diagnostic_execution_valid") is True
            and prior.get("production_runtime_modified") is False
            and prior.get("gate_e_candidate") is False
            and prior.get("C158_summary_sha256") == old.SOURCE_SHA,
            "Expected accepted C159 report")
    s = prior.get("summary", {})
    require(old._gate(s) and s.get("terminal_result_gate_passed") is True
            and s.get("base_reasons") == {"OBSERVED_VALUE":768, "MISSING_DELIVERY":384,
                "PERMISSION_DENIED":384, "BUDGET_EXHAUSTED":384}
            and s.get("training_steps") == s.get("fresh_seed_count") == 0
            and all(s.get(k) is False for k in ("model_loading", "controller_exercised",
                "retrieval_exercised", "live_cycle_replayed", "answer_generation_exercised",
                "production_state_commit")), "C159 profile mismatch")
    require([r["router_seed"] for r in prior.get("records", [])] == list(ROUTER_SEEDS),
            "Full ordered C159 records required")


def validate_outputs(prior, source, plan, root, protected, old):
    """Replay the deterministic emitter only, not an old live/model run."""
    calls = 0
    for record, (origin, rows) in zip(prior["records"], source, strict=True):
        require((record["router_seed"], record["source_file"], record["source_sha256"]) ==
                (origin["router_seed"], origin["file"], origin["sha256"]), "C159 source binding drift")
        path = old._safe_file(root, record["file"])
        require(sha(path) == record["sha256"] and path.stat().st_size == record["serialized_bytes"],
                "C159 result bytes mismatch")
        protected[path] = record["sha256"]
        saved = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        require(len(saved) == len(rows) == 640, "C159 row coverage mismatch")
        for i, (row, stored) in enumerate(zip(rows, saved, strict=True)):
            bound = old._binding(plan["records"][i // 5])
            output = old.emit_terminal(bound, row["source_request_id"], row["result"])
            controls = []
            for name, rid, result, reason in old._variants(row):
                actual = old.emit_terminal(bound, rid, result)
                require(actual.status == "REJECTED" and actual.reason == reason
                        and old._no_payload(actual), "Accepted control not reproduced")
                controls.append(dict(condition=name, output=asdict(actual), passed=True))
            wanted = dict(source_row=i, source_request_id=row["source_request_id"],
                          scenario=row["scenario"], output=asdict(output), passed=True, controls=controls)
            require(stored == wanted, "C159 deterministic output replay mismatch")
            calls += 1 + len(controls)
    require(calls == 6528, "C159 replay count mismatch")
    return calls


def select_live(head, texts, catalog, features, compose):
    """No expected key/value/label. Every raw query is ranked against live descriptors."""
    import torch
    require(len(texts) == QUERIES and len(catalog) == 64, "Registered query/catalog shape required")
    descriptors = [h["descriptor"] for h in catalog]
    encoded, cost = compose(head, list(texts) + descriptors, features)
    q, d = encoded[:QUERIES], encoded[QUERIES:]
    with torch.inference_mode():
        scores = torch.cat([q[i:i+216] @ d.T for i in range(0, QUERIES, 216)])
        require(tuple(scores.shape) == (QUERIES, 64) and bool(torch.isfinite(scores).all()),
                "Invalid live ranking scores")
        positions = scores.argmax(dim=1).cpu().tolist()
    return positions, scores, cost


def execute_selected(scope, query_id, handle, router, full_state, binding, registry, api, ops, old_bit):
    """Only the learned selected handle enters recovery, never the evaluator target."""
    import numpy as np
    require(type(old_bit) is int and old_bit in (0, 1), "Registered stale bit required")
    request = api.Request(request_id=scope + "|" + query_id, scope_id=scope,
        key=handle["key"], domain=handle["domain"], schema=handle["schema"],
        operations=tuple(handle["operations"]), source_sha256=binding.source_sha256,
        index_fingerprint=binding.index_fingerprint, source_path=binding.source_path,
        request_epoch=binding.evidence_time, provider_generation=binding.revision)
    reference = api.EvidenceRef(request.key, api.Provenance(binding.source_id, api.OBSERVED,
                                binding.revision, binding.evidence_time))
    require(sum(r == reference for r in full_state.observations) == 1,
            "Selected handle missing from trusted reference fixture")
    state = replace(full_state, observations=tuple(r for r in full_state.observations
                                                  if r.evidence_id != request.key))
    read = api.ReadRequest(request.request_id, request.scope_id, reference,
                           request.domain, request.schema, request.operations)
    working = api.WorkingState(binding.evidence_time, 7,
                 np.array([[1.,1.,1.,float(old_bit),.125,-.25,.375,-.5]]))
    budget = api.BudgetState(3, 1)
    meter = binding.adapter
    before = (meter.calls, meter.vectors)
    result = api.cycle(router, read, request, state, working, budget, registry,
                       api.Permission(True), ops, lambda delivery: delivery)
    result.update(retrieval_calls=meter.calls-before[0], vectors_scored=meter.vectors-before[1])
    bound = api.BoundRequest(request.request_id, scope, request.key, binding.source_id,
                             binding.evidence_time, binding.revision)
    original = blob(result)
    output = api.emit(bound, request.request_id, result)
    mutated = blob(result) != original
    return result, output, reference, budget, mutated


def assess_output(output, request_id, scope, reference, selected_value, target_key, target_value):
    """Post-execution scoring; matching bit alone never establishes relevance."""
    p = reference.provenance
    bound = bool(output.status == "ANSWERED" and output.reason == "OBSERVED_VALUE"
        and output.request_id == request_id and output.scope_id == scope
        and output.record_key == reference.evidence_id and output.source_id == p.source_id
        and output.evidence_time == p.evidence_time and output.revision == p.revision
        and type(output.value) is int and output.value in (0,1) and output.value == selected_value)
    semantic = bound and output.record_key == target_key and output.value == target_value
    restored = json.loads(blob(asdict(output)))
    serial = restored == asdict(output) and (output.value is None or type(restored["value"]) is int)
    return dict(bound=bound, semantic_correct=bool(semantic), serialization_ok=serial)


def compact_cycle(result):
    """Keep every actual decision, not 64 repeated refs in each output row."""
    return {**{k:v for k,v in result.items() if k != "final_evidence"},
            "final_evidence_sha256":hashlib.sha256(blob(result["final_evidence"])).hexdigest(),
            "final_reference_count":len(result["final_evidence"]["observations"])}


def gate(s):
    if not (s.get("episodes") == EPISODES and s.get("failed_episodes") == 0
        and s.get("ranking_queries") == EPISODES and s.get("candidate_scores") == 64*EPISODES
        and s.get("controller_decisions") == 2*EPISODES and s.get("acquisitions") == EPISODES
        and s.get("publications") == EPISODES and s.get("retrieval_calls") == 2*EPISODES
        and s.get("vectors_scored") == 128*EPISODES and s.get("answered") == EPISODES
        and s.get("weight_mutations") == s.get("output_mutations") == s.get("serialization_failures") == 0
        and s.get("router_episodes") == {str(k):EPISODES//3 for k in ROUTER_SEEDS}
        and s.get("ranker_replay_cases") == 41472 and s.get("original12_replay_cases") == 288
        and s.get("c159_replay_calls") == 6528
        and math.isfinite(s.get("minimum_controller_margin", math.nan))
        and s["minimum_controller_margin"] > 0):
        return False
    return all(s.get("arms", {}).get(a, {}).get(o) == dict(cases=20736, binding_correct=20736,
                    semantic_correct=20727 if a == ARMS[0] else 20736)
               for a in ARMS for o in ORDERS)


def run(*, c159_summary, c151_summary, output_dir):
    import numpy as np
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
    from fold_lm.v05_benchmarks import gate_e_c157_controller_bridge as bridge
    from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
    from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter(); completed = []
    torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    try:
        require(sha(c159_summary) == C159_SHA, "C159 hash mismatch")
        prior = json.loads(c159_summary.read_text(encoding="utf-8")); header(prior, terminal)
        source = ancestor(prior["input_sha256"], terminal.SOURCE_SHA)
        _, old_plan, old_rows, protected, check_files = terminal._load_source(source)
        for p,h in prior["input_sha256"].items():
            p = Path(p); require(p not in protected or protected[p] == h, "Conflicting input hashes"); protected[p] = h
        protected[c159_summary] = C159_SHA
        replay_outputs = validate_outputs(prior, old_rows, old_plan, c159_summary.parent, protected, terminal)
        p153 = json.loads(ancestor(protected, payload.C153_SHA).read_text(encoding="utf-8"))
        # C155-C159 no longer needed the catalog, but C153 pinned its bytes.
        for name, h in p153["input_sha256"].items():
            path = Path(name)
            require(path not in protected or protected[path] == h, "Conflicting C153 source hash")
            protected[path] = h
        check_files()
        streams, metadata, _ = payload._load_inputs(ancestor(protected, payload.C154_SHA),
                                                   ancestor(protected, payload.C153_SHA), protected)
        states = {}; bindings = {}
        for record, state, _, _ in streams:
            order = record["order"]
            if order in states:
                require({r.evidence_id:r for r in states[order].observations} ==
                        {r.evidence_id:r for r in state.observations}, "Snapshot state disagreement")
            states[order] = state
        for sid, md in metadata.items():
            b = payload.load_binding(md)
            bindings[sid] = replace(b, adapter=recovery.MeteredAdapter(b.adapter))
        registry = MappingProxyType(bindings)
        p157_path = ancestor(protected, recovery.C157_SHA)
        p157 = json.loads(p157_path.read_text(encoding="utf-8")); recovery._header(p157)
        routers = []
        for record in p157["records"]:
            model, path = recovery._load_router(p157_path.parent, record)
            protected[path] = record["checkpoint"]["sha256"]; routers.append(model)
        router_fingerprints = [recovery._fingerprint(m) for m in routers]
        root = c151_summary.parent
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        protected.update({c151_summary:ranking.SOURCE_SHA, root/"evaluation-manifest.json":ranking.MANIFEST_SHA,
                          root/"split-plan.json":ranking.PLAN_SHA, fixture:ranking.QUERY_SHA})
        check_files()
        p151 = json.loads(c151_summary.read_text(encoding="utf-8"))
        suite = json.loads((root/"evaluation-manifest.json").read_text(encoding="utf-8"))
        split = json.loads((root/"split-plan.json").read_text(encoding="utf-8"))
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        require(suite == c143._build_suite(rows) and split == c151._build_plan(rows), "Manifest/generator mismatch")
        ranking._validate_source(p151, suite, split, c151, c146)
        vocabulary = c139._training_vocabulary(rows)
        require(len(vocabulary) == 49 and c139._fixture_oov_count(rows,vocabulary) == 0, "Vocabulary/OOV drift")
        require(torch.cuda.is_available(), "CUDA needed for unchanged frozen ranker replay")
        torch.cuda.set_device(0); device = torch.device("cuda")
        features = lambda texts: c139._collision_free_text_features(list(texts),vocabulary,device=device)
        snapshots = {}
        for order, state in states.items():
            b = bindings[state.observations[0].provenance.source_id]
            path = Path(b.source_path).parent / "catalog.json"
            require(path in protected, "Catalog not pinned by accepted artifact chain")
            snapshots[order] = ranking._load_snapshot(path, Path(b.source_path), lambda _: b.adapter)
        texts = [q["text"] for q in suite["queries"]]; descriptors = suite["descriptors"]
        labels = [q["expected_address"] for q in suite["queries"]]
        require(len({q["case_id"] for q in suite["queries"]}) == QUERIES, "Unique query identities required")
        old_indices = [texts.index(r["validation"]) for r in rows]
        plan = dict(queries=QUERIES, ranker_seeds=list(ranking.SEEDS), arms=ARMS, orders=ORDERS,
            routers=ROUTER_SEEDS, router_assignment="manifest_query_index_modulo_3",
            scenario="COLD_RECOVER", episodes=EPISODES, query_manifest_sha256=ranking.MANIFEST_SHA)
        plan_path = output_dir/"query-cycle-plan.json"; plan_path.write_bytes(blob(plan))
        protected[plan_path] = sha(plan_path)
        def fetch(req, reg):
            b = reg[payload._source_id(asdict(req))]
            return admission._fetch(req, asdict(b.handles[req.key]), b.adapter)
        def entry_ref(entry):
            raw = asdict(entry); raw["request"]["operations"] = list(raw["request"]["operations"])
            return projection._ref_from_entry(raw)
        ops = SimpleNamespace(reobserve=observe.reobserve, control_inputs=observe.control_inputs,
            resolver=payload.resolve_reference, empty_inbox=admission.State, fetch=fetch,
            admit=admission.admit, entry_ref=entry_ref, project=projection.project_observation)
        api = SimpleNamespace(Request=admission.Request, EvidenceRef=core.EvidenceRef, Provenance=core.Provenance,
            OBSERVED=core.ProvenanceKind.OBSERVED, ReadRequest=observe.ReadRequest, WorkingState=core.WorkingState,
            BudgetState=core.BudgetState, Permission=recovery.Permission, cycle=recovery.cycle,
            BoundRequest=terminal.BoundRequest, emit=terminal.emit_terminal)
        groups = {a:{o:Counter() for o in ORDERS} for a in ARMS}; totals=Counter(); router_counts=Counter()
        minimum_margin = math.inf
        print("[C160] accepted outputs/state lineage verified; plan fixed; no new training", flush=True)
        torch.cuda.reset_peak_memory_stats()
        for model_i, record in enumerate(p151["records"], 1):
            for arm in ARMS:
                head, path = ranking._load_head(root,record,arm,vocabulary,SharedRetrievalContentHead,device)
                protected[path] = record["arms"][arm]["checkpoint"]["sha256"]
                fingerprint = ranking._fingerprint(head)
                encoded, _ = c147._compose(head,texts+descriptors,features)
                with torch.inference_mode():
                    qv,dv=encoded[:QUERIES],encoded[QUERIES:]
                    replay=[]
                    for i in range(0,QUERIES,216):
                        replay.extend(c147._rank(qv[i:i+216]@dv.T,labels[i:i+216]))
                    original=c147._rank(qv[old_indices]@dv[:12].T,list(range(12)))
                ranking._check_replay(replay,record["arms"][arm]["results"])
                ranking._check_replay(original,record["arms"][arm]["original12"])
                totals.update(ranker_replay_cases=QUERIES,original12_replay_cases=12)
                for order in ORDERS:
                    snapshot=snapshots[order]; full_state=states[order]
                    binding=bindings[full_state.observations[0].provenance.source_id]
                    positions,scores,cost=select_live(head,texts,snapshot.catalog,features,c147._compose)
                    totals.update(ranking_queries=len(positions), candidate_scores=scores.numel())
                    require(all(snapshot.catalog[p]["descriptor"] == descriptors[r["predicted_address"]]
                        for p,r in zip(positions,replay,strict=True)), "Live ordered catalog selection changed")
                    scope=f"C160|{record['seed']}|{arm}|{order}"
                    trace=output_dir/f"queries-{record['seed']}-{arm.lower()}-{order.lower()}.jsonl.gz"
                    with gzip.open(trace,"wt",encoding="utf-8",newline="\n") as f:
                        for j,(query,position) in enumerate(zip(suite["queries"],positions,strict=True)):
                            handle=snapshot.catalog[position]; ri=router_index(j)
                            result,out,ref,budget,mutated=execute_selected(scope,query["case_id"],handle,
                                routers[ri],full_state,binding,registry,api,ops,j%2)
                            # Ground truth and source values are consulted only after output emission.
                            target=ranking._key(descriptors[query["expected_address"]])
                            judged=recovery._assess_episode(result,"COLD_RECOVER",ref,full_state,snapshot.values[handle["key"]],budget)
                            minimum_margin = min(minimum_margin, *judged["margins"])
                            outcheck=assess_output(out,scope+"|"+query["case_id"],scope,ref,
                                snapshot.values[handle["key"]],target,snapshot.values[target])
                            passed=bool(judged["passed"] and outcheck["bound"] and outcheck["serialization_ok"] and not mutated)
                            groups[arm][order].update(cases=1,binding_correct=int(outcheck["bound"]),semantic_correct=int(outcheck["semantic_correct"]))
                            totals.update(episodes=1,failed_episodes=int(not passed),controller_decisions=len(result["steps"]),
                                acquisitions=result["acquisitions"],publications=result["publications"],answered=int(out.status=="ANSWERED"),
                                output_mutations=int(mutated),serialization_failures=int(not outcheck["serialization_ok"]))
                            router_counts[str(ROUTER_SEEDS[ri])]+=1
                            f.write(json.dumps(dict(case_id=query["case_id"],text=query["text"],router_seed=ROUTER_SEEDS[ri],
                                selected_position=position,selected_key=handle["key"],output=asdict(out),
                                cycle=compact_cycle(result),cycle_assessment=judged,output_assessment=outcheck,passed=passed),
                                sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                            if (j+1)%216==0:
                                print(f"[C160] head {model_i}/12 arm={arm} order={order} queries={j+1}/1728 "
                                      f"failed={totals['failed_episodes']} remaining_queries={1727-j}",flush=True)
                    completed.append(dict(seed=record["seed"],split_id=record["split_id"],arm=arm,order=order,
                        file=trace.name,sha256=sha(trace),serialized_bytes=trace.stat().st_size,composition_cost=cost))
                totals["weight_mutations"]+=int(ranking._fingerprint(head)!=fingerprint)
                del head,encoded,qv,dv,scores
        totals["weight_mutations"]+=sum(recovery._fingerprint(m)!=h for m,h in zip(routers,router_fingerprints,strict=True))
        check_files()
        summary=dict(totals,retrieval_calls=sum(b.adapter.calls for b in bindings.values()),
            vectors_scored=sum(b.adapter.vectors for b in bindings.values()),router_episodes=dict(router_counts),
            arms={a:{o:dict(v) for o,v in d.items()} for a,d in groups.items()},c159_replay_calls=replay_outputs,
            minimum_controller_margin=minimum_margin,
            loaded_rankers=24,loaded_routers=3,fresh_seed_count=0,training_steps=0,live_query_selection=True,
            live_cycle_exercised=True,structured_result_exercised=True,answer_generation_exercised=False,
            production_state_commit=False,new_evidence_epoch=False,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),
            wall_clock_seconds=time.perf_counter()-started)
        passed=gate(summary);summary["live_query_result_gate_passed"]=passed
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C159_summary_sha256=C159_SHA,C151_summary_sha256=ranking.SOURCE_SHA,input_sha256={str(p):h for p,h in protected.items()},
            episode_plan=dict(file=plan_path.name,sha256=sha(plan_path)),summary=summary,records=completed,
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,ranker_device=torch.cuda.get_device_name(0),
                controller_device="cpu",precision="float32/highest",threads=2),
            limitations=["Same synthetic closed-set queries/known aliases; no fresh task or language generalization",
                "Each query uses one manifest-index-assigned frozen Controller, not all three for every ranker/query",
                "Only authorized COLD_RECOVER is newly exercised; older denied/missing-delivery controls are not rerun",
                "Cold state removes selected ref from a known 64-ref snapshot, not an initially empty world",
                "ANSWERED deterministically copies observed Boolean payload; not learned/generated semantic answer content",
                "Authentic irrelevant control evidence must remain a semantic error even if its bit matches",
                "Exact64 acquisition plus exact64 readback, no efficient retrieval or production performance claim",
                "No dynamic epoch, durable publication, concurrency, relevance-based abstention or Gate E completion"])
        tmp=output_dir/"summary.partial.json";tmp.write_bytes(blob(report));tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status="INVALID",diagnostic_execution_valid=False,
            error=str(exc),completed_streams=len(completed))))
        raise


def main():
    p=argparse.ArgumentParser(description="C160 frozen live query-to-terminal-result composition")
    for name in ("c159-summary","c151-summary","output-dir"):
        p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args()
    print("C160 rankers=24 CUDA; routers=3 CPU; training=0; fresh_seeds=0",flush=True)
    print("C160 query_episodes=82944; live_decisions=165888; exact_reads=165888; vectors=10616832",flush=True)
    print("C160 scenario=COLD_RECOVER; query_index_modulo_3 router schedule; no language generation",flush=True)
    report=run(**vars(args));print("=== C160 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
