"""C90: prospective controller-capacity frontier after C89.

C89 found a real sparse-runtime crossover at width 3072, but the default
production controller consumed about 35% of Shared-Basis core persistent bytes
because its hidden width defaults to the core width.  C90 asks whether the
controller bottleneck can be made materially smaller while preserving the
accepted C87 five-action routing semantics and trajectory quality.

One trained Composition core is shared by all router-width candidates within a
seed.  Candidates are evaluated on the same validation set.  The smallest
candidate passing every quality/compute criterion across all fresh seeds is
selected prospectively.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_composition
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import _storage_bytes
from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import train_unit_step_model
from fold_lm.v05_benchmarks.gate_d_c87_router_eval import evaluate_router
from fold_lm.v05_benchmarks.gate_d_c87_router_train import (
    ACTION_COUNT,
    build_router_examples,
    train_router,
)

EXPERIMENT_ID = "C90-v5d-router-hidden-width-frontier"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261131, 20261132, 20261133)
RANK = 2
HIDDEN_WIDTHS = (2, 4, 8, 16, 32)
DEFAULT_HIDDEN_WIDTH = 32
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.99
MIN_TRAJECTORY_EXACT = 0.99
MIN_COMPUTE_REDUCTION = 0.45
MAX_SELECTED_BYTES_OVER_DEFAULT = 0.50


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


def run(*, protected_result_path: Path, c89_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C90 requires CUDA")
    c89 = json.loads(c89_summary_path.read_text(encoding="utf-8"))
    if c89.get("experiment_id") != "C89-v5d-sparse-runtime-width-crossover":
        raise RuntimeError("C90 requires C89 summary")
    c89s = c89.get("summary", {})
    if c89.get("status") != "PASS" or not bool(c89s.get("router_inclusive_crossover_found")):
        raise RuntimeError("C90 requires accepted C89 router-inclusive crossover")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    by_width = {width: [] for width in HIDDEN_WIDTHS}
    for seed_index, seed in enumerate(SEEDS, start=1):
        config, initial_model, train, validation = _build_composition(seed, "v5b", device)
        model = copy.deepcopy(initial_model).to(device)
        model.core = SharedBasisFixedRoutingCore(
            initial_model.core,
            RANK,
            execution_mode="materialized",
        ).to(device)
        train_unit_step_model(model, train, seed=seed)
        model.core.set_execution_mode("gemm_native")
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        states, contexts, op_ids, labels = build_router_examples(model, train, device)

        for hidden in HIDDEN_WIDTHS:
            torch.manual_seed(seed + 90000 + hidden)
            router = SupervisedActionRouter(
                ActionRouterConfig(
                    width=config.width,
                    operation_vocab_size=2,
                    hidden_width=hidden,
                    action_count=ACTION_COUNT,
                )
            ).to(device)
            final_loss = train_router(router, states, contexts, op_ids, labels, seed=seed)
            metrics = evaluate_router(model, router, validation)
            metrics.update({
                "seed": seed,
                "hidden_width": hidden,
                "router_persistent_bytes": _storage_bytes(router),
                "final_router_loss": final_loss,
            })
            by_width[hidden].append(metrics)
            print(
                f"[C90] seed={seed} ({seed_index}/{len(SEEDS)}) hidden={hidden} "
                f"action={metrics['action_accuracy']:.6f} "
                f"class_min={metrics['minimum_class_recall']:.6f} "
                f"exact={metrics['learned_trajectory_exact_accuracy']:.6f}",
                flush=True,
            )

    default_bytes = int(by_width[DEFAULT_HIDDEN_WIDTH][0]["router_persistent_bytes"])
    candidates = []
    selected = None
    for hidden in HIDDEN_WIDTHS:
        rows = by_width[hidden]
        action = [float(row["action_accuracy"]) for row in rows]
        recall = [float(row["minimum_class_recall"]) for row in rows]
        exact = [float(row["learned_trajectory_exact_accuracy"]) for row in rows]
        reduction = [float(row["logical_compute_reduction_vs_fixed_max"]) for row in rows]
        bytes_value = int(rows[0]["router_persistent_bytes"])
        quality_pass = (
            min(action) >= MIN_ACTION_ACCURACY
            and min(recall) >= MIN_CLASS_RECALL
            and min(exact) >= MIN_TRAJECTORY_EXACT
            and min(reduction) >= MIN_COMPUTE_REDUCTION
        )
        row = {
            "hidden_width": hidden,
            "router_persistent_bytes": bytes_value,
            "bytes_over_default": bytes_value / default_bytes,
            "action_accuracy": _stats(action),
            "minimum_class_recall": _stats(recall),
            "trajectory_exact_accuracy": _stats(exact),
            "compute_reduction_vs_fixed_max": _stats(reduction),
            "quality_gate_passed": quality_pass,
        }
        candidates.append(row)
        if selected is None and quality_pass:
            selected = row

    capacity_gate = (
        selected is not None
        and float(selected["bytes_over_default"]) <= MAX_SELECTED_BYTES_OVER_DEFAULT
    )
    summary = {
        "seed_count": len(SEEDS),
        "rank": RANK,
        "core_width": 32,
        "hidden_width_candidates": list(HIDDEN_WIDTHS),
        "default_hidden_width": DEFAULT_HIDDEN_WIDTH,
        "selection_rule": "smallest hidden width passing all quality/compute gates",
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "minimum_trajectory_exact": MIN_TRAJECTORY_EXACT,
        "minimum_compute_reduction": MIN_COMPUTE_REDUCTION,
        "maximum_selected_bytes_over_default": MAX_SELECTED_BYTES_OVER_DEFAULT,
        "candidates": candidates,
        "selected_hidden_width": None if selected is None else int(selected["hidden_width"]),
        "selected_bytes_over_default": None if selected is None else float(selected["bytes_over_default"]),
        "router_capacity_gate_passed": capacity_gate,
    }

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C90")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "prospective supervised-router hidden-width capacity frontier",
        "seeds": list(SEEDS),
        "summary": summary,
        "C89_summary_sha256": _sha256(c89_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C90 selects controller capacity only on the current tiny Composition routing task",
            "C90 does not prove the selected bottleneck is sufficient for broader routing tasks",
            "C90 measures controller persistent bytes, not full end-to-end VRAM at large width",
            "C90 does not establish Gate D passage",
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
    parser.add_argument("--c89-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c89_summary_path=args.c89_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C90 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
