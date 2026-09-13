"""C62: cross-task multi-seed robustness for task-aware shared-basis routed weights.

C60/C61 established that the composition task can recover dense validation quality
using the GPU-friendly shared-basis family with rank scaled as width/16. C62 asks
whether that result generalizes across the three existing Gate-B task families
rather than being composition-specific.

For each task and seed:

1. train the high-precision V5-B model from scratch with the original Gate-B
   schedule;
2. choose rank = max(1, width // 16), yielding rank1 at width16 and rank2 at
   width32;
3. initialize shared-basis routed Up/Down factors from the same SVD fit used by
   C59-C61;
4. freeze every non-factor parameter;
5. tune only routed shared-basis factors with the task's native loss;
6. compare post-recovery validation score against that seed's dense reference.

The rank rule keeps combined routed Up/Down weight storage at 57.03125% of two
independent dense routed module weights for the current hidden_mult=2/modules=2
Gate-B tasks.

This remains a quality/robustness diagnostic. C58 covers large-width factorized
runtime scaling. Production runtime is not modified.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.condition_task import evaluate_condition
from fold_lm.v05.composition_task import evaluate_composition
from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import (
    DEFAULT_SEEDS,
    _build_condition,
    _build_composition,
    _build_language,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import (
    TaskTunableSharedBasisCore,
    _freeze_except_factors,
    _score,
    _storage,
)


EXPERIMENT_ID = "C62-shared-basis-cross-task-multiseed"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
TASKS = ("condition", "composition", "language")
FACTOR_LR = 0.002
TARGET_STORAGE_RATIO = 0.5703125

TASK_SPECS = {
    "condition": {
        "dense_steps": 260,
        "dense_lr": 0.01,
        "factor_steps": 260,
        "batch_size": 32,
        "score_name": "trajectory_exact_accuracy",
    },
    "composition": {
        "dense_steps": 300,
        "dense_lr": 0.005,
        "factor_steps": 300,
        "batch_size": 64,
        "score_name": "trajectory_exact_accuracy",
    },
    "language": {
        "dense_steps": 600,
        "dense_lr": 0.01,
        "factor_steps": 600,
        "batch_size": 24,
        "score_name": "accuracy",
    },
}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _progress_marks(steps: int) -> tuple[int, ...]:
    marks = {max(1, int(round(steps * fraction))) for fraction in (0.25, 0.5, 0.75, 1.0)}
    return tuple(sorted(marks))


def _build_task(task: str, seed: int, device: torch.device):
    if task == "condition":
        config, model, train, validation = _build_condition(seed, "v5b", device)
        return config, model, train, validation, evaluate_condition
    if task == "composition":
        config, model, train, validation = _build_composition(seed, "v5b", device)
        return config, model, train, validation, evaluate_composition
    if task == "language":
        config, model, train, validation = _build_language(seed, "v5b", device)
        return config, model, train, validation, evaluate_language
    raise ValueError(f"unknown C62 task: {task}")


def _task_loss(task: str, model, train, indices: torch.Tensor, device: torch.device) -> torch.Tensor:
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
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(
            model.config.state_scale
        )
        predicted = model(initial_values, operations, operands)
        return F.mse_loss(predicted, target_values)

    if task == "language":
        tokens = train.tokens[indices].to(device)
        tasks = train.tasks[indices].to(device)
        targets = train.targets[indices].to(device)
        logits = model(tokens, tasks)
        return F.cross_entropy(logits, targets)

    raise ValueError(f"unknown C62 task: {task}")


def _train_dense(task: str, seed: int, device: torch.device):
    spec = TASK_SPECS[task]
    config, model, train, validation, evaluator = _build_task(task, seed, device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(spec["dense_lr"]), weight_decay=0.0
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    batch_size = int(spec["batch_size"])
    steps = int(spec["dense_steps"])
    marks = _progress_marks(steps)
    model.train()
    initial_loss = None
    final_loss = None

    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C62 task={task} seed={seed} dense training produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in marks:
            print(
                f"[C62] task={task} seed={seed} dense step={step}/{steps} "
                f"loss={loss_value:.8f}",
                flush=True,
            )

    return (
        config,
        model,
        train,
        validation,
        evaluator,
        float(initial_loss),
        float(final_loss),
    )


def _recover_factors(
    *,
    task: str,
    seed: int,
    dense_model,
    train,
    validation,
    evaluator,
    device: torch.device,
) -> dict:
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C62 dense core must remain HighPrecisionFixedRoutingCore")
    core = dense_model.core
    if core.config.modules != 2 or core.config.hidden_mult != 2:
        raise RuntimeError("C62 expects modules=2 and hidden_mult=2")

    width = int(core.config.width)
    hidden = width * int(core.config.hidden_mult)
    rank = max(1, width // 16)
    storage = _storage(width=width, hidden=hidden, rank=rank)
    ratio = float(storage["representation_weight_ratio"])
    if abs(ratio - TARGET_STORAGE_RATIO) > 1e-12:
        raise RuntimeError(
            f"C62 unexpected storage ratio task={task}: width={width} rank={rank} ratio={ratio}"
        )

    score_name = str(TASK_SPECS[task]["score_name"])
    dense_score = float(evaluator(dense_model, validation)[score_name])
    candidate = copy.deepcopy(dense_model)
    tunable_core = TaskTunableSharedBasisCore(core, rank).to(device)
    candidate.core = tunable_core
    candidate = candidate.to(device)
    _freeze_except_factors(candidate, tunable_core)

    pre_score = _score(candidate, evaluator, validation, score_name)
    optimizer = torch.optim.AdamW(
        tunable_core.factor_parameters(), lr=FACTOR_LR, weight_decay=0.0
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    batch_size = int(TASK_SPECS[task]["batch_size"])
    steps = int(TASK_SPECS[task]["factor_steps"])
    marks = _progress_marks(steps)
    candidate.train()
    initial_loss = None
    final_loss = None

    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, candidate, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C62 task={task} seed={seed} factor recovery produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in marks:
            print(
                f"[C62] task={task} seed={seed} rank={rank} "
                f"factor step={step}/{steps} loss={loss_value:.8f}",
                flush=True,
            )

    post_score = _score(candidate, evaluator, validation, score_name)
    return {
        "task": task,
        "seed": seed,
        "width": width,
        "hidden_width": hidden,
        "rank": rank,
        **storage,
        "score_name": score_name,
        "dense_score": dense_score,
        "pre_task_tuning_score": pre_score,
        "post_task_tuning_score": post_score,
        "pre_delta": pre_score - dense_score,
        "post_delta": post_score - dense_score,
        "recovered_score": post_score - pre_score,
        "factor_initial_training_loss": float(initial_loss),
        "factor_final_training_loss": float(final_loss),
        "factor_steps": steps,
        "factor_learning_rate": FACTOR_LR,
        "batch_size": batch_size,
    }


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _summarize(records: list[dict]) -> dict:
    tasks: dict[str, dict] = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        if not rows:
            raise RuntimeError(f"C62 missing task records: {task}")
        dense_scores = [float(row["dense_score"]) for row in rows]
        pre_scores = [float(row["pre_task_tuning_score"]) for row in rows]
        post_scores = [float(row["post_task_tuning_score"]) for row in rows]
        deltas = [float(row["post_delta"]) for row in rows]
        ratios = [float(row["representation_weight_ratio"]) for row in rows]
        tasks[task] = {
            "runs": len(rows),
            "dense_score": _stats(dense_scores),
            "pre_task_tuning_score": _stats(pre_scores),
            "post_task_tuning_score": _stats(post_scores),
            "post_delta": _stats(deltas),
            "representation_weight_ratio": _stats(ratios),
            "all_post_scores_match_dense": all(abs(delta) <= 1e-7 for delta in deltas),
        }
    return {
        "tasks": tasks,
        "all_tasks_all_seeds_match_dense": all(
            bool(tasks[task]["all_post_scores_match_dense"]) for task in TASKS
        ),
    }


def run(
    *,
    protected_result_path: Path,
    c61_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C62 requires CUDA")

    c61 = json.loads(c61_summary_path.read_text(encoding="utf-8"))
    if c61.get("experiment_id") != "C61-shared-basis-rank2-multiseed":
        raise RuntimeError("C62 requires accepted C61 summary")
    if c61.get("status") != "PASS":
        raise RuntimeError("C61 summary is not PASS")
    if not bool(c61.get("summary", {}).get("all_rank2_post_scores_match_dense", False)):
        raise RuntimeError("C62 requires C61 all-seed composition recovery")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records: list[dict] = []
    total = len(TASKS) * len(SEEDS)
    completed = 0

    for task in TASKS:
        for seed in SEEDS:
            print(
                f"[C62] task={task} seed={seed} start ({completed + 1}/{total})",
                flush=True,
            )
            (
                _config,
                dense_model,
                train,
                validation,
                evaluator,
                dense_initial_loss,
                dense_final_loss,
            ) = _train_dense(task, seed, device)
            record = _recover_factors(
                task=task,
                seed=seed,
                dense_model=dense_model,
                train=train,
                validation=validation,
                evaluator=evaluator,
                device=device,
            )
            record["dense_initial_training_loss"] = dense_initial_loss
            record["dense_final_training_loss"] = dense_final_loss
            records.append(record)
            completed += 1
            print(
                f"[C62] task={task} seed={seed} done ({completed}/{total}) "
                f"rank={record['rank']} dense={record['dense_score']:.6f} "
                f"pre={record['pre_task_tuning_score']:.6f} "
                f"post={record['post_task_tuning_score']:.6f} "
                f"storage={record['representation_weight_ratio']:.6f}",
                flush=True,
            )
            del dense_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C62")

    summary = _summarize(records)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "shared-basis task-aware recovery robustness across Gate-B task families and seeds",
        "tasks": list(TASKS),
        "seeds": list(SEEDS),
        "rank_rule": "max(1, width // 16)",
        "target_representation_weight_ratio": TARGET_STORAGE_RATIO,
        "factor_learning_rate": FACTOR_LR,
        "task_specs": TASK_SPECS,
        "records": records,
        "summary": summary,
        "C61_summary_sha256": _sha256(c61_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "independent_dense_then_scaled_rank_factor_recovery",
        "non_factor_parameters_frozen_during_recovery": True,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C62 covers the three existing small Gate-B tasks, not broad language/model scaling quality",
            "three deterministic seeds per task are a robustness check, not exhaustive generalization",
            "factor recovery uses bounded task-aware steps with fixed learning rate 0.002",
            "C62 does not measure factorized inference runtime; C58 covers large-width runtime scaling",
            "C62 alone cannot establish Gate C pass",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c61-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c61_summary_path=args.c61_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C62 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
