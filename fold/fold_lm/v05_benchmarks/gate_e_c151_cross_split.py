"""C151: fixed-recipe replication across four new main-training splits.

Same synthetic lexicon/task, NOT an independent language benchmark. Splits are
selected by data-only structural rules, never by model results. No recipe sweep.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import torch

EXPERIMENT_ID = "C151-v5e-cross-split-replication"
STAGE = "V5-E-CROSS-SPLIT-REPLICATION"
PRIOR_ID = "C150-v5e-global-auxiliary-negatives"
PRIOR_COMMIT = "1e9cfdbaf3631dbb207d2177f6ff6291673ec286"
PRIOR_SHA = "7e87a93e60ad334a9077fa132a0dc73da07a3da159c6f572d81190b66c8b95e7"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
SEEDS = tuple(range(20261721, 20261733))
AXES = ("COLOR", "SHAPE", "MATERIAL")
PLAN_SHA = "db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0"


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _vocabulary_schedule(rows):
    """Only source TRAIN fields; keep each value's original three alias slots."""
    maps = [dict() for _ in AXES]
    old = []
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        words = row["descriptor"].split()
        trains = [q.split() for q in row["train"]]
        if len(words) != 3 or len(trains) != 3 or any(len(q) != 3 for q in trains):
            raise ValueError("Expected three-factor, three-query training rows")
        old.append(row["descriptor"])
        for axis, value in enumerate(words):
            aliases = tuple(q[axis] for q in trains)
            if len(set(aliases)) != 3 or (value in maps[axis] and maps[axis][value] != aliases):
                raise ValueError("Conflicting original alias schedule")
            maps[axis][value] = aliases
    if len(old) != 8 or len(set(old)) != 8 or any(len(m) != 4 for m in maps):
        raise ValueError("Expected eight unique training triples and four values per factor")
    words = [w for m in maps for w in m]
    aliases = [a for m in maps for seq in m.values() for a in seq]
    if len(set(words)) != 12 or len(set(aliases)) != 36 or set(words) & set(aliases):
        raise ValueError("Canonical and alias identities must be disjoint")
    return maps, sorted(old)


def _build_plan(rows):
    maps, old = _vocabulary_schedule(rows)
    values = [sorted(m) for m in maps]
    used = set(old)
    splits = []
    # Structural rejection only: unique triples, balanced marginals, disjoint train sets.
    for split_index in range(4):
        for attempt in range(10000):
            columns = []
            for axis in range(3):
                order = sorted(range(8), key=lambda i: (
                    hashlib.sha256(f"C151|{split_index}|{attempt}|{axis}|{i}".encode()).digest(), i))
                columns.append([values[axis][i % 4] for i in order])
            descriptors = sorted(" ".join(p) for p in zip(*columns, strict=True))
            if len(set(descriptors)) == 8 and not used.intersection(descriptors):
                break
        else:
            raise RuntimeError("Registered structural split generator exhausted")
        used.update(descriptors)
        texts = [" ".join(maps[a][word][k] for a, word in enumerate(d.split()))
                 for d in descriptors for k in range(3)]
        splits.append(dict(split_id=f"S{split_index+1}", structural_attempt=attempt,
                           fresh_seeds=list(SEEDS[3*split_index:3*split_index+3]),
                           descriptors=descriptors, queries=texts,
                           targets=[i for i in range(8) for _ in range(3)],
                           factor_value_counts={axis:dict(sorted(Counter(d.split()[a] for d in descriptors).items()))
                                                for a, axis in enumerate(AXES)}))
    return dict(schema_version=1, experiment_id=EXPERIMENT_ID,
                generator="SHA256-per-column-order-v1; first admissible structural split",
                source_training_descriptors=old, splits=splits)


def _training_rows(split):
    return [dict(key=f"train-{i}", descriptor=d, split="TRAIN_COMBINATION",
                 train=split["queries"][3*i:3*i+3]) for i, d in enumerate(split["descriptors"])]


