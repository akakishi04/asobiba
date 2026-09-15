"""C146: final three-factor supervised reference, not factor discovery.

Only the shape auxiliary coefficient changes between paired training arms.
The original raw-text scorer, vocabulary and evaluation catalog are unchanged.
No production retrieval, evidence commit or ANSWER is exercised here.
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
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead

EXPERIMENT_ID = "C146-v5e-all-factor-supervised-reference"
STAGE = "V5-E-ALL-FACTOR-SUPERVISED-REFERENCE"
SEEDS = tuple(range(20261661, 20261673))
ARMS = ("COLOR_MATERIAL_AUX", "ALL_FACTOR_AUX")
AXES = ("COLOR", "SHAPE", "MATERIAL")
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
STEPS, LR, SCALE = 600, 0.002, 12.0
C145_ID = "C145-v5e-material-alignment-intervention"
C145_COMMIT = "b7d82dad56fb03cd270a62a7e8d01fc014025197"
C144_SHA = "c56823a036f22eae47da953d5ccdd0888eb7697ba9efb8ae41f8114a4ab0fe43"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
PRIOR_MASKS = {
    "COLOR_AUX": {"COLOR":128, "COLOR+MATERIAL":52, "COLOR+SHAPE":16,
                  "COLOR+SHAPE+MATERIAL":33, "MATERIAL":546, "SHAPE":522, "SHAPE+MATERIAL":167},
    "COLOR_MATERIAL_AUX": {"COLOR":21, "COLOR+MATERIAL":1, "COLOR+SHAPE":3,
                           "MATERIAL":15, "SHAPE":294, "SHAPE+MATERIAL":12},
}
PRIOR_PAIRED = dict(rescued_errors=1153, new_errors=35,
                    material_related_rescues=724, material_related_regressions=4)


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


def _manifest_bytes(suite: dict, expected_sha: str = MANIFEST_SHA) -> bytes:
    """Match the accepted manifest bytes, including Windows newline serialization."""
    text = json.dumps(suite, indent=2, allow_nan=False)
    for payload in (text.encode("utf-8"), text.replace("\n", "\r\n").encode("utf-8")):
        if hashlib.sha256(payload).hexdigest() == expected_sha:
            return payload
    raise RuntimeError("C143 evaluation manifest drift")



def _training_specs(rows: list[dict]) -> tuple[tuple, dict[str, tuple]]:
    """Extract all supervision from TRAIN_COMBINATION fields only."""
    texts, desc, targets = [], [], []
    maps = {axis: {} for axis in AXES}
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        canonical = row["descriptor"].split()
        if len(canonical) != 3 or not row["train"]:
            raise ValueError("Three-factor training descriptor/queries required")
        address = len(desc)
        desc.append(row["descriptor"])
        for text in row["train"]:
            aliases = text.split()
            if len(aliases) != 3:
                raise ValueError("Three whitespace-separated alias fields required")
            texts.append(text)
            targets.append(address)
            for axis, alias, value in zip(AXES, aliases, canonical, strict=True):
                if alias in maps[axis] and maps[axis][alias] != value:
                    raise ValueError(f"Conflicting {axis} training alias: {alias}")
                maps[axis][alias] = value
    if not desc:
        raise ValueError("Empty training split")
    alignments = {}
    for axis, mapping in maps.items():
        aliases = tuple(sorted(mapping))
        values = tuple(sorted(set(mapping.values())))
        alignments[axis] = aliases, values, tuple(values.index(mapping[a]) for a in aliases)
    return (tuple(texts), tuple(desc), tuple(targets)), alignments


def _objective(head, main, color, material, shape, *, shape_weight: float):
    if shape_weight not in (0.0, 1.0) or isinstance(shape_weight, bool):
        raise ValueError("Only registered shape weights 0.0 and 1.0 are allowed")
    def ce(data):
        q, d, labels = data
        return F.cross_entropy(head.scores(q, d) * SCALE, labels)
    ml, cl, matl = ce(main), ce(color), ce(material)
    # Exact C145 treatment arithmetic; no shape graph exists in the control.
    total = ml + 1.0 * cl + 1.0 * matl
    sl = total.new_zeros(()) if shape_weight == 0 else ce(shape)
    if shape_weight:
        total = total + shape_weight * sl
    if not all(torch.isfinite(x).item() for x in (total, ml, cl, matl, sl)):
        raise RuntimeError("Non-finite C146 objective")
    return total, ml, cl, matl, sl


def _train(head, main, alignments, *, shape_weight: float, steps: int = STEPS, progress=None):
    if type(steps) is not int or steps <= 0:
        raise ValueError("Positive integer step count required")
    opt = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    def losses():
        return _objective(head, main, alignments["COLOR"], alignments["MATERIAL"],
                          alignments.get("SHAPE"), shape_weight=shape_weight)
    for step in range(1, steps + 1):
        opt.zero_grad(set_to_none=True)
        values = losses()
        values[0].backward()
        opt.step()
        if progress and (step in (1, steps) or step % 200 == 0):
            progress(step, [x.detach().item() for x in values[1:]])
    head.eval()
    with torch.inference_mode():
        values = losses()
        # Training diagnostics only: singleton fit is not compositional generalization.
        fit = {axis: (head.select(a, d) == y).float().mean().item()
               for axis, (a, d, y) in alignments.items()}
    return dict(optimizer_steps=steps, final_losses=dict(zip(
        ("total", "main", "color", "material", "weighted_shape"),
        [x.item() for x in values], strict=True)), training_alignment_accuracy=fit)


def _audit_results(results: list[dict], suite: dict) -> dict:
    """Validate scores/labels and recompute all masks from predictions, not metrics."""
    queries, descriptors = suite["queries"], suite["descriptors"]
    if len(results) != len(queries) or not results or len(set(descriptors)) != len(descriptors):
        raise ValueError("Result/manifest coverage or descriptor identity mismatch")
    masks = Counter()
    for q, r in zip(queries, results, strict=True):
        e, p, rival = q["expected_address"], r["predicted_address"], r["best_other_address"]
        if any(type(i) is not int or not 0 <= i < len(descriptors) for i in (e, p, rival)) or e == rival:
            raise ValueError("Invalid candidate index")
        s, t, margin = (float(r[k]) for k in ("expected_score", "best_other_score", "expected_margin"))
        if not all(math.isfinite(v) for v in (s, t, margin)) or abs((s-t)-margin) > 1e-6:
            raise ValueError("Invalid or inconsistent score margin")
        correct = p == e
        if (r["correct"] is not correct or (correct and margin < 0)
                or (not correct and (p != rival or margin > 0))):
            raise ValueError("Prediction/margin/correctness mismatch")
        if not correct:
            expected, predicted = descriptors[e].split(), descriptors[p].split()
            if len(expected) != 3 or len(predicted) != 3:
                raise ValueError("Three canonical factors required")
            masks["+".join(axis for axis, x, y in zip(AXES, expected, predicted, strict=True) if x != y)] += 1
    errors = sum(masks.values())
    groups = {}
    for name in ("TRAIN_COMBINATION", "PRIOR_HELDOUT_COMBINATION", "NEW_COMBINATION", "ORIGINAL_VALIDATION_IN_64"):
        selected = [r for q, r in zip(queries, results, strict=True)
                    if (q.get("original_validation_query", False) if name == "ORIGINAL_VALIDATION_IN_64"
                        else q.get("bucket") == name)]
        if selected:
            groups[name] = dict(cases=len(selected), correct=sum(r["correct"] for r in selected),
                                accuracy=sum(r["correct"] for r in selected)/len(selected),
                                min_expected_margin=min(r["expected_margin"] for r in selected))
    return dict(cases=len(results), correct=len(results)-errors, errors=errors,
                accuracy=1-errors/len(results), mismatch_masks=dict(sorted(masks.items())),
                factor_involved_errors={a: sum(n for mask, n in masks.items() if a in mask.split("+")) for a in AXES},
                positive_margin_count=sum(r["expected_margin"] > 0 for r in results),
                min_expected_margin=min(r["expected_margin"] for r in results), groups=groups)


def _pair(before: list[dict], after: list[dict], suite: dict) -> dict:
    if len(before) != len(after) or len(before) != len(suite["queries"]):
        raise ValueError("Paired coverage mismatch")
    rescued, new = Counter(), Counter()
    transitions = Counter()
    for q, b, a in zip(suite["queries"], before, after, strict=True):
        state = ("BOTH_CORRECT" if b["correct"] and a["correct"] else
                 "RESCUED" if not b["correct"] and a["correct"] else
                 "NEW_ERROR" if b["correct"] and not a["correct"] else "BOTH_WRONG")
        transitions[state] += 1
        if state in ("RESCUED", "NEW_ERROR"):
            wrong = b if state == "RESCUED" else a
            e = suite["descriptors"][q["expected_address"]].split()
            p = suite["descriptors"][wrong["predicted_address"]].split()
            mask = "+".join(axis for axis, x, y in zip(AXES, e, p, strict=True) if x != y)
            (rescued if state == "RESCUED" else new)[mask] += 1
    return dict(rescued_errors=transitions["RESCUED"], new_errors=transitions["NEW_ERROR"],
                both_correct=transitions["BOTH_CORRECT"], both_wrong=transitions["BOTH_WRONG"],
                rescued_masks=dict(sorted(rescued.items())), regression_masks=dict(sorted(new.items())))


def _perfect(results):
    return bool(results) and all(r["correct"] and math.isfinite(r["expected_margin"])
                                and r["expected_margin"] > 0 for r in results)


def _validate_c145(data: dict, suite: dict) -> None:
    s = data.get("summary", {})
    required = dict(fresh_seeds=list(range(20261641,20261653)), unique_fresh_seed_count=12,
                    paired_heads=24, **CONFIG, train_steps=600, learning_rate=LR, logit_scale=SCALE,
                    color_weight=1.0, material_weight=1.0, full_candidate_count=64, queries_per_model=1728,
                    full_ranking_cases_per_arm=20736, additional_runtime_path=False,
                    inference_oracle_used=False, material_alignment_gate_passed=False)
    if (data.get("experiment_id") != C145_ID or data.get("commit_sha") != C145_COMMIT
            or data.get("status") != "FAIL" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C144_result_sha256") != C144_SHA or any(s.get(k) != v for k,v in required.items())
            or s.get("paired") != PRIOR_PAIRED):
        raise ValueError("Accepted C145 prerequisite identity/configuration mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != required["fresh_seeds"]:
        raise ValueError("Full ordered C145 records required, not console-only summary")
    totals = {arm: Counter() for arm in PRIOR_MASKS}
    paired = Counter()
    full_pass = Counter()
    old_suite = dict(descriptors=suite["descriptors"][:12], queries=[dict(expected_address=i) for i in range(12)])
    for record in records:
        entries = record["arms"]
        if entries["COLOR_AUX"]["initial_head_sha256"] != entries["COLOR_MATERIAL_AUX"]["initial_head_sha256"]:
            raise ValueError("C145 paired initial weights mismatch")
        for arm in PRIOR_MASKS:
            entry = entries[arm]
            if entry["training"]["optimizer_steps"] != 600:
                raise ValueError("C145 training schedule mismatch")
            metrics = _audit_results(entry["results"], suite)
            totals[arm].update(metrics["mismatch_masks"])
            full_pass[arm] += int(metrics["errors"] == 0)
            if metrics["mismatch_masks"] != entry["metrics"]["mismatch_masks"]:
                raise ValueError("C145 per-model error accounting mismatch")
            _audit_results(entry["original12"], old_suite)
            if not _perfect(entry["original12"]) or entry["original12_all_pass"] is not True:
                raise ValueError("C145 original-12 protection profile mismatch")
        p = _pair(entries["COLOR_AUX"]["results"], entries["COLOR_MATERIAL_AUX"]["results"], suite)
        paired.update(dict(rescued_errors=p["rescued_errors"], new_errors=p["new_errors"],
                           material_related_rescues=sum(n for m,n in p["rescued_masks"].items() if "MATERIAL" in m),
                           material_related_regressions=sum(n for m,n in p["regression_masks"].items() if "MATERIAL" in m)))
    for arm, masks in totals.items():
        if dict(masks) != PRIOR_MASKS[arm] or s["arms"][arm]["mismatch_masks"] != dict(masks):
            raise ValueError("C145 aggregate mismatch masks")
        aggregate = s["arms"][arm]
        expected = dict(cases=20736, errors=sum(masks.values()), correct=20736-sum(masks.values()),
                        material_involved_errors=sum(n for mask,n in masks.items() if "MATERIAL" in mask),
                        full_model_pass_count=full_pass[arm], original12_full_pass_count=12)
        if any(aggregate.get(k) != v for k,v in expected.items()):
            raise ValueError("C145 aggregate count mismatch")
    if dict(paired) != PRIOR_PAIRED:
        raise ValueError("C145 full-record paired accounting mismatch")


def run(*, c145_summary_path: Path, output_dir: Path, protected_result_path: Path,
        protected_fixture_path: Path) -> dict:
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c145_material_alignment_intervention as c145
    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        fixture = Path(__file__).parent / "fixtures" / "c138_compositional_alias_queries.json"
        protected = {fixture:QUERY_SHA, protected_result_path:C37_SHA, protected_fixture_path:FIXTURE_SHA,
                     c145_summary_path:_sha(c145_summary_path)}
        def check_files():
            for path, expected in protected.items():
                if _sha(path) != expected:
                    raise RuntimeError(f"C146 input/protected mutation or mismatch: {path}")
        check_files()
        if c145.CONFIG != CONFIG or (c145.TRAIN_STEPS,c145.LR,c145.LOGIT_SCALE) != (STEPS,LR,SCALE):
            raise RuntimeError("C145 reference configuration drift")
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite = c143._build_suite(rows)
        manifest_bytes = _manifest_bytes(suite)
        _validate_c145(json.loads(c145_summary_path.read_text(encoding="utf-8")), suite)
        main_spec, alignment_specs = _training_specs(rows)
        if (len(main_spec[0]),len(main_spec[1])) != (24,8) or any(
                (len(a),len(d)) != (12,4) for a,d,_ in alignment_specs.values()):
            raise RuntimeError("C146 training coverage mismatch")
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary):
            raise RuntimeError("C146 vocabulary/OOV mismatch")
        manifest_path = output_dir / "evaluation-manifest.json"
        manifest_path.write_bytes(manifest_bytes)
        protected[manifest_path] = MANIFEST_SHA
        if not torch.cuda.is_available():
            raise RuntimeError("Formal C146 run requires CUDA; no CPU fallback")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        def features(texts):
            return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        def encode_spec(spec):
            return features(spec[0]), features(spec[1]), torch.tensor(spec[2], dtype=torch.long, device=device)
        main = encode_spec(main_spec)
        alignments = {axis:encode_spec(spec) for axis,spec in alignment_specs.items()}
        full_q = features([q["text"] for q in suite["queries"]])
        full_d = features(suite["descriptors"])
        labels = [q["expected_address"] for q in suite["queries"]]
        old_q = features([row["validation"] for row in rows])
        old_d = features([row["descriptor"] for row in rows])
        input_state = copy.deepcopy((rows, suite))
        started = time.perf_counter()
        for index, seed in enumerate(SEEDS, 1):
            torch.manual_seed(seed + 13900)
            prototype = SharedRetrievalContentHead(**CONFIG).to(device)
            heads = {arm:copy.deepcopy(prototype) for arm in ARMS}
            initial = _fingerprint(prototype)
            if any(_fingerprint(h) != initial for h in heads.values()):
                raise RuntimeError("C146 paired initialization mismatch")
            del prototype
            print(f"[C146] seed {index}/12 paired_initial_weights_equal=True seed={seed}", flush=True)
            entries = {}
            for arm, weight in zip(ARMS, (0.0,1.0), strict=True):
                head = heads[arm]
                def progress(step, vals):
                    print(f"[C146] seed {index}/12 arm={arm} train {step}/600 "
                          f"main={vals[0]:.8f} color={vals[1]:.8f} material={vals[2]:.8f} weighted_shape={vals[3]:.8f}", flush=True)
                torch.cuda.synchronize()
                start = time.perf_counter()
                training = _train(head, main, alignments, shape_weight=weight, progress=progress)
                torch.cuda.synchronize()
                training["wall_clock_seconds"] = time.perf_counter()-start
                frozen = _fingerprint(head)
                old = c143._score(head, old_q, old_d, list(range(12)))
                full = []
                for offset in range(0,1728,216):
                    full.extend(c143._score(head, full_q[offset:offset+216], full_d, labels[offset:offset+216]))
                    print(f"[C146] seed {index}/12 arm={arm} audited={offset+216}/1728 "
                          f"correct={sum(r['correct'] for r in full)} remaining={1512-offset}", flush=True)
                metrics = _audit_results(full, suite)
                if _fingerprint(head) != frozen or (rows,suite) != input_state:
                    raise RuntimeError("C146 evaluation mutated model/manifest")
                entries[arm] = dict(training=training, initial_head_sha256=initial, final_head_sha256=frozen,
                                    parameter_count=sum(p.numel() for p in head.parameters()),
                                    original12=old, original12_all_pass=_perfect(old), metrics=metrics, results=full,
                                    checkpoint=c145._save_head(output_dir/f"seed-{seed}-{arm.lower()}.pt",head,vocabulary))
            paired = _pair(entries[ARMS[0]]["results"],entries[ARMS[1]]["results"],suite)
            records.append(dict(seed=seed, arms=entries, paired=paired))
            print(f"[C146] seed {index}/12 complete control_errors={entries[ARMS[0]]['metrics']['errors']} "
                  f"all_factor_errors={entries[ARMS[1]]['metrics']['errors']} "
                  f"rescued={paired['rescued_errors']} new_errors={paired['new_errors']} remaining_seeds={12-index}",flush=True)
            del heads, head
        check_files()
        arms = {}
        for arm in ARMS:
            all_results = [v for r in records for v in r["arms"][arm]["results"]]
            repeated_suite = dict(descriptors=suite["descriptors"], queries=suite["queries"]*12)
            arms[arm] = _audit_results(all_results,repeated_suite)
            arms[arm]["full_model_pass_count"] = sum(_perfect(r["arms"][arm]["results"]) for r in records)
            arms[arm]["original12_full_pass_count"] = sum(r["arms"][arm]["original12_all_pass"] for r in records)
        paired = {k:sum(r["paired"][k] for r in records) for k in ("rescued_errors","new_errors","both_correct","both_wrong")}
        for k in ("rescued_masks","regression_masks"):
            paired[k] = dict(sorted(sum((Counter(r["paired"][k]) for r in records),Counter()).items()))
        passed = arms[ARMS[1]]["full_model_pass_count"] == 12 and arms[ARMS[1]]["original12_full_pass_count"] == 12
        report = dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
                      C145_summary_sha256=protected[c145_summary_path],evaluation_manifest_sha256=MANIFEST_SHA,
                      input_sha256={str(p):h for p,h in protected.items()},
                      environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,device=torch.cuda.get_device_name(0)),
                      summary=dict(fresh_seeds=list(SEEDS),paired_heads=24,**CONFIG,train_steps=STEPS,learning_rate=LR,
                                   logit_scale=SCALE,color_weight=1.0,material_weight=1.0,shape_weight=1.0,
                                   full_candidate_count=64,queries_per_model=1728,full_cases_per_arm=20736,
                                   original12_cases_per_arm=144,training_main_queries=24,training_main_candidates=8,
                                   auxiliary_aliases_per_factor=12,auxiliary_candidates_per_factor=4,
                                   paired_initialization_verified=True,evaluation_weights_preserved=True,evaluation_oov_count=0,
                                   zero_paired_lexical_overlap=True,inference_oracle_used=False,runtime_path_exercised=False,
                                   baseline_error_contrast_available=arms[ARMS[0]]["errors"]>0,
                                   arms=arms,paired=paired,all_factor_reference_gate_passed=passed,
                                   wall_clock_seconds=time.perf_counter()-started),records=records,
                      limitations=["Final registered three-factor supervised reference, not automatic factor discovery or a theoretical upper bound",
                                   "Same synthetic development fixture and known aliases; fresh seeds are not fresh tasks",
                                   "Shape supervision adds labels and training computation; no inference parameters or oracle added",
                                   "Both original-12 and expanded-64 evaluations are ranking-only, not runtime/ANSWER tests",
                                   "PASS requires exhaustive positive-margin treatment success; control perfection would not prove improvement",
                                   "Do not tune coefficient/steps/width or choose models after seeing this run; Gate E remains NOT PASSED"])
        temporary = output_dir/"summary.partial.json"
        temporary.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        temporary.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_seeds=len(records)),indent=2),encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="C146 paired final all-factor supervised reference")
    parser.add_argument("--c145-summary",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args = parser.parse_args()
    print(f"C146 prerequisite_summary = {args.c145_summary}",flush=True)
    print("C146 changed_variable = shape alignment coefficient 0 -> 1 only",flush=True)
    print("C146 fresh_seeds = 20261661..20261672; paired_heads = 24",flush=True)
    print("C146 full_rankings = 41472; original12_rankings = 288; runtime_path_exercised = False",flush=True)
    report = run(c145_summary_path=args.c145_summary,output_dir=args.output_dir,
                 protected_result_path=Path('runs/chatgpt-last-result.json'),
                 protected_fixture_path=Path('runs/fixtures/v05-c-composition-20260921.pt'))
    shown = dict(report,records="omitted; see summary.json")
    print("=== C146 RESULT ===",flush=True)
    print(json.dumps(shown,indent=2,allow_nan=False),flush=True)
    return 0
