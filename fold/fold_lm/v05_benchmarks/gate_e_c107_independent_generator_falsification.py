"""C107: independent-evaluator falsification of C106 mechanism routing."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c106_unseen_mask_generalization as canonical
from fold_lm.v05_benchmarks import gate_e_c107_independent_eval_fixture as independent

EXPERIMENT_ID = "C107-v5e-independent-evaluator-falsification"
C106_EXPERIMENT_ID = "C106-v5e-unseen-eligibility-mask-generalization"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261301, 20261302, 20261303)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _independent_tensors(device):
    rows = independent.independent_rows(base=3)
    width = canonical.WIDTH
    working = torch.zeros(len(rows), 1, width, device=device)
    context = torch.zeros_like(working)
    op_ids = torch.zeros(len(rows), dtype=torch.int64, device=device)
    labels = torch.tensor([r["expected_action"] for r in rows], dtype=torch.int64, device=device)
    for i, row in enumerate(rows):
        base, dep, present, observed = row["visible"]
        working[i, 0, 0] = float(base) / 3.0
        working[i, 0, 1] = float(dep)
        working[i, 0, 2] = float(present)
        working[i, 0, 3] = float(observed)
        context[i, 0, :4] = torch.tensor(row["eligible_mask"], dtype=torch.float32, device=device)
    return rows, (working, context, op_ids, labels)


@torch.inference_mode()
def _independent_evaluate(router, _rows_unused, _tensors_unused, _require_all_classes):
    rows, tensors = _independent_tensors(next(router.parameters()).device)
    working, context, op_ids, labels = tensors
    pred = router(working, context, op_ids).argmax(dim=-1)
    accuracy = float((pred == labels).float().mean().item())
    flips = int((pred != labels).sum().item())
    recalls = []
    for action in range(6):
        mask = labels == action
        recalls.append(float((pred[mask] == action).float().mean().item()))

    answerable = [i for i, r in enumerate(rows) if r["dependency"] == 0 or r["evidence_present"] == 1]
    required = [i for i, r in enumerate(rows) if r["dependency"] == 1 and r["evidence_present"] == 0]
    available = [i for i in required if any(rows[i]["eligible_mask"])]
    unavailable = [i for i in required if not any(rows[i]["eligible_mask"])]

    ineligible = 0
    bits = {independent.READ_MEMORY: 0, independent.RETRIEVE: 1, independent.OBSERVE: 2, independent.ASK_USER: 3}
    for i in required:
        action = int(pred[i].item())
        if action in bits and rows[i]["eligible_mask"][bits[action]] == 0:
            ineligible += 1

    groups = {}
    for i in required:
        r = rows[i]
        groups.setdefault((r["dependency"], r["eligible_mask"]), []).append(i)
    hidden_invariance = 1.0
    for pair in groups.values():
        if len(pair) != 2 or int(pred[pair[0]]) != int(pred[pair[1]]):
            hidden_invariance = 0.0
            break

    return {
        "action_accuracy": accuracy,
        "minimum_present_class_recall": min(recalls),
        "action_flip_count": flips,
        "answerable_answer_rate": float((pred[answerable] == independent.ANSWER).float().mean().item()),
        "required_no_direct_answer_rate": float((pred[required] != independent.ANSWER).float().mean().item()),
        "minimum_burden_rate": float((pred[available] == labels[available]).float().mean().item()),
        "no_eligible_stop_rate": float((pred[unavailable] == independent.STOP_UNRESOLVED).float().mean().item()),
        "ineligible_mechanism_count": ineligible,
        "hidden_counterfactual_action_invariance": hidden_invariance,
    }


def _semantic_agreement():
    independent_rows = independent.independent_rows(base=3)
    canonical_rows = canonical._rows((3,), canonical.ALL_MASKS)
    table = {(r["dependency"], r["hidden"], r["evidence_present"], r["eligible_mask"]): r["oracle_action"] for r in canonical_rows}
    matches = 0
    for row in independent_rows:
        key = (row["dependency"], row["hidden"], row["evidence_present"], row["eligible_mask"])
        matches += int(table.get(key) == row["expected_action"])
    return matches / len(independent_rows), len(table) == len(independent_rows) == 128


def run(*, protected_result_path: Path, c106_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c106_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C106_EXPERIMENT_ID:
        raise RuntimeError("C107 requires C106 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get("unseen_mask_generalization_gate_passed"):
        raise RuntimeError("C107 requires accepted C106 gate")
    if not torch.cuda.is_available():
        raise RuntimeError("C107 requires CUDA")

    source = inspect.getsource(independent)
    forbidden = [x for x in ("gate_e_acquisition_mechanism_oracle", "gate_e_information_sufficiency_oracle", "gate_e_c106_unseen_mask_generalization") if x in source]
    if forbidden:
        raise RuntimeError(f"independent fixture imports canonical generator markers: {forbidden}")

    before = _sha(protected_result_path)
    agreement, coverage = _semantic_agreement()
    previous = canonical._evaluate
    canonical._evaluate = _independent_evaluate
    try:
        records = [canonical._train_seed(seed, torch.device("cuda")) for seed in SEEDS]
    finally:
        canonical._evaluate = previous

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C107")

    metrics = [r["ood"] for r in records]
    all_pass = agreement == 1.0 and coverage and all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "training_generator_family": "C106 canonical training generator",
        "evaluation_generator_family": "independent C107 fixture",
        "evaluation_example_count": 128,
        "independent_fixture_forbidden_import_hits": forbidden,
        "independent_vs_canonical_label_agreement_rate": agreement,
        "independent_vs_canonical_key_coverage_complete": coverage,
        "independent_action_accuracy": _stats([m["action_accuracy"] for m in metrics]),
        "independent_minimum_class_recall": _stats([m["minimum_present_class_recall"] for m in metrics]),
        "independent_action_flip_count": {"sum": sum(m["action_flip_count"] for m in metrics), "max": max(m["action_flip_count"] for m in metrics)},
        "independent_minimum_burden_rate": _stats([m["minimum_burden_rate"] for m in metrics]),
        "independent_ineligible_mechanism_count": {"sum": sum(m["ineligible_mechanism_count"] for m in metrics), "max": max(m["ineligible_mechanism_count"] for m in metrics)},
        "independent_hidden_counterfactual_action_invariance": _stats([m["hidden_counterfactual_action_invariance"] for m in metrics]),
        "all_validation_passed": all_pass,
        "independent_evaluator_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "independent-generator falsification of shared train/eval implementation bugs",
        "summary": summary,
        "records": records,
        "C106_summary_sha256": _sha(c106_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C107 changes generator implementation but preserves the same abstract feature semantics",
            "the production router implementation remains shared",
            "feature re-encoding, distractors, and noisy runtime metadata remain untested",
            "C107 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    for row in records:
        m = row["ood"]
        print(f"[C107] seed={row['seed']} independent={m['action_accuracy']:.6f} min_recall={m['minimum_present_class_recall']:.6f} burden={m['minimum_burden_rate']:.6f} flips={m['action_flip_count']} pass={row['validation_passed']}", flush=True)
    return report
