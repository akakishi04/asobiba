"""V5-C runtime benchmark for dense, literal-direct, and compact-vectorized cores.

This benchmark rebuilds one fixed fresh-seed task-aware compression candidate per
selected task, verifies quality parity, then times end-to-end validation forwards
on one requested device. Progress is written to stderr so JSON stdout may still
be redirected to a file.

The progress line reports completed units, percent, elapsed wall time, and a
simple ETA estimated from completed units. It is intentionally approximate: the
high-precision training, task-aware tuning, and timing phases have different
costs.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import sys
import time

import torch

from fold_lm.v05.compact_runtime import CompactVectorizedFixedRoutingCore
from fold_lm.v05.compressed_runtime import CompressedFixedRoutingCore
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_task_aware_recovery import (
    DEFAULT_PROFILE,
    TaskTunableCompressedCore,
    _freeze_except_compressed,
    _initializations_from_core,
)
from fold_lm.v05_benchmarks.gate_c_task_aware_revalidation import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
    TASKS,
    TUNING_SPECS,
    _task_loss,
    _training_examples,
)
from fold_lm.v05_benchmarks.gate_c_task_quality import _train_high_precision


VARIANTS = ("dense", "direct", "compact")
DEFAULT_RUNTIME_SEEDS = (FRESH_SEEDS[0],)
_TUNING_PROGRESS_MARKS = 4


def _format_duration(seconds: float) -> str:
    if not isinstance(seconds, (int, float)) or not math.isfinite(float(seconds)) or seconds < 0:
        raise ValueError("seconds must be finite and nonnegative")
    seconds = float(seconds)
    if seconds < 60.0:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(seconds, 60.0)
    if minutes < 60.0:
        return f"{int(minutes)}m{sec:04.1f}s"
    hours, minute = divmod(minutes, 60.0)
    return f"{int(hours)}h{int(minute):02d}m{sec:04.1f}s"


def format_progress_line(
    completed: int,
    total: int,
    elapsed_seconds: float,
    label: str,
) -> str:
    if type(completed) is not int or type(total) is not int or total <= 0:
        raise ValueError("completed/total must be integer progress values")
    if completed < 0 or completed > total:
        raise ValueError("completed must be in [0, total]")
    if not isinstance(label, str) or not label:
        raise ValueError("label must be non-empty")
    elapsed = float(elapsed_seconds)
    if not math.isfinite(elapsed) or elapsed < 0.0:
        raise ValueError("elapsed_seconds must be finite and nonnegative")
    percent = 100.0 * completed / total
    if completed == 0:
        eta = "--"
    else:
        eta_seconds = elapsed / completed * (total - completed)
        eta = _format_duration(eta_seconds)
    return (
        f"[gate-c-runtime] {completed}/{total} ({percent:5.1f}%) "
        f"elapsed={_format_duration(elapsed)} eta={eta} {label}"
    )


class _Progress:
    def __init__(self, total: int) -> None:
        if type(total) is not int or total <= 0:
            raise ValueError("total must be positive")
        self.total = total
        self.completed = 0
        self.started = time.perf_counter()

    def _emit(self, label: str) -> None:
        elapsed = time.perf_counter() - self.started
        print(
            format_progress_line(self.completed, self.total, elapsed, label),
            file=sys.stderr,
            flush=True,
        )

    def note(self, label: str) -> None:
        self._emit(label)

    def advance(self, label: str) -> None:
        if self.completed >= self.total:
            raise RuntimeError("progress exceeded total")
        self.completed += 1
        self._emit(label)



def _validated_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA runtime benchmark requested but CUDA is unavailable")
    return result


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _prepared_validation(task: str, validation, device: torch.device) -> tuple[torch.Tensor, ...]:
    if task == "condition":
        return (
            validation.initial_values.to(device),
            validation.operations.to(device),
            validation.candidates.to(device),
        )
    if task == "composition":
        return (
            validation.initial_values.to(device),
            validation.operations.to(device),
            validation.operands.to(device),
        )
    if task == "language":
        return validation.tokens.to(device), validation.tasks.to(device)
    raise ValueError("unknown task")


def _forward_prepared(task: str, model, prepared: tuple[torch.Tensor, ...]) -> torch.Tensor:
    if task in TASKS:
        return model(*prepared)
    raise ValueError("unknown task")


@torch.inference_mode()
def measure_forward(
    task: str,
    model,
    prepared: tuple[torch.Tensor, ...],
    *,
    warmup: int,
    repeats: int,
    device: torch.device,
) -> dict:
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")
    model.eval()
    for _ in range(warmup):
        _forward_prepared(task, model, prepared)
    _sync(device)

    samples: list[float] = []
    for _ in range(repeats):
        _sync(device)
        started = time.perf_counter()
        _forward_prepared(task, model, prepared)
        _sync(device)
        samples.append(time.perf_counter() - started)

    ordered = sorted(samples)
    p90_index = max(0, min(len(ordered) - 1, math.ceil(0.90 * len(ordered)) - 1))
    return {
        "repeats": repeats,
        "mean_seconds": sum(samples) / len(samples),
        "median_seconds": statistics.median(samples),
        "p90_seconds": ordered[p90_index],
        "min_seconds": min(samples),
        "max_seconds": max(samples),
    }


def _build_fixed_candidate(
    task: str,
    seed: int,
    device: torch.device,
    progress: _Progress,
):
    progress.note(f"task={task} seed={seed} high-precision training")
    model, validation, evaluator, score_name = _train_high_precision(task, seed, device)
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained model core must remain HighPrecisionFixedRoutingCore")
    source_core = model.core
    high_score = float(evaluator(model, validation)[score_name])
    progress.advance(f"task={task} high-precision ready score={high_score:.6f}")

    initializations, _diagnostics = _initializations_from_core(
        source_core, DEFAULT_PROFILE, device=device
    )
    tuned_model = copy.deepcopy(model)
    tunable_core = TaskTunableCompressedCore(source_core, initializations).to(device)
    tuned_model.core = tunable_core
    tuned_model = tuned_model.to(device)
    _freeze_except_compressed(tuned_model, tunable_core)

    train = _training_examples(task, tuned_model, seed)
    spec = TUNING_SPECS[task]
    steps = int(spec["steps"])
    optimizer = torch.optim.AdamW(
        tunable_core.compressed_trainable_parameters(),
        lr=float(spec["learning_rate"]),
        weight_decay=0.0,
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    marks = sorted({max(1, math.ceil(steps * index / _TUNING_PROGRESS_MARKS)) for index in range(1, _TUNING_PROGRESS_MARKS + 1)})
    tuned_model.train()
    for step in range(1, steps + 1):
        indices = torch.randint(
            train.size,
            (int(spec["batch_size"]),),
            generator=sampler,
        )
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, tuned_model, train, indices, device)
        if not torch.isfinite(loss):
            raise ValueError("runtime candidate task tuning produced non-finite loss")
        loss.backward()
        optimizer.step()
        if step in marks:
            progress.advance(f"task={task} task-aware tuning {step}/{steps}")

    exported = tunable_core.export_initializations()
    tuned_score = float(evaluator(tuned_model, validation)[score_name])

    direct_model = copy.deepcopy(model)
    direct_model.core = CompressedFixedRoutingCore(source_core, exported).to(device)
    direct_model = direct_model.to(device)
    compact_model = copy.deepcopy(model)
    compact_model.core = CompactVectorizedFixedRoutingCore(source_core, exported).to(device)
    compact_model = compact_model.to(device)

    direct_score = float(evaluator(direct_model, validation)[score_name])
    compact_score = float(evaluator(compact_model, validation)[score_name])
    if abs(direct_score - tuned_score) > 1e-7 or abs(compact_score - tuned_score) > 1e-7:
        raise RuntimeError("runtime variants changed task score after fixed-candidate export")

    return {
        "dense": model,
        "direct": direct_model,
        "compact": compact_model,
    }, validation, score_name, {
        "dense": high_score,
        "direct": direct_score,
        "compact": compact_score,
        "task_aware_materialized": tuned_score,
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
        dense_mean = sum(float(row["timings"]["dense"]["mean_seconds"]) for row in rows) / len(rows)
        for variant in VARIANTS:
            mean_seconds = sum(float(row["timings"][variant]["mean_seconds"]) for row in rows) / len(rows)
            variant_summary[variant] = {
                "mean_seconds": mean_seconds,
                "mean_milliseconds": mean_seconds * 1000.0,
                "runtime_ratio_vs_dense": mean_seconds / dense_mean,
                "mean_score": sum(float(row["scores"][variant]) for row in rows) / len(rows),
            }
        tasks[task] = {
            "runs": len(rows),
            "variants": variant_summary,
            "max_abs_direct_compact_score_gap": max(
                abs(float(row["scores"]["direct"]) - float(row["scores"]["compact"]))
                for row in rows
            ),
        }
    return {"tasks": tasks}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_RUNTIME_SEEDS,
    task_names: tuple[str, ...] = TASKS,
    device: str | torch.device = "cpu",
    warmup: int = 5,
    repeats: int = 30,
) -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("seeds must be distinct nonnegative integers")
    if any(seed in EXPLORATORY_SEEDS for seed in seeds):
        raise ValueError("runtime benchmark seeds must be disjoint from exploratory seeds")
    if not task_names or len(set(task_names)) != len(task_names) or any(task not in TASKS for task in task_names):
        raise ValueError("invalid task_names")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")

    device = _validated_device(device)
    total_units = len(seeds) * len(task_names) * (1 + _TUNING_PROGRESS_MARKS + len(VARIANTS))
    progress = _Progress(total_units)
    overall_started = time.perf_counter()
    records: list[dict] = []

    for task in task_names:
        for seed in seeds:
            models, validation, score_name, scores = _build_fixed_candidate(
                task, seed, device, progress
            )
            prepared = _prepared_validation(task, validation, device)
            timings: dict[str, dict] = {}
            for variant in VARIANTS:
                progress.note(f"task={task} variant={variant} timing")
                timings[variant] = measure_forward(
                    task,
                    models[variant],
                    prepared,
                    warmup=warmup,
                    repeats=repeats,
                    device=device,
                )
                progress.advance(
                    f"task={task} variant={variant} mean={timings[variant]['mean_seconds'] * 1000.0:.3f}ms"
                )
            records.append(
                {
                    "task": task,
                    "seed": seed,
                    "score_name": score_name,
                    "scores": scores,
                    "timings": timings,
                    "validation_examples": int(validation.size),
                }
            )

    elapsed = time.perf_counter() - overall_started
    if progress.completed != progress.total:
        raise RuntimeError("runtime benchmark progress accounting mismatch")
    progress.note(f"complete total={_format_duration(elapsed)}")

    device_name = "cpu"
    if device.type == "cuda":
        device_name = torch.cuda.get_device_name(device)
    return {
        "schema": "fold-v05-gate-c-runtime-benchmark-v1",
        "device": str(device),
        "device_name": device_name,
        "seeds": list(seeds),
        "task_names": list(task_names),
        "variants": list(VARIANTS),
        "warmup": warmup,
        "repeats": repeats,
        "records": records,
        "summary": summarize(records),
        "elapsed_seconds": elapsed,
        "progress_reporting": "stderr: completed/total, percent, elapsed, approximate ETA",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_RUNTIME_SEEDS))
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        task_names=tuple(args.tasks),
        device=args.device,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
