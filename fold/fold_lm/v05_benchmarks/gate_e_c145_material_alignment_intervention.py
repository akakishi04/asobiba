"""C145: paired fresh-seed material-alignment intervention after C144 attribution.

Changed variable: add material alias->canonical alignment loss on top of the
already accepted color-alignment training objective. Full-factorial evaluation
is ranking-only; no expanded persisted retrieval/runtime path is exercised.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead

EXPERIMENT_ID = "C145-v5e-material-alignment-intervention"
STAGE = "V5-E-MATERIAL-ALIGNMENT-INTERVENTION"
SEEDS = tuple(range(20261641, 20261653))
ARMS = ("COLOR_AUX", "COLOR_MATERIAL_AUX")
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
TRAIN_STEPS = 600
LR = 0.002
LOGIT_SCALE = 12.0
COLOR_WEIGHT = 1.0
MATERIAL_WEIGHT = 1.0
C144_ID = "C144-v5e-factor-mismatch-attribution"
C143_SHA = "4cbde8894639e37e640853e2cc6a1df9ac4f78b6ae41d17a1fed80512d109bca"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
QUERY_FIXTURE_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _head_sha(head) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class AlignmentSpec:
    aliases: tuple[str, ...]
    canonicals: tuple[str, ...]
    targets: tuple[int, ...]


def _alignment_spec(rows: list[dict], axis: int) -> AlignmentSpec:
    if axis not in (0, 1, 2):
        raise ValueError("axis must be color/shape/material")
    mapping: dict[str, str] = {}
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        descriptor = row["descriptor"].split()
        if len(descriptor) != 3:
            raise ValueError("Expected three-factor training descriptor")
        canonical = descriptor[axis]
        for text in row["train"]:
            aliases = text.split()
            if len(aliases) != 3:
                raise ValueError("Expected three-factor training query")
            alias = aliases[axis]
            if alias in mapping and mapping[alias] != canonical:
                raise ValueError("Ambiguous factor alias")
            mapping[alias] = canonical
    aliases = tuple(sorted(mapping))
    canonicals = tuple(sorted(set(mapping.values())))
    if len(aliases) != 12 or len(canonicals) != 4:
        raise ValueError("C145 requires 12 aliases and 4 values per factor")
    return AlignmentSpec(aliases, canonicals, tuple(canonicals.index(mapping[a]) for a in aliases))


def _main_spec(rows: list[dict]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[int, ...]]:
    queries, descriptors, targets = [], [], []
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        address = len(descriptors)
        descriptors.append(row["descriptor"])
        for text in row["train"]:
            queries.append(text)
            targets.append(address)
    if (len(queries), len(descriptors), len(targets)) != (24, 8, 24):
        raise ValueError("C145 main training split mismatch")
    return tuple(queries), tuple(descriptors), tuple(targets)


def _validate_c144(data: dict) -> None:
    s = data.get("summary", {})
    if (data.get("experiment_id") != C144_ID or data.get("status") != "PASS"
            or data.get("diagnostic_execution_valid") is not True
            or data.get("C143_summary_sha256") != C143_SHA
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA
            or data.get("production_runtime_modified") is not False
            or data.get("gate_e_candidate") is not False
            or s.get("attribution_complete") is not True):
        raise ValueError("C145 requires accepted C144 attribution PASS")
    aux = s.get("color_aux", {})
    if (aux.get("cases"), aux.get("errors")) != (20736, 1525):
        raise ValueError("C144 COLOR_AUX aggregate mismatch")
    masks = aux.get("mismatch_masks", {})
    expected = {"COLOR":152,"COLOR+MATERIAL":147,"COLOR+SHAPE":36,"COLOR+SHAPE+MATERIAL":38,
                "MATERIAL":679,"SHAPE":305,"SHAPE+MATERIAL":168}
    if masks != expected:
        raise ValueError("C144 mismatch-mask profile changed")
    transitions = s.get("paired_transitions", {})
    if transitions != {"BOTH_CORRECT":17070,"RESCUED":2141,"BOTH_WRONG":1417,"REGRESSION":108}:
        raise ValueError("C144 paired-transition profile changed")


def _objective(head, main, color, material, *, material_weight: float):
    q, d, targets = main
    main_loss = F.cross_entropy(head.scores(q, d) * LOGIT_SCALE, targets)
    ca, cc, ct = color
    color_loss = F.cross_entropy(head.scores(ca, cc) * LOGIT_SCALE, ct)
    ma, mc, mt = material
    material_loss = F.cross_entropy(head.scores(ma, mc) * LOGIT_SCALE, mt)
    total = main_loss + COLOR_WEIGHT * color_loss + material_weight * material_loss
    if not torch.isfinite(total):
        raise RuntimeError("C145 non-finite loss")
    return total, main_loss, color_loss, material_loss


def _train(head, main, color, material, *, material_weight: float, progress=None) -> dict:
    opt = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    for step in range(1, TRAIN_STEPS + 1):
        opt.zero_grad(set_to_none=True)
        total, main_loss, color_loss, material_loss = _objective(
            head, main, color, material, material_weight=material_weight)
        total.backward()
        opt.step()
        if progress and (step == 1 or step == TRAIN_STEPS or step % 200 == 0):
            progress(step, float(main_loss.detach()), float(color_loss.detach()), float(material_loss.detach()))
    head.eval()
    with torch.inference_mode():
        total, main_loss, color_loss, material_loss = _objective(
            head, main, color, material, material_weight=material_weight)
        color_acc = (head.select(color[0], color[1]) == color[2]).float().mean().item()
        material_acc = (head.select(material[0], material[1]) == material[2]).float().mean().item()
    return dict(final_total_loss=float(total), final_main_loss=float(main_loss),
                final_color_loss=float(color_loss), final_material_loss=float(material_loss),
                color_alignment_accuracy=color_acc, material_alignment_accuracy=material_acc,
                optimizer_steps=TRAIN_STEPS)


def _score(head, q_features, d_features, expected: list[int]) -> list[dict]:
    with torch.inference_mode():
        scores = head.scores(q_features, d_features)
    if scores.shape != (len(expected), len(d_features)) or not torch.isfinite(scores).all():
        raise RuntimeError("Invalid C145 score matrix")
    labels = torch.tensor(expected, device=scores.device)
    pred = scores.argmax(-1)
    right = scores[torch.arange(len(labels), device=scores.device), labels]
    rivals = scores.clone()
    rivals[torch.arange(len(labels), device=scores.device), labels] = -torch.inf
    other, other_idx = rivals.max(-1)
    return [dict(predicted_address=int(p), correct=int(p)==int(e), expected_score=float(rs),
                 best_other_address=int(oi), best_other_score=float(os), expected_margin=float(rs-os))
            for p,e,rs,oi,os in zip(pred.tolist(), labels.tolist(), right.tolist(), other_idx.tolist(), other.tolist(), strict=True)]


def _mask(expected: str, predicted: str) -> str:
    axes = ("COLOR", "SHAPE", "MATERIAL")
    e, p = expected.split(), predicted.split()
    changed = [a for a,x,y in zip(axes,e,p,strict=True) if x != y]
    if not changed:
        raise ValueError("Incorrect result cannot have identical descriptor")
    return "+".join(changed)


def _metrics(suite: dict, results: list[dict]) -> dict:
    descriptors = suite["descriptors"]
    masks = Counter()
    material_involved = 0
    groups = {}
    for q, r in zip(suite["queries"], results, strict=True):
        if not r["correct"]:
            mask = _mask(descriptors[q["expected_address"]], descriptors[r["predicted_address"]])
            masks[mask] += 1
            material_involved += int("MATERIAL" in mask)
    for bucket in ("TRAIN_COMBINATION","PRIOR_HELDOUT_COMBINATION","NEW_COMBINATION"):
        subset = [r for q,r in zip(suite["queries"], results, strict=True) if q["bucket"] == bucket]
        groups[bucket] = dict(cases=len(subset), correct=sum(x["correct"] for x in subset),
                              accuracy=sum(x["correct"] for x in subset)/len(subset),
                              min_expected_margin=min(x["expected_margin"] for x in subset))
    errors = sum(not r["correct"] for r in results)
    return dict(cases=len(results), correct=len(results)-errors, errors=errors,
                accuracy=(len(results)-errors)/len(results),
                positive_margin_count=sum(r["expected_margin"] > 0 for r in results),
                min_expected_margin=min(r["expected_margin"] for r in results),
                material_involved_errors=material_involved, mismatch_masks=dict(sorted(masks.items())),
                groups=groups)


def _pair(control: list[dict], treatment: list[dict], suite: dict) -> dict:
    descriptors = suite["descriptors"]
    rescued = new_errors = material_rescued = material_regressions = 0
    for q, c, t in zip(suite["queries"], control, treatment, strict=True):
        if not c["correct"] and t["correct"]:
            rescued += 1
            mask = _mask(descriptors[q["expected_address"]], descriptors[c["predicted_address"]])
            material_rescued += int("MATERIAL" in mask)
        elif c["correct"] and not t["correct"]:
            new_errors += 1
            mask = _mask(descriptors[q["expected_address"]], descriptors[t["predicted_address"]])
            material_regressions += int("MATERIAL" in mask)
    return dict(rescued_errors=rescued, new_errors=new_errors,
                material_related_rescues=material_rescued,
                material_related_regressions=material_regressions)


def _save_head(path: Path, head, vocabulary: tuple[str, ...]) -> dict:
    payload = dict(state_dict={k:v.detach().cpu().clone() for k,v in head.state_dict().items()},
                   vocabulary=list(vocabulary), config=CONFIG)
    torch.save(payload, path)
    return dict(path=str(path), sha256=_sha(path), serialized_bytes=path.stat().st_size)


def run(*, c144_result_path: Path, output_dir: Path, protected_result_path: Path,
        protected_fixture_path: Path) -> dict:
    from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143

    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        c144 = json.loads(c144_result_path.read_text(encoding="utf-8"))
        _validate_c144(c144)
        fixture = Path(__file__).parent / "fixtures" / "c138_compositional_alias_queries.json"
        required = {c144_result_path:_sha(c144_result_path), protected_result_path:C37_SHA,
                    protected_fixture_path:FIXTURE_SHA, fixture:QUERY_FIXTURE_SHA}
        def check_files():
            for path, expected in required.items():
                if _sha(path) != expected:
                    raise RuntimeError(f"C145 input/protected hash mismatch: {path}")
        check_files()
        if not torch.cuda.is_available():
            raise RuntimeError("C145 requires CUDA")
        rows = c138._load_fixture()
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary):
            raise RuntimeError("C145 vocabulary/OOV mismatch")
        suite = c143._build_suite(rows)
        device = torch.device("cuda")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        def features(texts):
            return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        main_q, main_d, main_t = _main_spec(rows)
        main = (features(main_q), features(main_d), torch.tensor(main_t, device=device))
        color_spec = _alignment_spec(rows, 0)
        material_spec = _alignment_spec(rows, 2)
        color = (features(color_spec.aliases), features(color_spec.canonicals), torch.tensor(color_spec.targets, device=device))
        material = (features(material_spec.aliases), features(material_spec.canonicals), torch.tensor(material_spec.targets, device=device))
        full_queries = features([q["text"] for q in suite["queries"]])
        full_desc = features(suite["descriptors"])
        full_expected = [q["expected_address"] for q in suite["queries"]]
        old_queries = features([r["validation"] for r in rows])
        old_desc = features([r["descriptor"] for r in rows])
        started = time.perf_counter()
        for seed_index, seed in enumerate(SEEDS, 1):
            torch.manual_seed(seed + 13900)
            prototype = SharedRetrievalContentHead(**CONFIG).to(device)
            heads = {arm:copy.deepcopy(prototype) for arm in ARMS}
            initial = _head_sha(prototype)
            if any(_head_sha(h) != initial for h in heads.values()):
                raise RuntimeError("C145 paired initialization mismatch")
            del prototype
            print(f"[C145] seed {seed_index}/12 paired_initial_weights_equal=True seed={seed}", flush=True)
            arm_records = {}
            for arm, material_weight in (("COLOR_AUX",0.0),("COLOR_MATERIAL_AUX",MATERIAL_WEIGHT)):
                head = heads[arm]
                print(f"[C145] seed {seed_index}/12 arm={arm} train start", flush=True)
                def progress(step, ml, cl, matl):
                    print(f"[C145] seed {seed_index}/12 arm={arm} train {step}/600 main={ml:.8f} color={cl:.8f} material={matl:.8f}", flush=True)
                train = _train(head, main, color, material, material_weight=material_weight, progress=progress)
                frozen = _head_sha(head)
                old = _score(head, old_queries, old_desc, list(range(12)))
                full = []
                for start in range(0, 1728, 216):
                    stop = start + 216
                    full.extend(_score(head, full_queries[start:stop], full_desc, full_expected[start:stop]))
                    print(f"[C145] seed {seed_index}/12 arm={arm} audited={stop}/1728 correct={sum(r['correct'] for r in full)} remaining={1728-stop}", flush=True)
                if _head_sha(head) != frozen:
                    raise RuntimeError("C145 evaluation mutated head")
                arm_records[arm] = dict(training=train, initial_head_sha256=initial,
                                        final_head_sha256=frozen, original12=old,
                                        original12_all_pass=all(r["correct"] and r["expected_margin"] > 0 for r in old),
                                        metrics=_metrics(suite, full), results=full,
                                        checkpoint=_save_head(output_dir/f"seed-{seed}-{arm.lower()}.pt", head, vocabulary),
                                        parameter_count=sum(p.numel() for p in head.parameters()))
            paired = _pair(arm_records["COLOR_AUX"]["results"], arm_records["COLOR_MATERIAL_AUX"]["results"], suite)
            records.append(dict(seed=seed, arms=arm_records, paired=paired))
            print(f"[C145] seed {seed_index}/12 complete control_errors={arm_records['COLOR_AUX']['metrics']['errors']} treatment_errors={arm_records['COLOR_MATERIAL_AUX']['metrics']['errors']} material_treatment_errors={arm_records['COLOR_MATERIAL_AUX']['metrics']['material_involved_errors']} rescued={paired['rescued_errors']} new_errors={paired['new_errors']} remaining_seeds={12-seed_index}", flush=True)
            del heads, head
        check_files()
        summary_arms = {}
        for arm in ARMS:
            ms = [r["arms"][arm]["metrics"] for r in records]
            summary_arms[arm] = dict(cases=sum(m["cases"] for m in ms), correct=sum(m["correct"] for m in ms),
                                     errors=sum(m["errors"] for m in ms),
                                     accuracy=sum(m["correct"] for m in ms)/sum(m["cases"] for m in ms),
                                     material_involved_errors=sum(m["material_involved_errors"] for m in ms),
                                     min_expected_margin=min(m["min_expected_margin"] for m in ms),
                                     full_model_pass_count=sum(r["arms"][arm]["metrics"]["errors"]==0 for r in records),
                                     original12_full_pass_count=sum(r["arms"][arm]["original12_all_pass"] for r in records),
                                     mismatch_masks=dict(sorted(sum((Counter(m["mismatch_masks"]) for m in ms), Counter()).items())))
        paired = {k:sum(r["paired"][k] for r in records) for k in records[0]["paired"]}
        control_material = summary_arms["COLOR_AUX"]["material_involved_errors"]
        treatment_material = summary_arms["COLOR_MATERIAL_AUX"]["material_involved_errors"]
        passed = bool(control_material > 0 and treatment_material == 0 and paired["new_errors"] == 0
                      and summary_arms["COLOR_MATERIAL_AUX"]["original12_full_pass_count"] == 12)
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip(),
                      C144_result_sha256=required[c144_result_path],
                      input_sha256={str(p):h for p,h in required.items()},
                      environment=dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                                       device=torch.cuda.get_device_name(0), precision="float32/highest"),
                      summary=dict(fresh_seeds=list(SEEDS), unique_fresh_seed_count=12,
                                   paired_heads=24, feature_dim=49, hidden_dim=64, residual_scale=1.0,
                                   train_steps=TRAIN_STEPS, learning_rate=LR, logit_scale=LOGIT_SCALE,
                                   color_weight=COLOR_WEIGHT, material_weight=MATERIAL_WEIGHT,
                                   full_candidate_count=64, queries_per_model=1728,
                                   full_ranking_cases_per_arm=20736, additional_runtime_path=False,
                                   inference_oracle_used=False, arms=summary_arms, paired=paired,
                                   material_alignment_gate_passed=passed,
                                   wall_clock_seconds=time.perf_counter()-started), records=records,
                      limitations=["Material alignment is explicit supervised factor labeling, not unsupervised discovery",
                                   "Primary full-factorial evaluation is ranking-only; no expanded persisted runtime path",
                                   "Fresh seeds reuse the same synthetic factor vocabulary and evaluation generator",
                                   "Treatment adds training computation but no inference parameters",
                                   "PASS would establish sufficiency only for eliminating registered material-involved residuals without paired regressions",
                                   "FAIL may still show partial reduction; do not tune weights or add shape loss under C145",
                                   "Gate E remains NOT PASSED"])
        tmp = output_dir/"summary.partial.json"
        tmp.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_seeds=len(records)), indent=2), encoding="utf-8")
        raise
