"""V5-C fresh-seed revalidation for the fixed task-aware compression candidate.

C10 used the exploratory Gate-B seeds and showed that the high-fidelity
compressed structure can recover composition quality when its continuous values
are tuned with task loss.  C11 freezes that candidate and revalidates it on
previously unused seeds across condition, composition, and short byte language.

The compression profile, block codes, correction coordinates, and payload are
not selected or changed by these fresh-seed runs.  Only compressed continuous
values are task-tuned.  After tuning, the representation is exported back to the
direct non-materializing runtime and score parity is checked.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    CompressedModuleInitializations,
)
from fold_lm.v05.condition_task import make_condition_splits
from fold_lm.v05.composition_task import make_composition_splits
from fold_lm.v05.language_task import make_language_splits
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_task_quality import TASKS, _train_high_precision
from fold_lm.v05_benchmarks.gate_c_task_aware_recovery import (
    DEFAULT_PROFILE,
    TaskTunableCompressedCore,
    _freeze_except_compressed,
    _initializations_from_core,
    _max_abs_correction,
)


EXPLORATORY_SEEDS = (20260911, 20260912, 20260913)
FRESH_SEEDS = (20260921, 20260922, 20260923)

TUNING_SPECS = {
    "condition": {"steps": 260, "learning_rate": 0.002, "batch_size": 32},
    "composition": {"steps": 300, "learning_rate": 0.002, "batch_size": 64},
    "language": {"steps": 600, "learning_rate": 0.002, "batch_size": 24},
}


def _training_examples(task: str, model, seed: int):
    if task == "condition":
        train, _ = make_condition_splits(
            model.config,
            train_examples=256,
            validation_examples=128,
            seed=seed + 100,
        )
        return train
    if task == "composition":
        train, _ = make_composition_splits(model.config)
        return train
    if task == "language":
        train, _ = make_language_splits(model.config)
        return train
    raise ValueError("unknown task")


def _task_loss(task: str, model, train, indices: torch.Tensor, device: torch.device):
    if task == "condition":
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        candidates = train.candidates[indices].to(device)
        targets = train.targets[indices].to(device)
        logits = model(initial_values, operations, candidates)
        return F.cross_entropy(logits.flatten(0, 1), targets.flatten())

    if task == "composition":
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        predicted = model(initial_values, operations, operands)
        target_values = targets.to(dtype=predicted.dtype) / float(model.config.state_scale)
        return F.mse_loss(predicted, target_values)

    if task == "language":
        tokens = train.tokens[indices].to(device)
        tasks = train.tasks[indices].to(device)
        targets = train.targets[indices].to(device)
        logits = model(tokens, tasks)
        return F.cross_entropy(logits, targets)

    raise ValueError("unknown task")


def _structure_snapshot(initializations: CompressedModuleInitializations) -> dict:
    return {
        "up_codes": np.stack([item.codes for item in initializations.up.encoded_weights], axis=0),
        "down_codes": np.stack([item.codes for item in initializations.down.encoded_weights], axis=0),
        "up_indices": tuple(item.correction_indices.copy() for item in initializations.up.encoded_weights),
        "down_indices": tuple(item.correction_indices.copy() for item in initializations.down.encoded_weights),
        "up_accounting": initializations.up.accounting,
        "down_accounting": initializations.down.accounting,
    }


def _assert_structure_unchanged(before: dict, after: CompressedModuleInitializations) -> None:
    after_up_codes = np.stack([item.codes for item in after.up.encoded_weights], axis=0)
    after_down_codes = np.stack([item.codes for item in after.down.encoded_weights], axis=0)
    if not np.array_equal(before["up_codes"], after_up_codes):
        raise RuntimeError("fresh-seed task tuning changed up codes")
    if not np.array_equal(before["down_codes"], after_down_codes):
        raise RuntimeError("fresh-seed task tuning changed down codes")
    for expected, item in zip(before["up_indices"], after.up.encoded_weights):
        if not np.array_equal(expected, item.correction_indices):
            raise RuntimeError("fresh-seed task tuning changed up correction coordinates")
    for expected, item in zip(before["down_indices"], after.down.encoded_weights):
        if not np.array_equal(expected, item.correction_indices):
            raise RuntimeError("fresh-seed task tuning changed down correction coordinates")
    if before["up_accounting"] != after.up.accounting:
        raise RuntimeError("fresh-seed task tuning changed up payload accounting")
    if before["down_accounting"] != after.down.accounting:
        raise RuntimeError("fresh-seed task tuning changed down payload accounting")


def run_one(
    task: str,
    seed: int,
    *,
    device: str | torch.device = "cpu",
) -> dict:
    if task not in TASKS:
        raise ValueError("unknown task")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if seed in EXPLORATORY_SEEDS:
        raise ValueError("C11 requires a seed not used by exploratory C7-C10 work")
    device = torch.device(device)
    spec = TUNING_SPECS[task]

    model, validation, evaluator, score_name = _train_high_precision(task, seed, device)
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained model core must remain HighPrecisionFixedRoutingCore")
    source_core = model.core
    high_score = float(evaluator(model, validation)[score_name])

    initializations, diagnostics = _initializations_from_core(
        source_core, DEFAULT_PROFILE, device=device
    )
    structure = _structure_snapshot(initializations)

    tuned_model = copy.deepcopy(model)
    tunable_core = TaskTunableCompressedCore(source_core, initializations).to(device)
    tuned_model.core = tunable_core
    tuned_model = tuned_model.to(device)
    _freeze_except_compressed(tuned_model, tunable_core)
    pre_score = float(evaluator(tuned_model, validation)[score_name])

    train = _training_examples(task, tuned_model, seed)
    optimizer = torch.optim.AdamW(
        tunable_core.compressed_trainable_parameters(),
        lr=float(spec["learning_rate"]),
        weight_decay=0.0,
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    tuned_model.train()
    for _ in range(int(spec["steps"])):
        indices = torch.randint(
            train.size,
            (int(spec["batch_size"]),),
            generator=sampler,
        )
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, tuned_model, train, indices, device)
        if not torch.isfinite(loss):
            raise ValueError("fresh-seed task-aware tuning produced non-finite loss")
        loss.backward()
        optimizer.step()

    post_metrics = evaluator(tuned_model, validation)
    post_score = float(post_metrics[score_name])
    exported = tunable_core.export_initializations()
    _assert_structure_unchanged(structure, exported)

    direct_model = copy.deepcopy(model)
    direct_model.core = CompressedFixedRoutingCore(source_core, exported).to(device)
    direct_model = direct_model.to(device)
    direct_metrics = evaluator(direct_model, validation)
    direct_score = float(direct_metrics[score_name])
    direct_gap = direct_score - post_score

    dense_bytes = (
        exported.up.accounting.dense_float32_bytes
        + exported.down.accounting.dense_float32_bytes
    )
    encoded_bytes = (
        exported.up.accounting.estimated_encoded_payload_bytes
        + exported.down.accounting.estimated_encoded_payload_bytes
    )
    return {
        "task": task,
        "seed": seed,
        "score_name": score_name,
        "high_precision_score": high_score,
        "pre_task_tuning_score": pre_score,
        "post_task_tuning_score": post_score,
        "direct_export_score": direct_score,
        "direct_export_score_gap": direct_gap,
        "pre_delta": pre_score - high_score,
        "post_delta": post_score - high_score,
        "recovered_score": post_score - pre_score,
        "module_payload_ratio": encoded_bytes / dense_bytes,
        "max_observed_abs_correction": _max_abs_correction(tunable_core),
        "payload_unchanged": True,
        "codes_unchanged": True,
        "correction_coordinates_unchanged": True,
        "tuning_steps": int(spec["steps"]),
        "tuning_learning_rate": float(spec["learning_rate"]),
        "tuning_batch_size": int(spec["batch_size"]),
    }


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    tasks: dict[str, dict] = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        if not rows:
            continue
        tasks[task] = {
            "runs": len(rows),
            "mean_high_precision_score": sum(float(row["high_precision_score"]) for row in rows) / len(rows),
            "mean_pre_task_tuning_score": sum(float(row["pre_task_tuning_score"]) for row in rows) / len(rows),
            "mean_post_task_tuning_score": sum(float(row["post_task_tuning_score"]) for row in rows) / len(rows),
            "min_post_task_tuning_score": min(float(row["post_task_tuning_score"]) for row in rows),
            "worst_post_delta": min(float(row["post_delta"]) for row in rows),
            "mean_recovered_score": sum(float(row["recovered_score"]) for row in rows) / len(rows),
            "mean_module_payload_ratio": sum(float(row["module_payload_ratio"]) for row in rows) / len(rows),
            "max_observed_abs_correction": max(float(row["max_observed_abs_correction"]) for row in rows),
            "max_abs_direct_export_score_gap": max(abs(float(row["direct_export_score_gap"])) for row in rows),
            "all_payload_unchanged": all(bool(row["payload_unchanged"]) for row in rows),
            "all_codes_unchanged": all(bool(row["codes_unchanged"]) for row in rows),
            "all_correction_coordinates_unchanged": all(bool(row["correction_coordinates_unchanged"]) for row in rows),
        }
    return {"tasks": tasks}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = FRESH_SEEDS,
    task_names: tuple[str, ...] = TASKS,
    device: str | torch.device = "cpu",
) -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(
        type(seed) is not int or seed < 0 for seed in seeds
    ):
        raise ValueError("seeds must be distinct nonnegative integers")
    if any(seed in EXPLORATORY_SEEDS for seed in seeds):
        raise ValueError("C11 seeds must be disjoint from exploratory seeds")
    if not task_names or len(set(task_names)) != len(task_names) or any(
        task not in TASKS for task in task_names
    ):
        raise ValueError("invalid task_names")

    records: list[dict] = []
    total = len(seeds) * len(task_names)
    completed = 0
    for task in task_names:
        for seed in seeds:
            print(
                f"[gate-c-revalidate] start task={task} seed={seed} ({completed + 1}/{total})",
                file=sys.stderr,
                flush=True,
            )
            record = run_one(task, seed, device=device)
            records.append(record)
            completed += 1
            print(
                f"[gate-c-revalidate] done task={task} seed={seed} "
                f"pre={record['pre_task_tuning_score']:.6f} "
                f"post={record['post_task_tuning_score']:.6f} "
                f"direct={record['direct_export_score']:.6f}",
                file=sys.stderr,
                flush=True,
            )
    return {
        "schema": "fold-v05-gate-c-task-aware-revalidation-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "exploratory_seeds": list(EXPLORATORY_SEEDS),
        "task_names": list(task_names),
        "profile": "high_fidelity_fixed_after_c10",
        "records": records,
        "summary": summarize(records),
        "fresh_seed_revalidation": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(FRESH_SEEDS))
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
