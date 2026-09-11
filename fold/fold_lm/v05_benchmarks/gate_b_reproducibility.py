"""Gate-B multi-seed reproducibility benchmark.

This runner reuses the exact small held-out training tasks established by the
V5-B unit tests.  It is intentionally separate from unittest so normal
regressions do not retrain every task across multiple seeds.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Callable

import torch

from fold_lm.v05.arithmetic_task import ArithmeticTaskConfig, train_addition_task
from fold_lm.v05.comparison_task import ComparisonTaskConfig, train_comparison_task
from fold_lm.v05.composition_task import CompositionTaskConfig, train_composition_task
from fold_lm.v05.condition_task import ConditionTaskConfig, train_condition_task
from fold_lm.v05.copy_task import CopyTaskConfig, train_copy_task
from fold_lm.v05.language_task import LanguageTaskConfig, train_short_language_task


DEFAULT_SEEDS = (20260911, 20260912, 20260913)


@dataclass(frozen=True)
class TaskSpec:
    name: str
    loss_key: str
    score_key: str
    run: Callable[[int, str | torch.device], dict]
    reference_bar: Callable[[dict], bool]


def _copy(seed: int, device: str | torch.device) -> dict:
    return train_copy_task(
        config=CopyTaskConfig(),
        seed=seed,
        steps=120,
        learning_rate=0.01,
        batch_size=32,
        train_examples=256,
        validation_examples=128,
        device=device,
    )


def _condition(seed: int, device: str | torch.device) -> dict:
    return train_condition_task(
        config=ConditionTaskConfig(),
        seed=seed,
        steps=260,
        learning_rate=0.01,
        batch_size=32,
        train_examples=256,
        validation_examples=128,
        device=device,
    )


def _comparison(seed: int, device: str | torch.device) -> dict:
    return train_comparison_task(
        config=ComparisonTaskConfig(),
        seed=seed,
        steps=300,
        learning_rate=0.01,
        batch_size=64,
        device=device,
    )


def _addition(seed: int, device: str | torch.device) -> dict:
    return train_addition_task(
        config=ArithmeticTaskConfig(),
        seed=seed,
        steps=300,
        learning_rate=0.005,
        batch_size=32,
        device=device,
    )


def _composition(seed: int, device: str | torch.device) -> dict:
    return train_composition_task(
        config=CompositionTaskConfig(),
        seed=seed,
        steps=300,
        learning_rate=0.005,
        batch_size=64,
        device=device,
    )


def _language(seed: int, device: str | torch.device) -> dict:
    return train_short_language_task(
        config=LanguageTaskConfig(),
        seed=seed,
        steps=600,
        learning_rate=0.01,
        batch_size=24,
        device=device,
    )


def _copy_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["nll"] < 0.02
        and final["token_accuracy"] >= 0.999
        and final["exact_accuracy"] >= 0.99
    )


def _condition_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["nll"] < 0.15
        and final["trajectory_accuracy"] >= 0.97
        and final["trajectory_exact_accuracy"] >= 0.90
        and final["final_accuracy"] >= 0.97
    )


def _comparison_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["nll"] < 0.02
        and final["accuracy"] >= 0.99
        and final["less_accuracy"] >= 0.99
        and final["equal_accuracy"] >= 0.99
        and final["greater_accuracy"] >= 0.99
    )


def _addition_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["mae"] < 0.20
        and final["max_abs_error"] < 0.50
        and final["exact_accuracy"] == 1.0
    )


def _composition_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["mse"] < 1e-4
        and final["max_abs_error"] < 0.50
        and final["point_accuracy"] >= 0.999
        and final["trajectory_exact_accuracy"] >= 0.99
        and final["final_accuracy"] >= 0.99
    )


def _language_bar(result: dict) -> bool:
    final = result["final"]
    return (
        final["nll"] < 0.10
        and final["accuracy"] >= 0.99
        and final["english_accuracy"] >= 0.99
        and final["japanese_accuracy"] >= 0.99
        and final["next_accuracy"] >= 0.99
        and final["instruction_accuracy"] >= 0.99
    )


TASKS: dict[str, TaskSpec] = {
    "copy": TaskSpec("copy", "nll", "exact_accuracy", _copy, _copy_bar),
    "condition": TaskSpec(
        "condition", "nll", "trajectory_exact_accuracy", _condition, _condition_bar
    ),
    "comparison": TaskSpec("comparison", "nll", "accuracy", _comparison, _comparison_bar),
    "addition": TaskSpec("addition", "mse", "exact_accuracy", _addition, _addition_bar),
    "composition": TaskSpec(
        "composition", "mse", "trajectory_exact_accuracy", _composition, _composition_bar
    ),
    "language": TaskSpec("language", "nll", "accuracy", _language, _language_bar),
}


def validate_seeds(seeds: tuple[int, ...]) -> tuple[int, ...]:
    if len(seeds) < 2:
        raise ValueError("Gate B reproducibility requires at least two seeds")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be distinct")
    for seed in seeds:
        if type(seed) is not int or seed < 0:
            raise ValueError("seeds must be nonnegative integers")
    return seeds


def summarize_records(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    by_task: dict[str, list[dict]] = {}
    for record in records:
        name = record.get("task")
        if name not in TASKS:
            raise ValueError(f"unknown task in record: {name}")
        by_task.setdefault(name, []).append(record)

    summary: dict[str, dict] = {}
    for name, task_records in sorted(by_task.items()):
        spec = TASKS[name]
        loss_improved = [
            row["initial"][spec.loss_key] > row["final"][spec.loss_key]
            for row in task_records
        ]
        bars = [bool(row["reference_bar_passed"]) for row in task_records]
        scores = [float(row["final"][spec.score_key]) for row in task_records]
        summary[name] = {
            "runs": len(task_records),
            "all_loss_improved": all(loss_improved),
            "reference_bar_pass_count": sum(bars),
            "all_reference_bars_passed": all(bars),
            "mean_final_score": sum(scores) / len(scores),
            "min_final_score": min(scores),
        }

    return {
        "tasks": summary,
        "all_runs_loss_improved": all(
            item["all_loss_improved"] for item in summary.values()
        ),
        "all_reference_bars_passed": all(
            item["all_reference_bars_passed"] for item in summary.values()
        ),
    }


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    task_names: tuple[str, ...] = tuple(TASKS),
    device: str | torch.device = "cpu",
) -> dict:
    seeds = validate_seeds(tuple(seeds))
    if not task_names:
        raise ValueError("task_names must be non-empty")
    if len(set(task_names)) != len(task_names):
        raise ValueError("task_names must be distinct")
    for name in task_names:
        if name not in TASKS:
            raise ValueError(f"unknown task: {name}")

    device = torch.device(device)
    records: list[dict] = []
    started = time.perf_counter()
    total = len(seeds) * len(task_names)
    completed = 0
    for name in task_names:
        spec = TASKS[name]
        for seed in seeds:
            print(
                f"[gate-b] start task={name} seed={seed} ({completed + 1}/{total})",
                file=sys.stderr,
                flush=True,
            )
            run_started = time.perf_counter()
            result = spec.run(seed, device)
            elapsed = time.perf_counter() - run_started
            record = {
                "task": name,
                "seed": seed,
                "parameters": result["parameters"],
                "train_examples": result["train_examples"],
                "validation_examples": result["validation_examples"],
                "initial": result["initial"],
                "final": result["final"],
                "reference_bar_passed": spec.reference_bar(result),
                "elapsed_seconds": elapsed,
            }
            records.append(record)
            completed += 1
            print(
                f"[gate-b] done task={name} seed={seed} "
                f"score={record['final'][spec.score_key]:.6f} "
                f"bar={record['reference_bar_passed']} elapsed={elapsed:.2f}s",
                file=sys.stderr,
                flush=True,
            )

    return {
        "schema": "fold-v05-gate-b-reproducibility-v1",
        "device": str(device),
        "seeds": list(seeds),
        "task_names": list(task_names),
        "records": records,
        "summary": summarize_records(records),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--tasks", nargs="+", choices=tuple(TASKS), default=list(TASKS))
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