def _perfect(results):
    return bool(results) and all(r["correct"] is True and math.isfinite(r["expected_margin"])
                                and r["expected_margin"] > 0 for r in results)


def _partition_metrics(results, suite, training_descriptors, audit):
    metrics = audit(results, suite)
    metrics.pop("groups")  # Do not reuse C143's obsolete TRAIN/HELDOUT assignment.
    membership = set(training_descriptors)
    groups = {}
    for name, in_train in (("CURRENT_TRAIN_COMBINATION", True), ("HELDOUT_COMBINATION", False)):
        selected = [r for q, r in zip(suite["queries"], results, strict=True)
                    if (suite["descriptors"][q["expected_address"]] in membership) == in_train]
        if not selected:
            raise ValueError("Both split partitions must be nonempty")
        groups[name] = dict(cases=len(selected), correct=sum(r["correct"] for r in selected),
                            accuracy=sum(r["correct"] for r in selected)/len(selected),
                            min_expected_margin=min(r["expected_margin"] for r in selected))
    metrics["groups"] = groups
    return metrics


def _validate_prior(data, suite, audit, pair):
    if (data.get("experiment_id") != PRIOR_ID or data.get("commit_sha") != PRIOR_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA):
        raise ValueError("Expected accepted C150 PASS")
    s = data["summary"]
    required = dict(fresh_seeds=list(range(20261701,20261713)), paired_heads=24, **CONFIG,
                    train_steps=600, learning_rate=.002, logit_scale=12.0,
                    training_composition="POOL_THEN_ENCODE", evaluation_composition="ENCODE_THEN_POOL",
                    positive_alias_pairs=36, auxiliary_coefficients=[1.0,1.0,1.0],
                    auxiliary_loss_reduction="sum of three 12-alias means",
                    control_auxiliary_candidates=4,treatment_auxiliary_candidates=12,
                    training_main_queries=24,training_main_candidates=8,
                    full_candidate_count=64,queries_per_model=1728,full_cases_per_arm=20736,
                    original12_cases_per_arm=144,paired_initialization_verified=True,
                    evaluation_weights_preserved=True,evaluation_oov_count=0,inference_oracle_used=False,
                    scoring_rule_changed=False,runtime_path_exercised=False,
                    composition_reference_match_rate=1.0,global_negative_gate_passed=True)
    if any(s.get(k) != v for k,v in required.items()):
        raise ValueError("C150 configuration/control mismatch")
    records = data.get("records")
    if not isinstance(records,list) or [r.get("seed") for r in records] != required["fresh_seeds"]:
        raise ValueError("Full ordered C150 records required")
    old_suite = dict(descriptors=suite["descriptors"][:12],queries=[dict(expected_address=i) for i in range(12)])
    flat = {a:[] for a in ARMS}
    for record in records:
        for arm in ARMS:
            e = record["arms"][arm]
            if len(e["results"]) != 1728 or len(e["original12"]) != 12:
                raise ValueError("C150 coverage mismatch")
            m = audit(e["results"],suite)
            expected_errors = int(arm == ARMS[0] and record["seed"] == 20261712)
            if (m != e["metrics"] or m["errors"] != expected_errors or not _perfect(e["original12"])
                    or e["auxiliary_candidate_scope"] != arm or e["evaluation_composition"] != "ENCODE_THEN_POOL"
                    or e["training"]["optimizer_steps"] != 600 or e["composition_reference_match"] is not True):
                raise ValueError("C150 model accounting/configuration mismatch")
            audit(e["original12"],old_suite)
            flat[arm].extend(e["results"])
        a,b = (record["arms"][arm] for arm in ARMS)
        if (a["initial_head_sha256"] != b["initial_head_sha256"]
                or pair(a["results"],b["results"],suite) != record["paired"]):
            raise ValueError("C150 initial/pair mismatch")
    repeated = dict(descriptors=suite["descriptors"],queries=suite["queries"]*12)
    for arm in ARMS:
        m = audit(flat[arm],repeated)
        m.update(full_model_pass_count=sum(_perfect(r["arms"][arm]["results"]) for r in records),
                 original12_full_pass_count=12)
        if m != s["arms"][arm]:
            raise ValueError("C150 aggregate mismatch")
    p = pair(flat[ARMS[0]],flat[ARMS[1]],repeated)
    if p != s["paired"] or (p["rescued_errors"],p["new_errors"],p["both_correct"],p["both_wrong"]) != (1,0,20735,0):
        raise ValueError("C150 aggregate pair mismatch")


