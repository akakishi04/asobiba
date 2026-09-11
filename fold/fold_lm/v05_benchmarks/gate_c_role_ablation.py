"""V5-C diagnostic: isolate quality loss from up/down module-weight compression.

The C7 balanced candidate showed substantial task degradation.  This benchmark
separates representation error from the direct compressed runtime and identifies
which module Linear role is responsible.

For one already-trained V5-B task model we build four comparisons from the exact
same compressed candidate:

- high_precision: untouched V5-B core;
- up_only: materialized compressed up.weight, dense down.weight;
- down_only: dense up.weight, materialized compressed down.weight;
- both_materialized: both compressed roles copied back into dense Linear layers;
- both_direct: the direct non-materializing compressed runtime.

If both_materialized and both_direct agree in task quality, any degradation is a
property of the compressed weights rather than the direct runtime bridge.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

import torch

from fold_lm.v05.compressed_runtime import CompressedFixedRoutingCore
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS
from fold_lm.v05_benchmarks.gate_c_task_quality import (
    DEFAULT_PROFILE,
    TASKS,
    CompressionProfile,
    _train_high_precision,
    compress_trained_core,
)


VARIANTS = ("high_precision", "up_only", "down_only", "both_materialized", "both_direct")


def _materialized_variant(
    model,
    compressed_core: CompressedFixedRoutingCore,
    *,
    use_up: bool,
    use_down: bool,
):
    if not isinstance(compressed_core, CompressedFixedRoutingCore):
        raise TypeError("compressed_core must be CompressedFixedRoutingCore")
    variant = copy.deepcopy(model)
    if not isinstance(variant.core, HighPrecisionFixedRoutingCore):
        raise TypeError("model core must be HighPrecisionFixedRoutingCore")
    with torch.no_grad():
        for module_index, module in enumerate(variant.core.module_set):
            if use_up:
                source = compressed_core.up_bank.materialized_weight(module_index).to(
                    dtype=module.up.weight.dtype,
                    device=module.up.weight.device,
                )
                module.up.weight.copy_(source)
            if use_down:
                source = compressed_core.down_bank.materialized_weight(module_index).to(
                    dtype=module.down.weight.dtype,
                    device=module.down.weight.device,
                )
                module.down.weight.copy_(source)
    return variant


def run_one(
    task: str,
    seed: int,
    *,
    profile: CompressionProfile = DEFAULT_PROFILE,
    device: str | torch.device = "cpu",
) -> dict:
    if task not in TASKS:
        raise ValueError("unknown task")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    device = torch.device(device)

    model, validation, evaluator, score_name = _train_high_precision(task, seed, device)
    high_metrics = evaluator(model, validation)
    high_score = float(high_metrics[score_name])
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained model core must remain HighPrecisionFixedRoutingCore")

    compressed_core, diagnostics = compress_trained_core(model.core, profile, device=device)
    up_only = _materialized_variant(model, compressed_core, use_up=True, use_down=False).to(device)
    down_only = _materialized_variant(model, compressed_core, use_up=False, use_down=True).to(device)
    both_materialized = _materialized_variant(
        model, compressed_core, use_up=True, use_down=True
    ).to(device)
    both_direct = copy.deepcopy(model)
    both_direct.core = compressed_core
    both_direct = both_direct.to(device)

    scores = {"high_precision": high_score}
    metrics = {"high_precision": high_metrics}
    for name, candidate in (
        ("up_only", up_only),
        ("down_only", down_only),
        ("both_materialized", both_materialized),
        ("both_direct", both_direct),
    ):
        candidate_metrics = evaluator(candidate, validation)
        metrics[name] = candidate_metrics
        scores[name] = float(candidate_metrics[score_name])

    return {
        "task": task,
        "seed": seed,
        "score_name": score_name,
        "scores": scores,
        "score_deltas": {name: value - high_score for name, value in scores.items()},
        "metrics": metrics,
        "up_final_reconstruction_mse": float(diagnostics["up"]["final_mse"]),
        "down_final_reconstruction_mse": float(diagnostics["down"]["final_mse"]),
        "module_payload_ratio": float(diagnostics["module_payload_ratio"]),
        "max_observed_abs_correction": float(diagnostics["max_observed_abs_correction"]),
        "materialized_direct_score_gap": scores["both_direct"] - scores["both_materialized"],
    }


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    tasks: dict[str, dict] = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        if not rows:
            continue
        variant_summary: dict[str, dict] = {}
        for variant in VARIANTS:
            values = [float(row["scores"][variant]) for row in rows]
            deltas = [float(row["score_deltas"][variant]) for row in rows]
            variant_summary[variant] = {
                "mean_score": sum(values) / len(values),
                "min_score": min(values),
                "mean_delta": sum(deltas) / len(deltas),
                "worst_delta": min(deltas),
            }
        tasks[task] = {
            "runs": len(rows),
            "variants": variant_summary,
            "mean_up_final_reconstruction_mse": sum(
                float(row["up_final_reconstruction_mse"]) for row in rows
            ) / len(rows),
            "mean_down_final_reconstruction_mse": sum(
                float(row["down_final_reconstruction_mse"]) for row in rows
            ) / len(rows),
            "mean_module_payload_ratio": sum(
                float(row["module_payload_ratio"]) for row in rows
            ) / len(rows),
            "max_observed_abs_correction": max(
                float(row["max_observed_abs_correction"]) for row in rows
            ),
            "max_abs_materialized_direct_score_gap": max(
                abs(float(row["materialized_direct_score_gap"])) for row in rows
            ),
        }
    return {"tasks": tasks}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    task_names: tuple[str, ...] = TASKS,
    profile: CompressionProfile = DEFAULT_PROFILE,
    device: str | torch.device = "cpu",
) -> dict:
    if len(seeds) < 1 or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("seeds must be distinct nonnegative integers")
    if not task_names or len(set(task_names)) != len(task_names) or any(task not in TASKS for task in task_names):
        raise ValueError("invalid task_names")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")

    records: list[dict] = []
    total = len(seeds) * len(task_names)
    completed = 0
    for task in task_names:
        for seed in seeds:
            print(
                f"[gate-c-role] start task={task} seed={seed} ({completed + 1}/{total})",
                file=sys.stderr,
                flush=True,
            )
            record = run_one(task, seed, profile=profile, device=device)
            records.append(record)
            completed += 1
            print(
                f"[gate-c-role] done task={task} seed={seed} "
                f"up={record['scores']['up_only']:.6f} "
                f"down={record['scores']['down_only']:.6f} "
                f"both={record['scores']['both_materialized']:.6f}",
                file=sys.stderr,
                flush=True,
            )
    return {
        "schema": "fold-v05-gate-c-role-ablation-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "task_names": list(task_names),
        "records": records,
        "summary": summarize(records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        task_names=tuple(args.tasks),
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
