"""C110: paired diagnosis of signed-boolean Control-Lane canonicalization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as c108

EXPERIMENT_ID = "C110-v5e-signed-control-canonicalization-diagnostic"
C109_EXPERIMENT_ID = "C109-v5e-reencoding-failure-localization"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
REPLAY_SEEDS = c108.SEEDS
_ORIGINAL_TENSORIZE = c108._tensorize


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _signed_tensorize(rows, codebook, device):
    working, context, op_ids, labels = _ORIGINAL_TENSORIZE(rows, codebook, device)
    working = working.clone()
    context = context.clone()
    working[:, :, 1:4] = torch.sign(working[:, :, 1:4])
    context[:, :, :4] = torch.sign(context[:, :, :4])
    if torch.any(working[:, :, 1:4] == 0) or torch.any(context[:, :, :4] == 0):
        raise RuntimeError("C110 sign canonicalizer received zero boolean code")
    return working, context, op_ids, labels


def _canonical_records(device):
    previous = c108._tensorize
    c108._tensorize = _signed_tensorize
    try:
        return [c108._train_seed(seed, device) for seed in REPLAY_SEEDS]
    finally:
        c108._tensorize = previous


def run(*, protected_result_path: Path, c109_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c109_summary_path.read_text(encoding="utf-8"))
    summary109 = prerequisite.get("summary", {})
    if prerequisite.get("experiment_id") != C109_EXPERIMENT_ID:
        raise RuntimeError("C110 requires C109 summary")
    if prerequisite.get("status") != "PASS" or not summary109.get("failure_localization_completed"):
        raise RuntimeError("C110 requires completed C109 localization")
    if not summary109.get("known_c108_negative_reproduced"):
        raise RuntimeError("C110 requires reproduced C108 negative")
    if not torch.cuda.is_available():
        raise RuntimeError("C110 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    raw = [c108._train_seed(seed, device) for seed in REPLAY_SEEDS]
    raw_negative_reproduced = any(r["seed"] == 20261311 and not r["validation_passed"] for r in raw)
    canonical = _canonical_records(device)
    for row in canonical:
        worst = min(m["action_accuracy"] for m in row["ood"].values())
        print(f"[C110] seed={row['seed']} anchor={row['anchor']['action_accuracy']:.6f} ood_acc_min={worst:.6f} pass={row['validation_passed']}", flush=True)

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C110")

    ood = [m for r in canonical for m in r["ood"].values()]
    canonical_all_pass = all(r["validation_passed"] for r in canonical)
    gate = bool(raw_negative_reproduced and canonical_all_pass)
    summary = {
        "replay_seeds": list(REPLAY_SEEDS),
        "architecture_training_optimizer_codebooks_changed": False,
        "adapter": "schema-known boolean signed value -> sign(value) in {-1,+1}",
        "raw_c108_negative_reproduced": raw_negative_reproduced,
        "canonical_anchor_action_accuracy": _stats([r["anchor"]["action_accuracy"] for r in canonical]),
        "canonical_anchor_minimum_class_recall": _stats([r["anchor"]["minimum_class_recall"] for r in canonical]),
        "canonical_ood_action_accuracy": _stats([m["action_accuracy"] for m in ood]),
        "canonical_ood_minimum_class_recall": _stats([m["minimum_class_recall"] for m in ood]),
        "canonical_ood_minimum_burden_rate": _stats([m["minimum_burden_rate"] for m in ood]),
        "canonical_ood_ineligible_mechanism_count": {"sum": sum(m["ineligible_mechanism_count"] for m in ood), "max": max(m["ineligible_mechanism_count"] for m in ood)},
        "canonical_ood_action_flip_count": {"sum": sum(m["action_flip_count"] for m in ood), "max": max(m["action_flip_count"] for m in ood)},
        "canonical_all_validation_passed": canonical_all_pass,
        "signed_control_canonicalization_diagnostic_gate_passed": gate,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION-DIAGNOSTIC",
        "status": "PASS",
        "status_meaning": "paired diagnosis of explicit signed boolean Control-Lane canonicalization",
        "summary": summary,
        "raw_records": raw,
        "canonical_records": canonical,
        "C109_summary_sha256": _sha(c109_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C110 assumes schema-known boolean channels and a sign contract",
            "C110 tests a diagnostic adapter rather than production integration",
            "near-zero, noisy, and stale runtime metadata remain untested",
            "C110 does not establish Gate E passage"
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