def _save_head(path, head, vocabulary, split_id, arm, fingerprint):
    torch.save(dict(state_dict={k:v.detach().cpu().clone() for k,v in head.state_dict().items()},
                    config=CONFIG,vocabulary=list(vocabulary),experiment_id=EXPERIMENT_ID,
                    split_id=split_id,auxiliary_candidate_scope=arm,split_plan_sha256=PLAN_SHA,
                    training_composition="POOL_THEN_ENCODE",inference_composition="ENCODE_THEN_POOL"),path)
    return dict(path=str(path),sha256=_sha(path),serialized_bytes=path.stat().st_size,
                tensor_sha256=fingerprint(head))


def run(*, c150_summary: Path, output_dir: Path):
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    from fold_lm.v05_benchmarks import gate_e_c148_train_consistent_composition as c148
    from fold_lm.v05_benchmarks import gate_e_c150_global_negatives as c150
    output_dir.mkdir(parents=True,exist_ok=False)
    completed=[]
    try:
        fixture=Path(__file__).parent/"fixtures/c138_compositional_alias_queries.json"
        source_manifest=c150_summary.parent/"evaluation-manifest.json"
        protected={c150_summary:PRIOR_SHA,source_manifest:MANIFEST_SHA,fixture:QUERY_SHA,
                   Path("runs/chatgpt-last-result.json"):C37_SHA,
                   Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
        def check_files():
            for path,sha in protected.items():
                if _sha(path)!=sha: raise RuntimeError(f"Input/protected mismatch: {path}")
        check_files()
        rows=json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite=json.loads(source_manifest.read_text(encoding="utf-8"))
        if suite!=c143._build_suite(rows): raise RuntimeError("Manifest/generator drift")
        _validate_prior(json.loads(c150_summary.read_text(encoding="utf-8")),suite,c146._audit_results,c146._pair)
        if c150.CONFIG!=CONFIG or (c150.STEPS,c150.LR,c150.SCALE)!=(600,.002,12.0):
            raise RuntimeError("Frozen training recipe drift")
        plan=_build_plan(rows)
        if hashlib.sha256(_bytes(plan)).hexdigest()!=PLAN_SHA: raise RuntimeError("Split-plan drift")
        (output_dir/"split-plan.json").write_bytes(_bytes(plan))
        (output_dir/"evaluation-manifest.json").write_bytes(source_manifest.read_bytes())
        protected[output_dir/"split-plan.json"]=PLAN_SHA
        protected[output_dir/"evaluation-manifest.json"]=MANIFEST_SHA
        # All four partitions are committed to disk BEFORE any model is trained.
        vocabulary=c139._training_vocabulary(rows)
        original_pairs=c146._training_specs(rows)[1]
        if len(vocabulary)!=49: raise RuntimeError("Vocabulary dimension mismatch")
        if not torch.cuda.is_available(): raise RuntimeError("Formal C151 execution requires CUDA")
        torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
        device=torch.device("cuda")
        def features(texts): return c139._collision_free_text_features(list(texts),vocabulary,device=device)
        def tensors(spec): return features(spec[0]),features(spec[1]),torch.tensor(spec[2],dtype=torch.long,device=device)
        qt=[q["text"] for q in suite["queries"]]; dt=suite["descriptors"]
        batch=c148._prepare(qt+dt,features)
        labels=[q["expected_address"] for q in suite["queries"]]
        old_indices=[qt.index(r["validation"]) for r in rows]
        started=time.perf_counter()
        for split in plan["splits"]:
            train_rows=_training_rows(split)
            main_spec,pairs=c146._training_specs(train_rows)
            if pairs!=original_pairs or c139._training_vocabulary(train_rows)!=vocabulary:
                raise RuntimeError("New split altered auxiliary supervision or vocabulary")
            main=tensors(main_spec)
            alignments={arm:{axis:tensors(s) for axis,s in c150._candidate_specs(pairs,arm).items()} for arm in ARMS}
            input_before=_bytes((rows,suite,plan))
            for seed in split["fresh_seeds"]:
                index=len(completed)+1
                torch.manual_seed(seed+13900)
                prototype=SharedRetrievalContentHead(**CONFIG).to(device)
                initial=c148._fingerprint(prototype)
                heads={arm:copy.deepcopy(prototype) for arm in ARMS}; del prototype
                if any(c148._fingerprint(h)!=initial for h in heads.values()): raise RuntimeError("Pair mismatch")
                print(f"[C151] split={split['split_id']} pair {index}/12 seed={seed} paired_initial_weights_equal=True",flush=True)
                entries={}
                for arm in ARMS:
                    head=heads[arm]
                    def progress(step,loss):
                        print(f"[C151] split={split['split_id']} pair {index}/12 arm={arm} train {step}/600 main={loss[0]:.8f}",flush=True)
                    torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats(); start=time.perf_counter()
                    training=c150._train(head,main,alignments[arm],progress=progress)
                    torch.cuda.synchronize()
                    training.update(wall_clock_seconds=time.perf_counter()-start,
                                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                                    within_factor_fit=c150._fit(head,alignments[ARMS[0]]),global_concept_fit=c150._fit(head,alignments[ARMS[1]]))
                    frozen=c148._fingerprint(head)
                    with torch.inference_mode(): encoded=c148._encode(head,batch,c150.EVAL_MODE)
                    reference,cost=c147._compose(head,qt+dt,features)
                    if not torch.allclose(encoded,reference,atol=1e-6,rtol=0): raise RuntimeError("Evaluator reference mismatch")
                    eq,ed=encoded[:1728],encoded[1728:]; results=[]
                    with torch.inference_mode():
                        for offset in range(0,1728,216):
                            results.extend(c147._rank(eq[offset:offset+216]@ed.T,labels[offset:offset+216]))
                            print(f"[C151] split={split['split_id']} pair {index}/12 arm={arm} audited={offset+216}/1728 remaining={1512-offset}",flush=True)
                        old=c147._rank(eq[old_indices]@ed[:12].T,list(range(12)))
                    if c148._fingerprint(head)!=frozen or _bytes((rows,suite,plan))!=input_before:
                        raise RuntimeError("Evaluation mutation")
                    entries[arm]=dict(training=training,initial_head_sha256=initial,final_head_sha256=frozen,
                        results=results,metrics=_partition_metrics(results,suite,split["descriptors"],c146._audit_results),
                        original12=old,original12_all_pass=_perfect(old),composition_accounting=cost,
                        parameter_count=sum(p.numel() for p in head.parameters()),
                        checkpoint=_save_head(output_dir/f"{split['split_id']}-seed-{seed}-{arm.lower()}.pt",head,vocabulary,split["split_id"],arm,c148._fingerprint))
                paired=c146._pair(entries[ARMS[0]]["results"],entries[ARMS[1]]["results"],suite)
                completed.append(dict(split_id=split["split_id"],seed=seed,arms=entries,paired=paired))
                print(f"[C151] pair {index}/12 complete within_errors={entries[ARMS[0]]['metrics']['errors']} global_errors={entries[ARMS[1]]['metrics']['errors']} remaining_pairs={12-index}",flush=True)
                del heads,head,encoded,reference,eq,ed
        check_files()
        by_split={}
        for split in plan["splits"]:
            models=[r for r in completed if r["split_id"]==split["split_id"]]
            repeated=dict(descriptors=dt,queries=suite["queries"]*3)
            by_split[split["split_id"]]={}
            for arm in ARMS:
                flat=[x for r in models for x in r["arms"][arm]["results"]]
                m=_partition_metrics(flat,repeated,split["descriptors"],c146._audit_results)
                m.update(full_model_pass_count=sum(_perfect(r["arms"][arm]["results"]) for r in models),
                         original12_full_pass_count=sum(r["arms"][arm]["original12_all_pass"] for r in models))
                by_split[split["split_id"]][arm]=m
        flat={a:[x for r in completed for x in r["arms"][a]["results"]] for a in ARMS}
        totals={a:dict(cases=len(flat[a]),correct=sum(x["correct"] for x in flat[a]),
                      errors=sum(not x["correct"] for x in flat[a]),min_expected_margin=min(x["expected_margin"] for x in flat[a]),
                      full_model_pass_count=sum(_perfect(r["arms"][a]["results"]) for r in completed),
                      original12_full_pass_count=sum(r["arms"][a]["original12_all_pass"] for r in completed)) for a in ARMS}
        passed=totals[ARMS[1]]["full_model_pass_count"]==12 and totals[ARMS[1]]["original12_full_pass_count"]==12
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C150_summary_sha256=PRIOR_SHA,evaluation_manifest_sha256=MANIFEST_SHA,split_plan_sha256=PLAN_SHA,
            input_sha256={str(p):h for p,h in protected.items()},
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,device=torch.cuda.get_device_name(0)),
            summary=dict(fresh_seeds=list(SEEDS),new_splits=4,seeds_per_split=3,paired_heads=24,**CONFIG,
                train_steps=600,learning_rate=.002,logit_scale=12.,auxiliary_coefficients=[1.,1.,1.],
                training_main_queries=24,training_main_candidates=8,positive_alias_pairs=36,
                full_cases_per_arm=20736,original12_cases_per_arm=144,heldout_combinations_per_split=56,
                recipe_changed=False,independent_task=False,inference_oracle_used=False,runtime_path_exercised=False,
                paired_initialization_verified=True,evaluation_weights_preserved=True,composition_reference_match_rate=1.,
                arms=totals,by_split=by_split,paired=c146._pair(flat[ARMS[0]],flat[ARMS[1]],dict(descriptors=dt,queries=suite["queries"]*12)),
                cross_split_gate_passed=passed,wall_clock_seconds=time.perf_counter()-started),records=completed,
            limitations=["New main-training splits within the SAME synthetic task; not independent semantics or language",
                         "Data-only balanced disjoint split construction fixed before model training; no performance-based sampling",
                         "Original alias schedule and all 36 explicit positive pairs retained; not factor discovery",
                         "Same 600-step C150 recipe; paired candidate-scope comparison is not compute-matched",
                         "No extra labels, coefficient search or favorable-seed selection after results",
                         "All original12 and full64 evaluations are ranking-only; Gate E remains NOT PASSED"])
        temp=output_dir/"summary.partial.json"; temp.write_bytes(_bytes(report)); temp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID,status="INVALID",error=str(exc),completed_pairs=len(completed))))
        raise


def main():
    parser=argparse.ArgumentParser(description="C151 fixed-recipe cross-split replication")
    parser.add_argument("--c150-summary",type=Path,required=True); parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    print("C151 new_splits=4; seeds_per_split=3; fresh_seeds=20261721..20261732; heads=24",flush=True)
    print("C151 same_task=True; frozen_recipe=True; ranking_only=True; full_rankings=41472; original12=288",flush=True)
    r=run(c150_summary=args.c150_summary,output_dir=args.output_dir)
    print("=== C151 RESULT ===",flush=True)
    print(json.dumps(dict(r,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__=="__main__": raise SystemExit(main())
