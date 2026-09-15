"""C149: frozen score accounting, NOT a new scorer or a model-quality gate.

Attribute positions label an after-the-fact decomposition only. Ranking uses
unchanged C148 encode-then-pool with no expected labels or typed slots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import torch

EXPERIMENT_ID = "C149-v5e-frozen-margin-accounting"
STAGE = "V5-E-FROZEN-MARGIN-ACCOUNTING"
PRIOR_ID = "C148-v5e-train-consistent-composition"
PRIOR_COMMIT = "dd0387b9cbee8ba38142b4ad7594c277d02b8c9d"
PRIOR_SHA = "4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
SEEDS = tuple(range(20261681, 20261693))  # Reused checkpoints, not fresh seeds.
ARMS = ("POOLED_TRAIN", "COMPOSED_TRAIN")
MODES = ("POOL_THEN_ENCODE", "ENCODE_THEN_POOL")
AXES = ("COLOR", "SHAPE", "MATERIAL")
RECONSTRUCTION_ATOL = 1e-5
PARTS = ("same_factor", "cross_factor", "candidate_norm")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _decompose(query: torch.Tensor, expected: torch.Tensor, rival: torch.Tensor) -> dict:
    """Symmetric exact algebra on frozen unit embeddings, accumulated in float64.

    E = sum_i a_i dot sum_j b^E_j; R analogously. Let nq,nE,nR be
    the three sum norms, alpha=(1/nE+1/nR)/2, beta=(1/nE-1/nR)/2.
    margin = alpha*(E-R)/nq + beta*(E+R)/nq.
    Split E-R into same-factor (diagonal) and cross-factor terms.
    This allocation is a declared convention, not unique causal attribution.
    """
    tensors = (query, expected, rival)
    if (any(not isinstance(t, torch.Tensor) or t.ndim != 3 for t in tensors)
            or any(t.shape != query.shape for t in tensors)
            or query.shape[0] < 1 or query.shape[1] != 3 or query.shape[2] < 1):
        raise ValueError("Equal nonempty [batch, 3, dimension] tensors required")
    a, e, r = [t.detach().to(device="cpu", dtype=torch.float64) for t in tensors]
    for t in (a, e, r):
        if not torch.isfinite(t).all() or not torch.allclose(
                t.norm(dim=-1), torch.ones_like(t[..., 0]), atol=5e-6, rtol=0):
            raise ValueError("Finite unit-normalized embeddings required")
    nq, ne, nr = (t.sum(1).norm(dim=-1) for t in (a, e, r))
    if any((n <= 1e-12).any() for n in (nq, ne, nr)):
        raise ValueError("Undefined normalization of unit sum")
    ge, gr = torch.einsum("bid,bjd->bij", a, e), torch.einsum("bid,bjd->bij", a, r)
    en, rn = ge.sum((1, 2)), gr.sum((1, 2))
    diagonal = (ge-gr).diagonal(dim1=1, dim2=2).sum(1)
    alpha, beta = (ne.reciprocal()+nr.reciprocal())/2, (ne.reciprocal()-nr.reciprocal())/2
    same = alpha*diagonal/nq
    cross = alpha*(en-rn-diagonal)/nq
    norm = beta*(en+rn)/nq
    direct = en/(nq*ne)-rn/(nq*nr)
    rebuilt = same+cross+norm
    if not torch.allclose(rebuilt, direct, atol=1e-10, rtol=0):
        raise ValueError("Decomposition identity failed")
    return dict(same_factor=same, cross_factor=cross, candidate_norm=norm,
                reconstructed_margin=rebuilt, direct_margin=direct,
                query_sum_norm=nq, expected_sum_norm=ne, rival_sum_norm=nr,
                expected_unit_dot_matrix=ge, rival_unit_dot_matrix=gr)


def _validate_prior(data: dict, suite: dict, audit, pair, perfect) -> list[dict]:
    s = data.get("summary", {})
    if (data.get("experiment_id") != PRIOR_ID or data.get("commit_sha") != PRIOR_COMMIT
            or data.get("status") != "FAIL" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA):
        raise ValueError("Expected accepted C148 valid negative")
    if (s.get("fresh_seeds") != list(SEEDS) or s.get("evaluation_composition") != MODES[1]
            or s.get("train_consistent_composition_gate_passed") is not False
            or s.get("paired_heads") != 24 or s.get("train_steps") != 600
            or any(s.get(k) != v for k,v in CONFIG.items())):
        raise ValueError("C148 configuration mismatch")
    for field in ("paired_initialization_verified", "evaluation_weights_preserved"):
        if s.get(field) is not True:
            raise ValueError("C148 execution control mismatch")
    if (s.get("inference_oracle_used") is not False or s.get("runtime_path_exercised") is not False
            or s.get("evaluation_oov_count") != 0 or s.get("composition_reference_match_rate") != 1.0):
        raise ValueError("C148 evaluation control mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != list(SEEDS):
        raise ValueError("Full ordered C148 records required, not console summary")
    expected_counts = ([0,0,5,0,0,0,0,0,0,0,0,6], [0,0,6,0,0,0,0,0,0,0,0,6])
    flat = {arm: [] for arm in ARMS}
    old_suite = dict(descriptors=suite["descriptors"][:12], queries=[dict(expected_address=i) for i in range(12)])
    for i, record in enumerate(records):
        for arm, mode, counts in zip(ARMS, MODES, expected_counts, strict=True):
            entry = record["arms"][arm]
            m = audit(entry["results"], suite)
            if (len(entry["results"]) != 1728 or m != entry["metrics"] or m["errors"] != counts[i]
                    or entry["evaluation_composition"] != MODES[1]
                    or entry["training"]["training_composition"] != mode
                    or entry["training"]["optimizer_steps"] != 600
                    or entry.get("composition_reference_match") is not True):
                raise ValueError("C148 per-model accounting or mode mismatch")
            audit(entry["original12"], old_suite)
            if len(entry["original12"]) != 12 or not perfect(entry["original12"]):
                raise ValueError("C148 original-12 control failed")
            flat[arm].extend(entry["results"])
        if record["arms"][ARMS[0]]["initial_head_sha256"] != record["arms"][ARMS[1]]["initial_head_sha256"]:
            raise ValueError("C148 initial pairing mismatch")
        if pair(record["arms"][ARMS[0]]["results"], record["arms"][ARMS[1]]["results"], suite) != record["paired"]:
            raise ValueError("C148 per-seed paired accounting mismatch")
    repeated = dict(descriptors=suite["descriptors"], queries=suite["queries"]*12)
    for arm in ARMS:
        m = audit(flat[arm], repeated)
        m.update(full_model_pass_count=sum(perfect(r["arms"][arm]["results"]) for r in records),
                 original12_full_pass_count=12)
        if m != s["arms"][arm]:
            raise ValueError("C148 aggregate mismatch")
    p = pair(flat[ARMS[0]], flat[ARMS[1]], repeated)
    if p != s["paired"] or (p["rescued_errors"],p["new_errors"],p["both_wrong"],p["both_correct"]) != (0,1,11,20724):
        raise ValueError("C148 paired totals mismatch")
    return records


def _load_head(run_dir, seed, arm, entry, vocabulary, device, head_class, fingerprint):
    filename = f"seed-{seed}-{arm.lower()}.pt"
    meta = entry["checkpoint"]
    path = run_dir / filename
    if (meta["path"].replace("\\", "/").rsplit("/",1)[-1] != filename
            or path.resolve().parent != run_dir.resolve()
            or _sha(path) != meta["sha256"] or path.stat().st_size != meta["serialized_bytes"]):
        raise ValueError("Checkpoint byte/path identity mismatch")
    saved = torch.load(path, weights_only=True, map_location="cpu")
    mode = MODES[ARMS.index(arm)]
    if (saved.get("experiment_id") != PRIOR_ID or saved.get("config") != CONFIG
            or tuple(saved.get("vocabulary",())) != tuple(vocabulary)
            or saved.get("training_composition") != mode or saved.get("inference_composition") != MODES[1]):
        raise ValueError("Checkpoint metadata mismatch")
    head = head_class(**CONFIG)
    head.load_state_dict(saved["state_dict"], strict=True)
    if fingerprint(head) != entry["final_head_sha256"]:
        raise ValueError("Checkpoint tensor identity mismatch")
    return head.to(device).eval().requires_grad_(False), path


def _diagnostic_summary(cases: list[dict]) -> dict:
    wrong = [r for r in cases if not r["correct"]]
    return dict(cases=len(cases), errors=len(wrong),
                max_reconstruction_error=max((r["reconstruction_error"] for r in cases), default=0.0),
                error_term_means={k: (sum(r[k] for r in wrong)/len(wrong) if wrong else None) for k in PARTS},
                positive_same_factor_errors=sum(r["same_factor"] > RECONSTRUCTION_ATOL for r in wrong),
                negative_cross_factor_errors=sum(r["cross_factor"] < -RECONSTRUCTION_ATOL for r in wrong),
                negative_candidate_norm_errors=sum(r["candidate_norm"] < -RECONSTRUCTION_ATOL for r in wrong))


def run(*, c148_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    from fold_lm.v05_benchmarks import gate_e_c148_train_consistent_composition as c148
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    try:
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        manifest = c148_summary.parent / "evaluation-manifest.json"
        protected = {c148_summary:PRIOR_SHA, manifest:MANIFEST_SHA, fixture:QUERY_SHA,
            Path("runs/chatgpt-last-result.json"):C37_SHA,
            Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
        def check_files():
            for path, sha in protected.items():
                if _sha(path) != sha:
                    raise ValueError(f"C149 input/protected/checkpoint mismatch: {path}")
        check_files()
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite = json.loads(manifest.read_text(encoding="utf-8"))
        if suite != c143._build_suite(rows):
            raise ValueError("Manifest/generator mismatch")
        prior = json.loads(c148_summary.read_text(encoding="utf-8"))
        records = _validate_prior(prior,suite,c146._audit_results,c146._pair,c148._perfect)
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows,vocabulary):
            raise ValueError("Vocabulary/OOV mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("C149 formal replay requires original CUDA path; no retraining/CPU fallback")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        def features(texts):
            return c139._collision_free_text_features(list(texts),vocabulary,device=device)
        qt, dt = [q["text"] for q in suite["queries"]], suite["descriptors"]
        texts = qt+dt
        batch = c148._prepare(texts,features)
        units = sorted({u for t in texts for u in t.split()})
        positions = {u:i for i,u in enumerate(units)}
        if any(len(t.split()) != 3 for t in texts):
            raise ValueError("This accounting requires the registered three-expression fixture")
        indices = torch.tensor([[positions[u] for u in t.split()] for t in texts])
        expected = [q["expected_address"] for q in suite["queries"]]
        old_indices = [qt.index(r["validation"]) for r in rows]
        started = time.perf_counter()
        for i, source in enumerate(records,1):
            for arm in ARMS:
                entry = source["arms"][arm]
                print(f"[C149] model {i}/12 arm={arm} checkpoint load seed={source['seed']}",flush=True)
                head,path = _load_head(c148_summary.parent,source["seed"],arm,entry,vocabulary,device,
                                       SharedRetrievalContentHead,c148._fingerprint)
                protected[path] = entry["checkpoint"]["sha256"]
                frozen = c148._fingerprint(head)
                actual = []
                with torch.inference_mode():
                    enc = c148._encode(head,batch,c148.EVAL_MODE)
                    eq,ed = enc[:1728],enc[1728:]
                    for start in range(0,1728,216):
                        result = c147._rank(eq[start:start+216] @ ed.T,expected[start:start+216])
                        c147._replay(result,entry["results"][start:start+216])
                        actual.extend(result)
                    old = c147._rank(eq[old_indices] @ ed[:12].T,list(range(12)))
                    c147._replay(old,entry["original12"])
                    # Same float32 encoder, then double-precision bookkeeping only.
                    uv = head.encode(features(units)).detach().cpu()
                ordered = uv[indices]
                qa,da = ordered[:1728],ordered[1728:]
                decomp = _decompose(qa,da[expected],da[[r["best_other_address"] for r in actual]])
                audited = []
                errors = []
                for j,(q,r) in enumerate(zip(suite["queries"],actual,strict=True)):
                    d = {key:float(decomp[key][j]) for key in PARTS+("reconstructed_margin",)}
                    drift = abs(d["reconstructed_margin"]-r["expected_margin"])
                    if drift > RECONSTRUCTION_ATOL:
                        raise ValueError("Float64 accounting does not reconstruct original float32 margin")
                    case = dict(case_id=q["case_id"],bucket=q["bucket"],correct=r["correct"],
                        predicted_address=r["predicted_address"],best_other_address=r["best_other_address"],
                        expected_margin=r["expected_margin"],reconstruction_error=drift,**d)
                    audited.append(case)
                    if not r["correct"]:
                        errors.append(dict(**case,text=q["text"],expected=dt[q["expected_address"]],
                            selected=dt[r["predicted_address"]],
                            query_units=q["text"].split(), expected_units=dt[q["expected_address"]].split(),
                            rival_units=dt[r["best_other_address"]].split(),
                            **{key:decomp[key][j].tolist() for key in
                               ("query_sum_norm","expected_sum_norm","rival_sum_norm",
                                "expected_unit_dot_matrix","rival_unit_dot_matrix")}))
                if c148._fingerprint(head) != frozen or suite != json.loads(manifest.read_text(encoding="utf-8")):
                    raise ValueError("Model/manifest mutated during accounting")
                completed.append(dict(seed=source["seed"],arm=arm,cases=audited,error_details=errors,
                    source_singleton_fit=entry["training"]["training_alignment_accuracy"],
                    checkpoint_sha256=protected[path],frozen_head_sha256=frozen,
                    accounting=_diagnostic_summary(audited)))
                print(f"[C149] model {i}/12 arm={arm} replay_match=True accounted=1728/1728 "
                      f"errors={len(errors)} max_residual={max(r['reconstruction_error'] for r in audited):.3g} "
                      f"remaining_heads={24-len(completed)}",flush=True)
                del head,enc,eq,ed
        check_files()
        arms = {arm:_diagnostic_summary([c for r in completed if r["arm"]==arm for c in r["cases"]]) for arm in ARMS}
        if (arms[ARMS[0]]["errors"],arms[ARMS[1]]["errors"]) != (11,12):
            raise ValueError("Wrong source residual coverage")
        compact_errors = [dict(seed=r["seed"],arm=r["arm"],**{k:e[k] for k in
                          ("text","expected","selected","expected_margin")+PARTS})
                          for r in completed for e in r["error_details"]]
        report = dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS",diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C148_summary_sha256=PRIOR_SHA,evaluation_manifest_sha256=MANIFEST_SHA,
            input_sha256={str(p):h for p,h in protected.items()},
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,device=torch.cuda.get_device_name(0)),
            summary=dict(analysis_only=True,loaded_checkpoints=24,fresh_seed_count=0,additional_training_steps=0,
                scoring_rule_changed=False,runtime_path_exercised=False,full_replay_cases=41472,original12_replay_cases=288,
                full_replay_match_rate=1.0,frozen_weights_preserved_rate=1.0,accounting_complete=True,
                reconstruction_atol=RECONSTRUCTION_ATOL,arms=arms,residual_case_details=compact_errors,
                source_paired=prior["summary"]["paired"],wall_clock_seconds=time.perf_counter()-started),
            records=completed,limitations=[
                "PASS means complete numerical accounting, not better model accuracy or Gate E success",
                "Same-factor/cross-factor labels use known fixture positions after ranking, not learned factorization",
                "Symmetric norm attribution is one exact algebraic convention, not unique causal identification",
                "No term is removed and no alternative score or model is selected",
                "Frozen float32 unit vectors are accumulated in float64 for accounting, not re-encoded in float64",
                "All 24 models and all queries are included; residual rows are not independent tasks",
                "Named attribute-loss and train-consistency sweeps remain closed; no automatic follow-on patch"])
        temp = output_dir/"summary.partial.json"
        temp.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        temp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_heads=len(completed)),indent=2),encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="C149 frozen margin accounting; no intervention")
    parser.add_argument("--c148-summary",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args = parser.parse_args()
    print(f"C149 prerequisite_summary = {args.c148_summary}",flush=True)
    print("C149 analysis_only=True; checkpoints=24; fresh_seeds=0; training_steps=0; scorer_changed=False",flush=True)
    report = run(c148_summary=args.c148_summary,output_dir=args.output_dir)
    print("=== C149 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
