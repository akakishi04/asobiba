"""C148: paired training-path alignment, with a common encode-then-pool evaluator.

Only main-task training composition differs. The existing three supervised
alignment terms remain unchanged. No inference dictionary, new labels, typed
slots, production changes, or checkpoint continuation is introduced.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import torch
from torch.nn import functional as F

EXPERIMENT_ID = "C148-v5e-train-consistent-composition"
STAGE = "V5-E-TRAIN-CONSISTENT-COMPOSITION"
SEEDS = tuple(range(20261681, 20261693))
ARMS = ("POOLED_TRAIN", "COMPOSED_TRAIN")
EVAL_MODE = "ENCODE_THEN_POOL"
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
STEPS, LR, SCALE = 600, 0.002, 12.0
C147_ID = "C147-v5e-frozen-composition-order"
C147_COMMIT = "beae04e34ec9298453953f6535de0328ead6be87"
C147_SHA = "c26700ba28b1616599617c73f36330dec5901c0f837744cdd86b4ea4580e632a"
C146_SHA = "693fadc5b4e76ab253d8395f9197b653ff2d6253435830a9165925948d99622b"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
AXES = ("COLOR", "SHAPE", "MATERIAL")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _fingerprint(head) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _units(text: str) -> tuple[str, ...]:
    if not isinstance(text, str) or not text.split():
        raise ValueError("Nonempty text required")
    return tuple(sorted(text.split()))  # Preserve multiplicity and hyphens.


@dataclass(frozen=True)
class TextBatch:
    whole_features: torch.Tensor
    unit_features: torch.Tensor
    indices: torch.Tensor
    mask: torch.Tensor


def _prepare(texts: list[str], features) -> TextBatch:
    """Cache input features/indexing only, NEVER parameter-dependent vectors."""
    pieces = [_units(t) for t in texts]
    if not pieces:
        raise ValueError("Nonempty batch required")
    unique = sorted({u for p in pieces for u in p})
    lookup = {u: i for i, u in enumerate(unique)}
    whole, units = features(texts), features(unique)
    if (whole.ndim != 2 or units.ndim != 2 or whole.shape[0] != len(texts)
            or units.shape[0] != len(unique) or whole.shape[1] != units.shape[1]
            or whole.device != units.device or whole.dtype != units.dtype
            or not torch.isfinite(whole).all() or not torch.isfinite(units).all()):
        raise ValueError("Invalid prepared features")
    width = max(map(len, pieces))
    indices = torch.zeros((len(pieces), width), dtype=torch.long, device=units.device)
    mask = torch.zeros((len(pieces), width), dtype=units.dtype, device=units.device)
    for row, p in enumerate(pieces):
        indices[row, :len(p)] = torch.tensor([lookup[u] for u in p], device=units.device)
        mask[row, :len(p)] = 1
    return TextBatch(whole, units, indices, mask)


def _encode(head, batch: TextBatch, mode: str) -> torch.Tensor:
    if mode == "POOL_THEN_ENCODE":
        return head.encode(batch.whole_features)
    if mode != EVAL_MODE:
        raise ValueError("Unregistered composition mode")
    # Do not use C147._compose here: it deliberately disables autograd.
    vectors = head.encode(batch.unit_features)
    pooled = (vectors[batch.indices] * batch.mask.unsqueeze(-1)).sum(dim=1)
    if not torch.isfinite(pooled).all() or (pooled.norm(dim=-1) <= 1e-12).any():
        raise ValueError("Undefined normalized unit sum")
    return F.normalize(pooled, dim=-1)


def _scores(head, queries: TextBatch, descriptors: TextBatch, mode: str) -> torch.Tensor:
    return _encode(head, queries, mode) @ _encode(head, descriptors, mode).T


def _objective(head, main, alignments, *, train_mode: str):
    q, d, labels = main
    ml = F.cross_entropy(_scores(head, q, d, train_mode) * SCALE, labels)
    def ce(axis):
        a, c, y = alignments[axis]
        return F.cross_entropy(head.scores(a, c) * SCALE, y)
    # Same order/arithmetic and singleton supervision as C146 treatment.
    cl, matl, sl = ce("COLOR"), ce("MATERIAL"), ce("SHAPE")
    total = ml + 1.0 * cl + 1.0 * matl + 1.0 * sl
    if not all(torch.isfinite(x).item() for x in (total, ml, cl, matl, sl)):
        raise RuntimeError("Nonfinite C148 objective")
    return total, ml, cl, matl, sl


def _train(head, main, alignments, *, mode: str, steps: int = STEPS, progress=None):
    if type(steps) is not int or steps <= 0:
        raise ValueError("Positive integer step count required")
    opt = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    for step in range(1, steps + 1):
        opt.zero_grad(set_to_none=True)
        values = _objective(head, main, alignments, train_mode=mode)
        values[0].backward()
        opt.step()
        if progress and (step in (1, steps) or step % 200 == 0):
            progress(step, [x.detach().item() for x in values[1:]])
    head.eval()
    with torch.inference_mode():
        values = _objective(head, main, alignments, train_mode=mode)
        fit = {axis: (head.select(a, d) == y).float().mean().item()
               for axis, (a, d, y) in alignments.items()}
    return dict(optimizer_steps=steps, training_composition=mode,
                final_losses=dict(zip(("total", "main", "color", "material", "shape"),
                                      [x.item() for x in values], strict=True)),
                training_alignment_accuracy=fit)


def _perfect(results) -> bool:
    return bool(results) and all(r["correct"] and math.isfinite(r["expected_margin"])
                                and r["expected_margin"] > 0 for r in results)


def _validate_prior(data: dict, suite: dict, audit, paired) -> None:
    s = data.get("summary", {})
    if (data.get("experiment_id") != C147_ID or data.get("commit_sha") != C147_COMMIT
            or data.get("status") != "FAIL" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C146_summary_sha256") != C146_SHA
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA):
        raise ValueError("Expected accepted C147 valid negative")
    required = dict(source_seeds=list(range(20261661, 20261673)), source_arm="ALL_FACTOR_AUX",
                    loaded_checkpoints=12, fresh_seed_count=0, additional_training_steps=0,
                    inference_oracle_used=False, runtime_path_exercised=False,
                    baseline_full_replay_cases=20736, treatment_full_ranking_cases=20736,
                    original12_replay_cases=144, original12_treatment_cases=144,
                    full_replay_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                    composition_order_gate_passed=False)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C147 configuration/control mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != required["source_seeds"]:
        raise ValueError("Full ordered C147 records required")
    modes = ("POOL_THEN_ENCODE", EVAL_MODE)
    expected_errors = {modes[0]: [0,0,0,2,1,7,0,0,0,0,1,0], modes[1]: [0,0,0,0,0,4,0,0,0,0,0,0]}
    expected_masks = {modes[0]: {"COLOR":5,"MATERIAL":5,"SHAPE":1}, modes[1]: {"COLOR":4}}
    old_suite = dict(descriptors=suite["descriptors"][:12], queries=[dict(expected_address=i) for i in range(12)])
    for i, record in enumerate(records):
        if record.get("source_training_alignment_accuracy") != dict.fromkeys(AXES, 1.0):
            raise ValueError("C147 source singleton-fit evidence mismatch")
        for mode in modes:
            entry = record["modes"][mode]
            if len(entry["results"]) != 1728 or len(entry["original12"]) != 12:
                raise ValueError("C147 per-model coverage mismatch")
            m = audit(entry["results"], suite)
            if m != entry["metrics"] or m["errors"] != expected_errors[mode][i]:
                raise ValueError("C147 per-model accounting mismatch")
            audit(entry["original12"], old_suite)
            if not _perfect(entry["original12"]):
                raise ValueError("C147 original-12 control mismatch")
        if paired(record["modes"][modes[0]]["results"], record["modes"][modes[1]]["results"]) != record["paired"]:
            raise ValueError("C147 per-model pair mismatch")
    repeated = dict(descriptors=suite["descriptors"], queries=suite["queries"] * 12)
    flat = {}
    for mode in modes:
        flat[mode] = [r for entry in records for r in entry["modes"][mode]["results"]]
        m = audit(flat[mode], repeated)
        m.update(full_model_pass_count=sum(_perfect(r["modes"][mode]["results"]) for r in records),
                 original12_full_pass_count=12)
        if m != s["modes"][mode] or m["mismatch_masks"] != expected_masks[mode]:
            raise ValueError("C147 aggregate mismatch")
    pairs = paired(flat[modes[0]], flat[modes[1]])
    if pairs != s["paired"] or pairs != dict(rescued_errors=10,new_errors=3,both_correct=20722,both_wrong=1):
        raise ValueError("C147 paired aggregate mismatch")


def _save_head(path, head, vocabulary, train_mode):
    torch.save(dict(state_dict={k:v.detach().cpu().clone() for k,v in head.state_dict().items()},
                    config=CONFIG, vocabulary=list(vocabulary), training_composition=train_mode,
                    inference_composition=EVAL_MODE, experiment_id=EXPERIMENT_ID), path)
    return dict(path=str(path), sha256=_sha(path), serialized_bytes=path.stat().st_size)


def run(*, c147_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    try:
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        protected = {c147_summary:C147_SHA, fixture:QUERY_SHA,
                     Path("runs/chatgpt-last-result.json"):C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
        def check_files():
            for path, expected in protected.items():
                if _sha(path) != expected:
                    raise RuntimeError(f"C148 input/protected identity mismatch: {path}")
        check_files()
        if c146.CONFIG != CONFIG or (c146.STEPS,c146.LR,c146.SCALE) != (STEPS,LR,SCALE):
            raise RuntimeError("Reference training configuration drift")
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite = c143._build_suite(rows)
        manifest_bytes = c146._manifest_bytes(suite)
        _validate_prior(json.loads(c147_summary.read_text(encoding="utf-8")),suite,c146._audit_results,c147._paired)
        manifest = output_dir / "evaluation-manifest.json"
        manifest.write_bytes(manifest_bytes)
        protected[manifest] = MANIFEST_SHA
        main_spec, alignment_specs = c146._training_specs(rows)
        if (len(main_spec[0]),len(main_spec[1])) != (24,8) or any((len(a),len(d)) != (12,4) for a,d,_ in alignment_specs.values()):
            raise RuntimeError("Training supervision coverage mismatch")
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows,vocabulary):
            raise RuntimeError("Vocabulary/OOV mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("Formal C148 run requires CUDA; no CPU fallback")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        def features(texts):
            return c139._collision_free_text_features(list(texts),vocabulary,device=device)
        main = (_prepare(list(main_spec[0]),features), _prepare(list(main_spec[1]),features),
                torch.tensor(main_spec[2],dtype=torch.long,device=device))
        alignments = {axis:(features(a),features(d),torch.tensor(y,dtype=torch.long,device=device))
                      for axis,(a,d,y) in alignment_specs.items()}
        qtexts = [q["text"] for q in suite["queries"]]
        dtexts = suite["descriptors"]
        full_batch = _prepare(qtexts+dtexts,features)
        labels = [q["expected_address"] for q in suite["queries"]]
        old_indices = [qtexts.index(r["validation"]) for r in rows]
        input_state = copy.deepcopy((rows,suite))
        started = time.perf_counter()
        for index,seed in enumerate(SEEDS,1):
            torch.manual_seed(seed+13900)
            prototype = SharedRetrievalContentHead(**CONFIG).to(device)
            heads = {arm:copy.deepcopy(prototype) for arm in ARMS}
            initial = _fingerprint(prototype)
            if any(_fingerprint(h) != initial for h in heads.values()):
                raise RuntimeError("Paired initial weights differ")
            del prototype
            print(f"[C148] seed {index}/12 paired_initial_weights_equal=True seed={seed}",flush=True)
            entries = {}
            for arm,train_mode in zip(ARMS,("POOL_THEN_ENCODE",EVAL_MODE),strict=True):
                head = heads[arm]
                def progress(step,vals):
                    print(f"[C148] seed {index}/12 arm={arm} train {step}/600 main={vals[0]:.8f} "
                          f"color={vals[1]:.8f} material={vals[2]:.8f} shape={vals[3]:.8f}",flush=True)
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                start = time.perf_counter()
                training = _train(head,main,alignments,mode=train_mode,progress=progress)
                torch.cuda.synchronize()
                training.update(wall_clock_seconds=time.perf_counter()-start,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
                frozen = _fingerprint(head)
                with torch.inference_mode():
                    encoded = _encode(head,full_batch,EVAL_MODE)
                reference,cost = c147._compose(head,qtexts+dtexts,features)
                if not torch.allclose(encoded,reference,atol=1e-6,rtol=0):
                    raise RuntimeError("Differentiable evaluator differs from C147 composition rule")
                eq,ed = encoded[:1728],encoded[1728:]
                results = []
                with torch.inference_mode():
                    for offset in range(0,1728,216):
                        results.extend(c147._rank(eq[offset:offset+216] @ ed.T,labels[offset:offset+216]))
                        print(f"[C148] seed {index}/12 arm={arm} eval={EVAL_MODE} audited={offset+216}/1728 "
                              f"correct={sum(r['correct'] for r in results)} remaining={1512-offset}",flush=True)
                    old = c147._rank(eq[old_indices] @ ed[:12].T,list(range(12)))
                metrics = c146._audit_results(results,suite)
                if _fingerprint(head) != frozen or (rows,suite) != input_state:
                    raise RuntimeError("Evaluation mutated weights/inputs")
                entries[arm] = dict(training=training,initial_head_sha256=initial,final_head_sha256=frozen,
                    evaluation_composition=EVAL_MODE,composition_reference_match=True,composition_accounting=cost,
                    metrics=metrics,results=results,original12=old,original12_all_pass=_perfect(old),
                    parameter_count=sum(p.numel() for p in head.parameters()),
                    checkpoint=_save_head(output_dir/f"seed-{seed}-{arm.lower()}.pt",head,vocabulary,train_mode))
            pairs = c146._pair(entries[ARMS[0]]["results"],entries[ARMS[1]]["results"],suite)
            completed.append(dict(seed=seed,arms=entries,paired=pairs))
            print(f"[C148] seed {index}/12 complete control_errors={entries[ARMS[0]]['metrics']['errors']} "
                  f"matched_errors={entries[ARMS[1]]['metrics']['errors']} rescued={pairs['rescued_errors']} "
                  f"new_errors={pairs['new_errors']} remaining_seeds={12-index}",flush=True)
            del heads,head,encoded,reference,eq,ed
        check_files()
        repeated = dict(descriptors=dtexts,queries=suite["queries"]*12)
        arms = {}
        for arm in ARMS:
            flat = [v for r in completed for v in r["arms"][arm]["results"]]
            arms[arm] = c146._audit_results(flat,repeated)
            arms[arm].update(full_model_pass_count=sum(_perfect(r["arms"][arm]["results"]) for r in completed),
                             original12_full_pass_count=sum(r["arms"][arm]["original12_all_pass"] for r in completed))
        pairs = c146._pair([v for r in completed for v in r["arms"][ARMS[0]]["results"]],
                           [v for r in completed for v in r["arms"][ARMS[1]]["results"]],repeated)
        passed = arms[ARMS[1]]["full_model_pass_count"] == 12 and arms[ARMS[1]]["original12_full_pass_count"] == 12
        report = dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C147_summary_sha256=C147_SHA,evaluation_manifest_sha256=MANIFEST_SHA,
            input_sha256={str(p):h for p,h in protected.items()},
            environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,device=torch.cuda.get_device_name(0),precision="float32/highest"),
            summary=dict(fresh_seeds=list(SEEDS),paired_heads=24,**CONFIG,train_steps=STEPS,learning_rate=LR,logit_scale=SCALE,
                color_weight=1.0,material_weight=1.0,shape_weight=1.0,training_main_queries=24,training_main_candidates=8,
                auxiliary_aliases_per_factor=12,auxiliary_candidates_per_factor=4,full_candidate_count=64,queries_per_model=1728,
                full_cases_per_arm=20736,original12_cases_per_arm=144,evaluation_composition=EVAL_MODE,
                changed_variable="main-task training composition only",paired_initialization_verified=True,
                evaluation_weights_preserved=True,evaluation_oov_count=0,inference_oracle_used=False,runtime_path_exercised=False,
                composition_reference_match_rate=1.0,baseline_error_contrast_available=arms[ARMS[0]]["errors"]>0,
                arms=arms,paired=pairs,train_consistent_composition_gate_passed=passed,wall_clock_seconds=time.perf_counter()-started),
            records=completed,limitations=[
                "Main-task training graph differs; all three existing explicit attribute supervision terms are retained",
                "Both arms use the same encode-then-pool evaluator; no inference-time replacement comparison here",
                "Fresh seeds reuse the same repeatedly inspected synthetic development task, not an independent task test",
                "Whitespace boundaries align with factor expressions; no learned segmentation or typed inference slots",
                "Equal optimizer steps/parameters do not imply equal compute; both heads reside during timing/VRAM accounting",
                "No detached or cross-step learned-vector cache during training; only input features/indexing are cached",
                "PASS is task-scoped sufficiency; if control is perfect it does not establish improvement",
                "All evaluation is ranking-only, including original12; no production or Gate E promotion",
                "No coefficient/step/width sweep or selection of favorable seeds after this result"])
        tmp = output_dir / "summary.partial.json"
        tmp.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        tmp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_seeds=len(completed)),indent=2),encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="C148 paired training/evaluation composition consistency")
    parser.add_argument("--c147-summary",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args = parser.parse_args()
    print(f"C148 prerequisite_summary = {args.c147_summary}",flush=True)
    print("C148 fresh_seeds = 20261681..20261692; paired_heads = 24",flush=True)
    print("C148 changed = main training composition; both arms evaluate ENCODE_THEN_POOL",flush=True)
    print("C148 additional_attribute_losses = 0; optimizer_steps_per_arm = 600; inference_oracle = False",flush=True)
    print("C148 full_rankings = 41472; original12_rankings = 288; runtime_path_exercised = False",flush=True)
    report = run(c147_summary=args.c147_summary,output_dir=args.output_dir)
    print("=== C148 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
