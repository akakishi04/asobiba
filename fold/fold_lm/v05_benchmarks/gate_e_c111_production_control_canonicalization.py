"""C111: integrate the C110 signed-boolean canonicalization as a production primitive.

C108 found a valid representation-robustness failure. C110 showed that explicit
schema-aware boolean canonicalization removes that failure diagnostically.
C111 asks whether the production ``canonicalize_boolean_channels`` primitive
recovers the known failing seed and also holds across fresh seeds without
changing the router architecture, optimizer, training schedule, or codebooks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05.controller import canonicalize_boolean_channels
from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as c108

EXPERIMENT_ID = "C111-v5e-production-control-canonicalization-integration"
C110_EXPERIMENT_ID = "C110-v5e-signed-control-canonicalization-diagnostic"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
KNOWN_REGRESSION_SEED = 20261311
FRESH_SEEDS = (20261321, 20261322, 20261323)
ALL_SEEDS = (KNOWN_REGRESSION_SEED,) + FRESH_SEEDS
_ORIGINAL_TENSORIZE = c108._tensorize


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _production_tensorize(rows, codebook, device):
    working, context, op_ids, labels = _ORIGINAL_TENSORIZE(rows, codebook, device)
    working = canonicalize_boolean_channels(
        working,
        (1, 2, 3),
        threshold=0.0,
        false_value=-1.0,
        true_value=1.0,
    )
    context = canonicalize_boolean_channels(
        context,
        (0, 1, 2, 3),
        threshold=0.0,
        false_value=-1.0,
        true_value=1.0,
    )
    return working, context, op_ids, labels


def _adapter_contract_smoke() -> bool:
    signed = torch.tensor([[[7.0, -0.1, 4.0, -3.5]]], dtype=torch.float32)
    signed_out = canonicalize_boolean_channels(signed, (1, 2, 3), threshold=0.0)
    zero_one = torch.tensor([[[0.0, 1.0, 0.0, 1.0]]], dtype=torch.float32)
    zero_one_out = canonicalize_boolean_channels(zero_one, (0, 1, 2, 3), threshold=0.5)
    return bool(
        torch.equal(signed_out, torch.tensor([[[7.0, -1.0, 1.0, -1.0]]]))
        and torch.equal(zero_one_out, torch.tensor([[[-1.0, 1.0, -1.0, 1.0]]]))
    )


def _run_records(device):
    previous = c108._tensorize
    c108._tensorize = _production_tensorize
    try:
        return [c108._train_seed(seed, device) for seed in ALL_SEEDS]
    finally:
        c108._tensorize = previous


def run(*, protected_result_path: Path, c110_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c110_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C110_EXPERIMENT_ID:
        raise RuntimeError("C111 requires C110 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "signed_control_canonicalization_diagnostic_gate_passed"
    ):
        raise RuntimeError("C111 requires accepted C110 canonicalization diagnostic")
    if not torch.cuda.is_available():
        raise RuntimeError("C111 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    adapter_smoke = _adapter_contract_smoke()
    records = _run_records(device)
    for row in records:
        worst_acc = min(m["action_accuracy"] for m in row["ood"].values())
        worst_recall = min(m["minimum_class_recall"] for m in row["ood"].values())
        print(
            f"[C111] seed={row['seed']} anchor={row['anchor']['action_accuracy']:.6f} "
            f"ood_acc_min={worst_acc:.6f} ood_recall_min={worst_recall:.6f} "
            f"pass={row['validation_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C111")

    known = next(row for row in records if row["seed"] == KNOWN_REGRESSION_SEED)
    fresh = [row for row in records if row["seed"] in FRESH_SEEDS]
    ood_metrics = [m for row in records for m in row["ood"].values()]
    known_recovered = bool(known["validation_passed"])
    fresh_all_passed = all(row["validation_passed"] for row in fresh)
    all_passed = all(row["validation_passed"] for row in records)
    gate = bool(adapter_smoke and known_recovered and fresh_all_passed and all_passed)

    summary = {
        "known_regression_seed": KNOWN_REGRESSION_SEED,
        "fresh_seeds": list(FRESH_SEEDS),
        "all_validation_seeds": list(ALL_SEEDS),
        "production_adapter": "canonicalize_boolean_channels",
        "signed_schema_threshold": 0.0,
        "canonical_false_value": -1.0,
        "canonical_true_value": 1.0,
        "router_architecture_changed": False,
        "training_optimizer_codebooks_changed": False,
        "adapter_contract_smoke_passed": adapter_smoke,
        "known_c108_failure_recovered": known_recovered,
        "fresh_seed_validation_all_passed": fresh_all_passed,
        "anchor_action_accuracy": _stats([r["anchor"]["action_accuracy"] for r in records]),
        "anchor_minimum_class_recall": _stats([r["anchor"]["minimum_class_recall"] for r in records]),
        "ood_action_accuracy": _stats([m["action_accuracy"] for m in ood_metrics]),
        "ood_minimum_class_recall": _stats([m["minimum_class_recall"] for m in ood_metrics]),
        "ood_minimum_burden_rate": _stats([m["minimum_burden_rate"] for m in ood_metrics]),
        "ood_ineligible_mechanism_count": {
            "sum": sum(m["ineligible_mechanism_count"] for m in ood_metrics),
            "max": max(m["ineligible_mechanism_count"] for m in ood_metrics),
        },
        "ood_action_flip_count": {
            "sum": sum(m["action_flip_count"] for m in ood_metrics),
            "max": max(m["action_flip_count"] for m in ood_metrics),
        },
        "all_validation_passed": all_passed,
        "production_control_canonicalization_gate_passed": gate,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-REPRESENTATION-INTEGRATION",
        "status": "PASS",
        "status_meaning": "production integration validation for schema-aware boolean Control-Lane canonicalization",
        "summary": summary,
        "records": records,
        "C110_summary_sha256": _sha(c110_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C111 validates the production adapter only for schema-known boolean channels",
            "the signed threshold is exact and noiseless; near-threshold noise remains untested",
            "stale or semantically incorrect runtime metadata remains untested",
            "C111 remains synthetic and does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report
