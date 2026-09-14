"""C109: localize the valid-negative C108 feature re-encoding failure.

C108 is complete as a valid negative result.  C109 does not change training,
thresholds, architecture, codebooks, or seeds.  It replays the registered C108
conditions and records per-codebook/per-class confusion plus the logical rows
that flip.  The only question is where the representation failure occurs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as c108

EXPERIMENT_ID = "C109-v5e-reencoding-failure-localization"
C108_EXPERIMENT_ID = c108.EXPERIMENT_ID
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
REPLAY_SEEDS = c108.SEEDS
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


@torch.inference_mode()
def _diagnostic_evaluate(router, rows, tensors):
    base_metrics = _ORIGINAL_EVALUATE(router, rows, tensors)
    working, context, op_ids, labels = tensors
    pred = router(working, context, op_ids).argmax(dim=-1)

    confusion = [[0 for _ in range(c108.ACTION_COUNT)] for _ in range(c108.ACTION_COUNT)]
    class_counts = [0 for _ in range(c108.ACTION_COUNT)]
    class_correct = [0 for _ in range(c108.ACTION_COUNT)]
    errors = []

    control = router.config.control_width
    state_feature = working[:, :, :control].mean(dim=1)
    context_feature = context[:, :, :control].mean(dim=1)
    operation_feature = router.operation_embedding(op_ids)
    feature = torch.cat((state_feature, context_feature, operation_feature), dim=-1)
    normed = router.norm(feature)

    for i, (expected, predicted) in enumerate(zip(labels.tolist(), pred.tolist())):
        expected = int(expected)
        predicted = int(predicted)
        confusion[expected][predicted] += 1
        class_counts[expected] += 1
        class_correct[expected] += int(expected == predicted)
        if expected != predicted:
            row = rows[i]
            errors.append(
                {
                    "row_index": i,
                    "expected_action": ACTION_NAMES[expected],
                    "predicted_action": ACTION_NAMES[predicted],
                    "dependency": int(row["dependency"]),
                    "hidden": int(row["hidden"]),
                    "evidence_present": int(row["evidence_present"]),
                    "eligible_mask": list(row["eligible_mask"]),
                    "working_control": [float(x) for x in state_feature[i].tolist()],
                    "context_control": [float(x) for x in context_feature[i].tolist()],
                    "normalized_feature": [float(x) for x in normed[i].tolist()],
                }
            )

    recalls = {
        ACTION_NAMES[action]: class_correct[action] / class_counts[action]
        for action in range(c108.ACTION_COUNT)
    }
    base_metrics.update(
        {
            "class_counts": dict(zip(ACTION_NAMES, class_counts)),
            "per_class_recall": recalls,
            "confusion_matrix_expected_rows_predicted_columns": confusion,
            "error_count": len(errors),
            "error_rows": errors,
        }
    )
    return base_metrics


_ORIGINAL_EVALUATE = c108._evaluate


def run(*, protected_result_path: Path, c108_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c108_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C108_EXPERIMENT_ID:
        raise RuntimeError("C109 requires C108 summary")
    if prerequisite.get("status") != "PASS":
        raise RuntimeError("C109 requires a validly executed C108")
    if prerequisite.get("summary", {}).get("feature_reencoding_falsification_gate_passed") is not False:
        raise RuntimeError("C109 is registered only for the accepted C108 negative result")
    if not torch.cuda.is_available():
        raise RuntimeError("C109 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    previous = c108._evaluate
    c108._evaluate = _diagnostic_evaluate
    try:
        records = [c108._train_seed(seed, device) for seed in REPLAY_SEEDS]
    finally:
        c108._evaluate = previous

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C109")

    failing_conditions = []
    for record in records:
        for codebook_name, metrics in record["ood"].items():
            if metrics["error_count"]:
                failing_conditions.append(
                    {
                        "seed": record["seed"],
                        "codebook": codebook_name,
                        "error_count": metrics["error_count"],
                        "action_accuracy": metrics["action_accuracy"],
                        "minimum_class_recall": metrics["minimum_class_recall"],
                        "per_class_recall": metrics["per_class_recall"],
                        "confusion_matrix": metrics["confusion_matrix_expected_rows_predicted_columns"],
                        "error_rows": metrics["error_rows"],
                    }
                )

    replay_anchor = [r["anchor"]["action_accuracy"] for r in records]
    replay_ood = [m["action_accuracy"] for r in records for m in r["ood"].values()]
    summary = {
        "replay_seeds": list(REPLAY_SEEDS),
        "training_codebooks": [list(x) for x in c108.TRAIN_CODEBOOKS],
        "ood_codebooks": [list(x) for x in c108.OOD_CODEBOOKS],
        "training_and_thresholds_changed": False,
        "replay_anchor_action_accuracy": _stats(replay_anchor),
        "replay_ood_action_accuracy": _stats(replay_ood),
        "failing_condition_count": len(failing_conditions),
        "failing_seed_codebook_pairs": [
            [row["seed"], row["codebook"]] for row in failing_conditions
        ],
        "known_c108_negative_reproduced": any(
            row["seed"] == 20261311 and row["error_count"] > 0
            for row in failing_conditions
        ),
        "failure_localization_completed": True,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION-DIAGNOSTIC",
        "status": "PASS",
        "status_meaning": "localization of the accepted C108 representation-robustness failure",
        "summary": summary,
        "failing_conditions": failing_conditions,
        "C108_summary_sha256": _sha(c108_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C109 is a replay/localization diagnostic and does not repair C108",
            "C109 intentionally reuses the registered C108 seeds and codebooks",
            "a fix hypothesis must be registered only after the failing codebook/class pattern is observed",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )

    for record in records:
        for name, metrics in record["ood"].items():
            print(
                f"[C109] seed={record['seed']} codebook={name} "
                f"accuracy={metrics['action_accuracy']:.6f} errors={metrics['error_count']} "
                f"recalls={metrics['per_class_recall']}",
                flush=True,
            )
    return report
