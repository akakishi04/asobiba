"""C112: falsify dependence on class-balanced V5-E training.

C104-C111 used class-balanced sampling for the six-action selector.  C112 keeps
the accepted production boolean Control-Lane canonicalizer and the registered
C108/C111 task, architecture, optimizer, codebooks, and training schedule, but
replaces class-balanced batches with uniform sampling over training rows.

This isolates one question: does the learned policy still hold under the natural
synthetic class frequency, where ANSWER dominates and ASK_USER / STOP_UNRESOLVED
are rare?
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as c108
from fold_lm.v05_benchmarks import gate_e_c111_production_control_canonicalization as c111

EXPERIMENT_ID = "C112-v5e-natural-class-frequency-falsification"
C111_EXPERIMENT_ID = c111.EXPERIMENT_ID
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261331, 20261332, 20261333)
BATCH_SIZE = c108.PER_CLASS_BATCH * c108.ACTION_COUNT
ACTION_NAMES = (
    "ANSWER",
    "READ_MEMORY",
    "RETRIEVE",
    "OBSERVE",
    "ASK_USER",
    "STOP_UNRESOLVED",
)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _natural_indices(labels: torch.Tensor, generator: torch.Generator, device: torch.device):
    """Sample uniformly from rows, preserving the dataset's natural class skew."""
    choice = torch.randint(labels.numel(), (BATCH_SIZE,), generator=generator)
    return choice.to(device)


def _natural_class_distribution():
    rows = c108._logical_rows(c108.TRAIN_BASES)
    counts = [0] * c108.ACTION_COUNT
    for row in rows:
        counts[int(row["expected_action"])] += 1
    # _concat_training duplicates the same logical rows once per training codebook.
    counts = [count * len(c108.TRAIN_CODEBOOKS) for count in counts]
    total = sum(counts)
    return (
        {name: count for name, count in zip(ACTION_NAMES, counts)},
        {name: count / total for name, count in zip(ACTION_NAMES, counts)},
    )


def _train_seed(seed: int, device: torch.device):
    previous_tensorize = c108._tensorize
    previous_sampler = c108._balanced_indices
    c108._tensorize = c111._production_tensorize
    c108._balanced_indices = _natural_indices
    try:
        return c108._train_seed(seed, device)
    finally:
        c108._tensorize = previous_tensorize
        c108._balanced_indices = previous_sampler


def run(*, protected_result_path: Path, c111_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c111_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C111_EXPERIMENT_ID:
        raise RuntimeError("C112 requires C111 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "production_control_canonicalization_gate_passed"
    ):
        raise RuntimeError("C112 requires accepted C111 production canonicalization")
    if not torch.cuda.is_available():
        raise RuntimeError("C112 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    class_counts, class_fractions = _natural_class_distribution()
    records = []
    for seed in SEEDS:
        row = _train_seed(seed, device)
        records.append(row)
        worst_acc = min(m["action_accuracy"] for m in row["ood"].values())
        worst_recall = min(m["minimum_class_recall"] for m in row["ood"].values())
        print(
            f"[C112] seed={seed} anchor={row['anchor']['action_accuracy']:.6f} "
            f"ood_acc_min={worst_acc:.6f} ood_recall_min={worst_recall:.6f} "
            f"pass={row['validation_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C112")

    ood = [m for row in records for m in row["ood"].values()]
    all_passed = all(row["validation_passed"] for row in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(c108.TRAIN_BASES),
        "validation_bases": list(c108.VALIDATION_BASES),
        "class_balanced_training": False,
        "sampling": "uniform training-row sampling with replacement",
        "batch_size": BATCH_SIZE,
        "training_steps": c108.TRAIN_STEPS,
        "natural_training_class_counts": class_counts,
        "natural_training_class_fractions": class_fractions,
        "production_adapter": "canonicalize_boolean_channels",
        "training_codebooks": [list(x) for x in c108.TRAIN_CODEBOOKS],
        "ood_codebooks": [list(x) for x in c108.OOD_CODEBOOKS],
        "anchor_action_accuracy": _stats([r["anchor"]["action_accuracy"] for r in records]),
        "anchor_minimum_class_recall": _stats([r["anchor"]["minimum_class_recall"] for r in records]),
        "ood_action_accuracy": _stats([m["action_accuracy"] for m in ood]),
        "ood_minimum_class_recall": _stats([m["minimum_class_recall"] for m in ood]),
        "ood_minimum_burden_rate": _stats([m["minimum_burden_rate"] for m in ood]),
        "ood_ineligible_mechanism_count": {
            "sum": sum(m["ineligible_mechanism_count"] for m in ood),
            "max": max(m["ineligible_mechanism_count"] for m in ood),
        },
        "ood_action_flip_count": {
            "sum": sum(m["action_flip_count"] for m in ood),
            "max": max(m["action_flip_count"] for m in ood),
        },
        "ood_hidden_counterfactual_action_invariance": _stats(
            [m["hidden_counterfactual_action_invariance"] for m in ood]
        ),
        "all_validation_passed": all_passed,
        "natural_class_frequency_falsification_gate_passed": bool(all_passed),
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "falsification of class-balanced-training dependence",
        "summary": summary,
        "records": records,
        "C111_summary_sha256": _sha(c111_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C112 changes class sampling but remains synthetic",
            "the natural distribution is the current exhaustive synthetic distribution, not a measured product distribution",
            "runtime metadata remains semantically correct and current",
            "C112 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report
