"""C95: prospective fresh-seed held-out validation of the fixed control lane."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05_benchmarks.gate_d_c95_control_lane_helpers import (
    MIN_ACTION_ACCURACY,
    MIN_CLASS_RECALL,
    ROUTER_SEED_OFFSET,
    TRAIN_STEPS,
    train_and_measure,
)

EXPERIMENT_ID = "C95-v5d-control-lane-fresh-seed-validation"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261151, 20261152, 20261153)
WIDTHS = (3072, 5120)
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 4


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c94_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C95 requires CUDA")
    c94 = json.loads(c94_summary_path.read_text(encoding="utf-8"))
    if c94.get("experiment_id") != "C94-v5d-control-lane-convergence-diagnosis":
        raise RuntimeError("C95 requires C94 summary")
    prior = c94.get("summary", {})
    if c94.get("status") != "PASS" or not bool(
        prior.get("control_lane_convergence_gate_passed")
    ) or not bool(prior.get("strong_width_independence_supported")):
        raise RuntimeError("C95 requires accepted C94 control-lane diagnosis")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for width in WIDTHS:
        for seed in SEEDS:
            row = train_and_measure(width, device, seed)
            records.append(row)
            v = row["validation"]
            print(
                f"[C95] width={width} seed={seed} "
                f"heldout_action={v['action_accuracy']:.6f} "
                f"heldout_class_min={v['minimum_class_recall']:.6f} "
                f"flips={v['action_flip_count']} pass={v['quality_passed']}",
                flush=True,
            )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C95")

    accuracies = [float(row["validation"]["action_accuracy"]) for row in records]
    recalls = [float(row["validation"]["minimum_class_recall"]) for row in records]
    flips = [int(row["validation"]["action_flip_count"]) for row in records]
    byte_values = [int(row["router_persistent_bytes"]) for row in records]
    summary = {
        "widths": list(WIDTHS),
        "fresh_seeds": list(SEEDS),
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "router_seed_offset": ROUTER_SEED_OFFSET,
        "held_out_row_split": "row_index % 5 == 0",
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "heldout_action_accuracy": _stats(accuracies),
        "heldout_minimum_class_recall": _stats(recalls),
        "heldout_action_flip_count": {
            "sum": sum(flips),
            "max": max(flips),
        },
        "router_persistent_bytes": _stats(byte_values),
        "all_quality_passed": all(bool(row["validation"]["quality_passed"]) for row in records),
    }
    summary["prospective_control_lane_gate_passed"] = bool(summary["all_quality_passed"])

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "prospective fresh-seed held-out control-lane validation",
        "records": records,
        "summary": summary,
        "C94_summary_sha256": _sha256(c94_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C95 validates the synthetic five-action routing table, not broad routing generalization",
            "the control-lane router remains benchmark-only diagnostic code",
            "C95 establishes prospective routing quality before production adoption",
            "C95 does not by itself establish Gate D passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c94-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c94_summary_path=args.c94_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C95 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
