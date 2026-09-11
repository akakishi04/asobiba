"""Gate-B controlled comparison against dense and shared/recurrent baselines.

The benchmark keeps dataset construction, task model, encoder/decoder, loss,
optimizer, training steps, and seed schedule fixed.  Only ``model.core`` is
replaced with one of three implementations exposing the same state-update API:

- ``v5b``: HighPrecisionFixedRoutingCore
- ``dense``: ActiveComputeDenseCore, matched on active Linear MACs
- ``shared``: ParameterMatchedSharedCore, matched on independent core parameters

Representative tasks span state manipulation, multi-step composition, and
short bilingual byte language.  This is a controlled Gate-B comparison, not a
claim of broad model superiority.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass

import torch
from torch.nn import functional as F

from fold_lm.v05.baselines import (
    ActiveComputeDenseCore,
    ParameterMatchedSharedCore,
    reference_core_stats,
    trainable_parameter_count,
)
from fold_lm.v05.composition_task import (
    CompositionModel,
    CompositionTaskConfig,
    evaluate_composition,
    make_composition_splits,
)
from fold_lm.v05.condition_task import (
    ConditionHoldUpdateModel,
    ConditionTaskConfig,
    evaluate_condition,
    make_condition_splits,
)
from fold_lm.v05.language_task import (
    LanguageTaskConfig,
    ShortByteLanguageModel,
    evaluate_language,
    make_language_splits,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


ARCHITECTURES = ("v5b", "dense", "shared")
TASKS = ("condition", "composition", "language")
DEFAULT_SEEDS = (20260911, 20260912, 20260913)


@dataclass(frozen=True)
class CoreComparisonStats:
    architecture: str
    trainable_parameters: int
    active_linear_macs_per_slot_step: int

    def __post_init__(self) -> None:
        if self.architecture not in ARCHITECTURES:
            raise ValueError("unknown architecture")
        if type(self.trainable_parameters) is not int or self.trainable_parameters <= 0:
            raise ValueError("trainable_parameters must be positive")
        if (
            type(self.active_linear_macs_per_slot_step) is not int
            or self.active_linear_macs_per_slot_step <= 0
        ):
            raise ValueError("active_linear_macs_per_slot_step must be positive")


def _core_config(model) -> LearnedCoreConfig:
    core = model.core
    config = getattr(core, "config", None)
    if not isinstance(config, LearnedCoreConfig):
        raise TypeError("task model must expose a LearnedCoreConfig core")
    return config


def replace_core(model, architecture: str):
    if architecture not in ARCHITECTURES:
        raise ValueError(f"unknown architecture: {architecture}")
    config = _core_config(model)
    if architecture == "v5b":
        return model
    if architecture == "dense":
        model.core = ActiveComputeDenseCore(config)
    else:
        model.core = ParameterMatchedSharedCore(config)
    return model


def core_stats_for(model, architecture: str) -> CoreComparisonStats:
    if architecture not in ARCHITECTURES:
        raise ValueError(f"unknown architecture: {architecture}")
    config = _core_config(model)
    if architecture == "v5b":
        stats = reference_core_stats(config)
    else:
        stats = model.core.stats()
    return CoreComparisonStats(
        architecture=architecture,
        trainable_parameters=stats.trainable_parameters,
        active_linear_macs_per_slot_step=stats.active_linear_macs_per_slot_step,
    )


def _build_condition(seed: int, architecture: str, device: torch.device):
    config = ConditionTaskConfig()
    torch.manual_seed(seed)
    train, validation = make_condition_splits(
        config, train_examples=256, validation_examples=128, seed=seed + 100
    )
    model = ConditionHoldUpdateModel(config)
    if architecture != "v5b":
        torch.manual_seed(seed + 1000 + ARCHITECTURES.index(architecture))
        replace_core(model, architecture)
    model = model.to(device)
    return config, model, train, validation


def _train_condition(seed: int, architecture: str, device: torch.device) -> dict:
    config, model, train, validation = _build_condition(seed, architecture, device)
    stats = core_stats_for(model, architecture)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    initial = evaluate_condition(model, validation)
    model.train()
    for _ in range(260):
        indices = torch.randint(train.size, (32,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        candidates = train.candidates[indices].to(device)
        targets = train.targets[indices].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(initial_values, operations, candidates)
        loss = F.cross_entropy(logits.flatten(0, 1), targets.flatten())
        if not torch.isfinite(loss):
            raise ValueError("condition baseline comparison produced non-finite loss")
        loss.backward()
        optimizer.step()
    final = evaluate_condition(model, validation)
    return {
        "initial": initial,
        "final": final,
        "model_parameters": trainable_parameter_count(model),
        "core_parameters": stats.trainable_parameters,
        "active_linear_macs_per_slot_step": stats.active_linear_macs_per_slot_step,
        "score": final["trajectory_exact_accuracy"],
    }


def _build_composition(seed: int, architecture: str, device: torch.device):
    config = CompositionTaskConfig()
    torch.manual_seed(seed)
    train, validation = make_composition_splits(config)
    model = CompositionModel(config)
    if architecture != "v5b":
        torch.manual_seed(seed + 1000 + ARCHITECTURES.index(architecture))
        replace_core(model, architecture)
    model = model.to(device)
    return config, model, train, validation


def _train_composition(seed: int, architecture: str, device: torch.device) -> dict:
    config, model, train, validation = _build_composition(seed, architecture, device)
    stats = core_stats_for(model, architecture)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    initial = evaluate_composition(model, validation)
    model.train()
    for _ in range(300):
        indices = torch.randint(train.size, (64,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(config.state_scale)
        optimizer.zero_grad(set_to_none=True)
        predicted = model(initial_values, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise ValueError("composition baseline comparison produced non-finite loss")
        loss.backward()
        optimizer.step()
    final = evaluate_composition(model, validation)
    return {
        "initial": initial,
        "final": final,
        "model_parameters": trainable_parameter_count(model),
        "core_parameters": stats.trainable_parameters,
        "active_linear_macs_per_slot_step": stats.active_linear_macs_per_slot_step,
        "score": final["trajectory_exact_accuracy"],
    }


def _build_language(seed: int, architecture: str, device: torch.device):
    config = LanguageTaskConfig()
    torch.manual_seed(seed)
    train, validation = make_language_splits(config)
    model = ShortByteLanguageModel(config)
    if architecture != "v5b":
        torch.manual_seed(seed + 1000 + ARCHITECTURES.index(architecture))
        replace_core(model, architecture)
    model = model.to(device)
    return config, model, train, validation


def _train_language(seed: int, architecture: str, device: torch.device) -> dict:
    _config, model, train, validation = _build_language(seed, architecture, device)
    stats = core_stats_for(model, architecture)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    initial = evaluate_language(model, validation)
    model.train()
    for _ in range(600):
        indices = torch.randint(train.size, (24,), generator=sampler)
        tokens = train.tokens[indices].to(device)
        tasks = train.tasks[indices].to(device)
        targets = train.targets[indices].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(tokens, tasks)
        loss = F.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise ValueError("language baseline comparison produced non-finite loss")
        loss.backward()
        optimizer.step()
    final = evaluate_language(model, validation)
    return {
        "initial": initial,
        "final": final,
        "model_parameters": trainable_parameter_count(model),
        "core_parameters": stats.trainable_parameters,
        "active_linear_macs_per_slot_step": stats.active_linear_macs_per_slot_step,
        "score": final["accuracy"],
    }


RUNNERS = {
    "condition": _train_condition,
    "composition": _train_composition,
    "language": _train_language,
}


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    summary: dict[str, dict[str, dict]] = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        if not rows:
            continue
        task_summary: dict[str, dict] = {}
        for architecture in ARCHITECTURES:
            arch_rows = [row for row in rows if row["architecture"] == architecture]
            if not arch_rows:
                continue
            scores = [float(row["score"]) for row in arch_rows]
            task_summary[architecture] = {
                "runs": len(arch_rows),
                "mean_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "mean_elapsed_seconds": sum(float(row["elapsed_seconds"]) for row in arch_rows)
                / len(arch_rows),
                "core_parameters": arch_rows[0]["core_parameters"],
                "active_linear_macs_per_slot_step": arch_rows[0][
                    "active_linear_macs_per_slot_step"
                ],
            }
        summary[task] = task_summary
    return {"tasks": summary}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    task_names: tuple[str, ...] = TASKS,
    architectures: tuple[str, ...] = ARCHITECTURES,
    device: str | torch.device = "cpu",
) -> dict:
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("seeds must contain at least two distinct nonnegative integers")
    if not task_names or len(set(task_names)) != len(task_names) or any(name not in TASKS for name in task_names):
        raise ValueError("invalid task_names")
    if not architectures or len(set(architectures)) != len(architectures) or any(name not in ARCHITECTURES for name in architectures):
        raise ValueError("invalid architectures")

    device = torch.device(device)
    total = len(seeds) * len(task_names) * len(architectures)
    completed = 0
    started = time.perf_counter()
    records: list[dict] = []
    for task in task_names:
        runner = RUNNERS[task]
        for architecture in architectures:
            for seed in seeds:
                print(
                    f"[gate-b-baseline] start task={task} arch={architecture} seed={seed} ({completed + 1}/{total})",
                    file=sys.stderr,
                    flush=True,
                )
                run_started = time.perf_counter()
                result = runner(seed, architecture, device)
                elapsed = time.perf_counter() - run_started
                record = {
                    "task": task,
                    "architecture": architecture,
                    "seed": seed,
                    **result,
                    "elapsed_seconds": elapsed,
                }
                records.append(record)
                completed += 1
                print(
                    f"[gate-b-baseline] done task={task} arch={architecture} seed={seed} "
                    f"score={record['score']:.6f} elapsed={elapsed:.2f}s",
                    file=sys.stderr,
                    flush=True,
                )
    return {
        "schema": "fold-v05-gate-b-baseline-comparison-v1",
        "device": str(device),
        "seeds": list(seeds),
        "task_names": list(task_names),
        "architectures": list(architectures),
        "records": records,
        "summary": summarize(records),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    parser.add_argument("--architectures", nargs="+", choices=ARCHITECTURES, default=list(ARCHITECTURES))
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        task_names=tuple(args.tasks),
        architectures=tuple(args.architectures),
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
