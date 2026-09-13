"""C88: does learned 50% logical compute reduction become real GPU speedup?"""
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
from fold_lm.v05_benchmarks.gate_d_c88_runtime_helpers import (
    learned_sparse_forward,
    measure_pair,
)
from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import fixed_max_forward

EXPERIMENT_ID = "C88-v5d-composition-learned-sparse-wallclock-runtime"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261121, 20261122, 20261123)
RANK = 2
MAX_RUNTIME_RATIO = 0.95


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


def run(*, protected_result_path: Path, c87_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C88 requires CUDA")
    c87 = json.loads(c87_summary_path.read_text(encoding="utf-8"))
    if c87.get("experiment_id") != "C87-v5d-composition-supervised-variable-step-router":
        raise RuntimeError("C88 requires C87 summary")
    if c87.get("status") != "PASS" or not bool(
        c87.get("summary", {}).get("supervised_variable_step_router_gate_passed")
    ):
        raise RuntimeError("C88 requires accepted C87 router gate")

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
        train_unit_step_model(model, train, seed=seed)
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
        train_router(router, states, contexts, op_ids, labels, seed=seed)
        metrics = evaluate_router(model, router, validation)
        if metrics["action_accuracy"] < 0.995 or metrics["learned_trajectory_exact_accuracy"] < 0.99:
            raise RuntimeError(f"C88 seed={seed} failed accepted C87 semantics")

        initial = validation.initial_values.to(device)
        operations = validation.operations.to(device)
        operands = validation.operands.to(device)
        with torch.inference_mode():
            fixed = fixed_max_forward(model, initial, operations, operands)
            adaptive = learned_sparse_forward(model, router, initial, operations, operands)
        outputs_allclose = bool(torch.allclose(adaptive, fixed, rtol=5e-4, atol=1e-4))
        output_max_abs_gap = float((adaptive - fixed).abs().max().item())
        runtime = measure_pair(model, router, initial, operations, operands)
        record = {
            "seed": seed,
            "batch": validation.size,
            "action_accuracy": float(metrics["action_accuracy"]),
            "trajectory_exact_accuracy": float(metrics["learned_trajectory_exact_accuracy"]),
            "logical_compute_reduction_vs_fixed_max": float(metrics["logical_compute_reduction_vs_fixed_max"]),
            "outputs_allclose": outputs_allclose,
            "output_max_abs_gap": output_max_abs_gap,
            **runtime,
        }
        records.append(record)
        print(
            f"[C88] seed={seed} done ({index}/{len(SEEDS)}) "
            f"device_ratio={runtime['adaptive_over_fixed_device']['median']:.4f} "
            f"wall_ratio={runtime['adaptive_over_fixed_wall']['median']:.4f} "
            f"allclose={outputs_allclose}",
            flush=True,
        )
        torch.cuda.empty_cache()

    device_ratios = [float(r["adaptive_over_fixed_device"]["median"]) for r in records]
    wall_ratios = [float(r["adaptive_over_fixed_wall"]["median"]) for r in records]
    summary = {
        "seed_count": len(SEEDS),
        "reuses_c87_seeds_for_runtime_mechanism_measurement": True,
        "validation_batch": records[0]["batch"],
        "logical_compute_reduction_vs_fixed_max": _stats(
            [float(r["logical_compute_reduction_vs_fixed_max"]) for r in records]
        ),
        "adaptive_over_fixed_device_latency": _stats(device_ratios),
        "adaptive_over_fixed_wall_latency": _stats(wall_ratios),
        "all_outputs_allclose": all(bool(r["outputs_allclose"]) for r in records),
        "minimum_required_speedup": 1.0 - MAX_RUNTIME_RATIO,
        "maximum_runtime_ratio": MAX_RUNTIME_RATIO,
    }
    summary["learned_sparse_wallclock_gate_passed"] = (
        bool(summary["all_outputs_allclose"])
        and max(device_ratios) <= MAX_RUNTIME_RATIO
        and max(wall_ratios) <= MAX_RUNTIME_RATIO
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C88")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "learned sparse adaptive-compute end-to-end runtime measurement",
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C87_summary_sha256": _sha256(c87_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C88 measures the current eager Python/gather/nonzero/index_copy sparse implementation",
            "C88 uses tiny Composition width=32 and full validation batch only",
            "a negative runtime result does not invalidate the C87 logical-compute result",
            "C88 does not by itself establish Gate D passage",
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
    parser.add_argument("--c87-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c87_summary_path=args.c87_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C88 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
