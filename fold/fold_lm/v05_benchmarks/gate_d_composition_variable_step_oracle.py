"""C86: V5-D variable-step oracle baseline on Composition.

C85 proved the supervised ANSWER/COMPUTE wiring on the tiny Condition task.
C86 moves to actual variable compute depth before training a larger router.
Composition operand magnitude is used as an observable difficulty axis:

    operand 0 -> 0 unit core steps
    operand 1 -> 1 unit core step
    operand 2 -> 2 unit core steps

The core is trained to apply one signed unit transition per step.  Evaluation
compares a fixed-max two-substep execution against a sparse oracle that gathers
only active rows.  This is still an oracle experiment; controller learning for
the expanded action space is deferred.
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

from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_composition
from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import (
    evaluate_variable_step,
    train_unit_step_model,
)

EXPERIMENT_ID = "C86-v5d-composition-variable-step-oracle"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261111, 20261112, 20261113)
RANK = 2
MIN_TRAJECTORY_EXACT = 0.99
MAX_LOGICAL_STEPS_PER_EVENT = 1.05
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


def run(*, protected_result_path: Path, c85_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C86 requires CUDA")
    c85 = json.loads(c85_summary_path.read_text(encoding="utf-8"))
    if c85.get("experiment_id") != "C85-v5d-condition-supervised-action-router":
        raise RuntimeError("C86 requires C85 summary")
    if c85.get("status") != "PASS" or not bool(
        c85.get("summary", {}).get("supervised_router_gate_passed")
    ):
        raise RuntimeError("C86 requires accepted C85 supervised router gate")

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
        final_loss = train_unit_step_model(model, train, seed=seed)
        metrics = evaluate_variable_step(model, validation)
        metrics.update({"seed": seed, "final_training_loss": final_loss})
        records.append(metrics)
        print(
            f"[C86] seed={seed} done ({index}/{len(SEEDS)}) "
            f"exact={metrics['sparse_oracle_trajectory_exact_accuracy']:.6f} "
            f"steps/event={metrics['logical_compute_steps_per_event']:.4f} "
            f"reduction={metrics['logical_compute_reduction_vs_fixed_max']:.4f} "
            f"gap={metrics['output_max_abs_gap']:.3e}",
            flush=True,
        )

    exact = [float(row["sparse_oracle_trajectory_exact_accuracy"]) for row in records]
    fixed_exact = [float(row["fixed_max_trajectory_exact_accuracy"]) for row in records]
    steps = [float(row["logical_compute_steps_per_event"]) for row in records]
    zero = [float(row["zero_step_event_rate"]) for row in records]
    two = [float(row["two_step_event_rate"]) for row in records]
    reduction = [float(row["logical_compute_reduction_vs_fixed_max"]) for row in records]
    gaps = [float(row["output_max_abs_gap"]) for row in records]

    summary = {
        "seed_count": len(SEEDS),
        "rank": RANK,
        "action_semantics": {
            "operand_0": "ANSWER/no-op (0 steps)",
            "operand_1": "COMPUTE(operation,1)",
            "operand_2": "COMPUTE(operation,2)",
        },
        "fixed_max_steps_per_event": 2.0,
        "sparse_oracle_trajectory_exact_accuracy": _stats(exact),
        "fixed_max_trajectory_exact_accuracy": _stats(fixed_exact),
        "logical_compute_steps_per_event": _stats(steps),
        "zero_step_event_rate": _stats(zero),
        "two_step_event_rate": _stats(two),
        "logical_compute_reduction_vs_fixed_max": _stats(reduction),
        "sparse_vs_fixed_output_max_abs_gap": _stats(gaps),
        "all_sparse_vs_fixed_outputs_allclose": all(
            bool(row["outputs_allclose"]) for row in records
        ),
        "minimum_trajectory_exact_accuracy": MIN_TRAJECTORY_EXACT,
        "maximum_logical_steps_per_event": MAX_LOGICAL_STEPS_PER_EVENT,
        "minimum_zero_step_rate": MIN_ZERO_STEP_RATE,
        "minimum_two_step_rate": MIN_TWO_STEP_RATE,
        "minimum_compute_reduction_vs_fixed_max": MIN_COMPUTE_REDUCTION,
    }
    summary["variable_step_oracle_gate_passed"] = (
        min(exact) >= MIN_TRAJECTORY_EXACT
        and bool(summary["all_sparse_vs_fixed_outputs_allclose"])
        and max(steps) <= MAX_LOGICAL_STEPS_PER_EVENT
        and min(zero) >= MIN_ZERO_STEP_RATE
        and min(two) >= MIN_TWO_STEP_RATE
        and min(reduction) >= MIN_COMPUTE_REDUCTION
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C86")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "variable-step oracle compute-depth baseline",
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C85_summary_sha256": _sha256(c85_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C86 uses oracle operation and operand magnitude rather than a learned variable-step router",
            "logical compute reduction is not yet a production wall-clock speedup claim",
            "C86 covers only the tiny Composition task and max depth two",
            "C86 does not establish Gate D passage",
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
    parser.add_argument("--c85-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c85_summary_path=args.c85_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C86 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
