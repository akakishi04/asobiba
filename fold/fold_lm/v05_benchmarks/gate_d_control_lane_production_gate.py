"""C96: production ControlLaneActionRouter runtime/VRAM gate.

C95 prospectively validated the fixed control-lane routing semantics on fresh
seeds and held-out rows.  C96 promotes that representation into production code
and verifies the production class itself at width 3072/5120 using learned
actions, end-to-end sparse runtime, output equivalence, and router memory cost.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05_benchmarks.gate_d_c96_production_helpers import (
    CONTROL_WIDTH,
    HIDDEN_WIDTH,
    TRAIN_STEPS,
    train_measure,
)

EXPERIMENT_ID = "C96-v5d-production-control-lane-runtime-vram"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261161, 20261162, 20261163)
WIDTHS = (3072, 5120)
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.99
MIN_COMPUTE_REDUCTION = 0.45
MAX_RUNTIME_RATIO = 0.80
MAX_ROUTER_CORE_RATIO = 0.001
MAX_ROUTER_VRAM_GIB = 0.05


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


def run(*, protected_result_path: Path, c95_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C96 requires CUDA")
    c95 = json.loads(c95_summary_path.read_text(encoding="utf-8"))
    if c95.get("experiment_id") != "C95-v5d-control-lane-fresh-seed-validation":
        raise RuntimeError("C96 requires C95 summary")
    if c95.get("status") != "PASS" or not bool(
        c95.get("summary", {}).get("prospective_control_lane_gate_passed")
    ):
        raise RuntimeError("C96 requires accepted C95 prospective control-lane gate")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for width in WIDTHS:
        for seed in SEEDS:
            row = train_measure(width, device, seed)
            records.append(row)
            print(
                f"[C96] width={width} seed={seed} "
                f"heldout={row['heldout']['action_accuracy']:.6f} "
                f"runtime_action={row['runtime_actions']['action_accuracy']:.6f} "
                f"device={row['learned_over_fixed_device']['median']:.4f} "
                f"wall={row['learned_over_fixed_wall']['median']:.4f} "
                f"router/core={row['router_over_core_persistent_ratio']:.8f} "
                f"vram={row['router_device_free_vram_cost_bytes'] / (1024**3):.6f}GiB",
                flush=True,
            )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C96")

    heldout_acc = [float(r["heldout"]["action_accuracy"]) for r in records]
    heldout_recall = [float(r["heldout"]["minimum_class_recall"]) for r in records]
    runtime_acc = [float(r["runtime_actions"]["action_accuracy"]) for r in records]
    runtime_recall = [float(r["runtime_actions"]["minimum_class_recall"]) for r in records]
    reduction = [float(r["runtime_actions"]["logical_compute_reduction_vs_fixed_max"]) for r in records]
    device_ratio = [float(r["learned_over_fixed_device"]["median"]) for r in records]
    wall_ratio = [float(r["learned_over_fixed_wall"]["median"]) for r in records]
    router_core = [float(r["router_over_core_persistent_ratio"]) for r in records]
    router_vram_gib = [float(r["router_device_free_vram_cost_bytes"]) / (1024**3) for r in records]

    summary = {
        "widths": list(WIDTHS),
        "fresh_seeds": list(SEEDS),
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "minimum_compute_reduction": MIN_COMPUTE_REDUCTION,
        "maximum_runtime_ratio": MAX_RUNTIME_RATIO,
        "maximum_router_core_persistent_ratio": MAX_ROUTER_CORE_RATIO,
        "maximum_router_device_free_vram_cost_gib": MAX_ROUTER_VRAM_GIB,
        "heldout_action_accuracy": _stats(heldout_acc),
        "heldout_minimum_class_recall": _stats(heldout_recall),
        "runtime_action_accuracy": _stats(runtime_acc),
        "runtime_minimum_class_recall": _stats(runtime_recall),
        "logical_compute_reduction_vs_fixed_max": _stats(reduction),
        "learned_over_fixed_device": _stats(device_ratio),
        "learned_over_fixed_wall": _stats(wall_ratio),
        "router_over_core_persistent_ratio": _stats(router_core),
        "router_device_free_vram_cost_gib": _stats(router_vram_gib),
        "all_outputs_allclose": all(bool(r["output_allclose"]) for r in records),
    }
    summary["production_control_lane_gate_passed"] = (
        min(heldout_acc) >= MIN_ACTION_ACCURACY
        and min(heldout_recall) >= MIN_CLASS_RECALL
        and min(runtime_acc) >= MIN_ACTION_ACCURACY
        and min(runtime_recall) >= MIN_CLASS_RECALL
        and min(reduction) >= MIN_COMPUTE_REDUCTION
        and max(device_ratio) <= MAX_RUNTIME_RATIO
        and max(wall_ratio) <= MAX_RUNTIME_RATIO
        and max(router_core) <= MAX_ROUTER_CORE_RATIO
        and max(router_vram_gib) <= MAX_ROUTER_VRAM_GIB
        and bool(summary["all_outputs_allclose"])
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "production control-lane learned-action runtime and VRAM gate",
        "records": records,
        "summary": summary,
        "C95_summary_sha256": _sha256(c95_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": True,
        "gate_d_candidate": bool(summary["production_control_lane_gate_passed"]),
        "limitations": [
            "C96 remains scoped to the synthetic five-action routing table",
            "C96 measures widths 3072/5120 and balanced batch 216 only",
            "current sparse execution is eager nonzero/index_select/index_copy rather than fused",
            "Gate D requires a separate formal decision even if C96 passes",
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
    parser.add_argument("--c95-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c95_summary_path=args.c95_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C96 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
