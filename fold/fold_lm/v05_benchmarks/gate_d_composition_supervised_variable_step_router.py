"""C87: supervised learned variable-step router on Composition.

C86 established the oracle 0/1/2-step policy.  C87 removes oracle action
selection at inference and trains a five-action controller from observable
working state, full operand event context, and ADD/SUB operation token.
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
from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import train_unit_step_model
from fold_lm.v05_benchmarks.gate_d_c87_router_train import (
    ACTION_COUNT,
    build_router_examples,
    train_router,
)
from fold_lm.v05_benchmarks.gate_d_c87_router_eval import evaluate_router

EXPERIMENT_ID = "C87-v5d-composition-supervised-variable-step-router"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261121, 20261122, 20261123)
RANK = 2
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.99
MIN_TRAJECTORY_EXACT = 0.99
MIN_MEAN_EXACT_DELTA = -0.002
MAX_STEPS_PER_EVENT = 1.05
MIN_ZERO_STEP_RATE = 0.30
MIN_TWO_STEP_RATE = 0.30
MIN_COMPUTE_REDUCTION = 0.45


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


def run(*, protected_result_path: Path, c86_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C87 requires CUDA")
    c86 = json.loads(c86_summary_path.read_text(encoding="utf-8"))
    if c86.get("experiment_id") != "C86-v5d-composition-variable-step-oracle":
        raise RuntimeError("C87 requires C86 summary")
    if c86.get("status") != "PASS" or not bool(
        c86.get("summary", {}).get("variable_step_oracle_gate_passed")
    ):
        raise RuntimeError("C87 requires accepted C86 oracle gate")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for index, seed in enumerate(SEEDS, start=1):
        config, initial_model, train, validation = _build_composition(seed, "v5b", device)
        model = copy.deepcopy(initial_model).to(device)
        model.core = SharedBasisFixedRoutingCore(
            initial_model.core,
            RANK,
            execution_mode="materialized",
        ).to(device)
        final_model_loss = train_unit_step_model(model, train, seed=seed)
        model.core.set_execution_mode("gemm_native")
        for parameter in model.parameters():
            parameter.requires_grad_(False)

        torch.manual_seed(seed + 90000)
        router = SupervisedActionRouter(
            ActionRouterConfig(
                width=config.width,
                operation_vocab_size=2,
                action_count=ACTION_COUNT,
            )
        ).to(device)
        states, contexts, op_ids, labels = build_router_examples(model, train, device)
        final_router_loss = train_router(
            router, states, contexts, op_ids, labels, seed=seed
        )
        metrics = evaluate_router(model, router, validation)
        metrics.update({
            "seed": seed,
            "final_model_loss": final_model_loss,
            "final_router_loss": final_router_loss,
        })
        records.append(metrics)
        print(
            f"[C87] seed={seed} done ({index}/{len(SEEDS)}) "
            f"action={metrics['action_accuracy']:.6f} "
            f"class_min={metrics['minimum_class_recall']:.6f} "
            f"exact={metrics['learned_trajectory_exact_accuracy']:.6f} "
            f"steps/event={metrics['logical_compute_steps_per_event']:.4f}",
            flush=True,
        )

    action = [float(row["action_accuracy"]) for row in records]
    class_min = [float(row["minimum_class_recall"]) for row in records]
    exact = [float(row["learned_trajectory_exact_accuracy"]) for row in records]
    delta = [float(row["exact_delta_vs_oracle"]) for row in records]
    steps = [float(row["logical_compute_steps_per_event"]) for row in records]
    zero = [float(row["zero_step_event_rate"]) for row in records]
    two = [float(row["two_step_event_rate"]) for row in records]
    reduction = [float(row["logical_compute_reduction_vs_fixed_max"]) for row in records]

    summary = {
        "seed_count": len(SEEDS),
        "rank": RANK,
        "action_space": ["ANSWER", "ADD1", "ADD2", "SUB1", "SUB2"],
        "controller_observations": [
            "working_state", "operand_magnitude_context", "operation_token"
        ],
        "target_or_oracle_action_is_not_controller_input": True,
        "router_initialization_seed_offset": 90000,
        "action_accuracy": _stats(action),
        "minimum_per_seed_class_recall": _stats(class_min),
        "learned_trajectory_exact_accuracy": _stats(exact),
        "exact_delta_vs_c86_oracle": _stats(delta),
        "logical_compute_steps_per_event": _stats(steps),
        "zero_step_event_rate": _stats(zero),
        "two_step_event_rate": _stats(two),
        "logical_compute_reduction_vs_fixed_max": _stats(reduction),
        "all_learned_vs_oracle_outputs_allclose": all(
            bool(row["learned_vs_oracle_outputs_allclose"]) for row in records
        ),
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "minimum_trajectory_exact_accuracy": MIN_TRAJECTORY_EXACT,
        "minimum_mean_exact_delta": MIN_MEAN_EXACT_DELTA,
        "maximum_steps_per_event": MAX_STEPS_PER_EVENT,
        "minimum_zero_step_rate": MIN_ZERO_STEP_RATE,
        "minimum_two_step_rate": MIN_TWO_STEP_RATE,
        "minimum_compute_reduction_vs_fixed_max": MIN_COMPUTE_REDUCTION,
    }
    summary["supervised_variable_step_router_gate_passed"] = (
        min(action) >= MIN_ACTION_ACCURACY
        and min(class_min) >= MIN_CLASS_RECALL
        and min(exact) >= MIN_TRAJECTORY_EXACT
        and float(summary["exact_delta_vs_c86_oracle"]["mean"]) >= MIN_MEAN_EXACT_DELTA
        and max(steps) <= MAX_STEPS_PER_EVENT
        and min(zero) >= MIN_ZERO_STEP_RATE
        and min(two) >= MIN_TWO_STEP_RATE
        and min(reduction) >= MIN_COMPUTE_REDUCTION
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C87")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "supervised learned variable-step routing gate",
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C86_summary_sha256": _sha256(c86_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": True,
        "gate_d_candidate": False,
        "limitations": [
            "C87 uses explicit observable ADD/SUB token and operand magnitude",
            "C87 covers the tiny Composition task and max depth two",
            "logical compute reduction is not yet production wall-clock speedup",
            "C87 does not establish Gate D passage",
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
    parser.add_argument("--c86-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c86_summary_path=args.c86_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C87 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
