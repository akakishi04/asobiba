"""V5-C post-training compression quality benchmark.

Train the same high-precision V5-B task models used by the Gate-B controlled
comparison, compress only the module-specific MLP Linear weights, then compare
held-out task quality and direct runtime on the exact same validation split.

The default profile is intentionally one fixed *candidate*, not a Gate-C claim:

    dense V5-B -> codebook initialization -> fixed-code continuous tuning
               -> block-code reassignment -> fixed-code continuous tuning

Capacity reported here is only the estimated payload for the compressed module
Linear weights.  It is not whole-model size and it is not serialized file size.
A real serializer and resident-byte accounting remain separate Gate-C work.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import json
import math
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    CompressedModuleInitializations,
    ModuleCompressionConfig,
)
from fold_lm.v05.compression_init import CompressionInitialization, initialize_from_dense_weights
from fold_lm.v05.compression_reassignment import reassign_block_codes
from fold_lm.v05.compression_tuning import fit_fixed_codes_to_dense
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import (
    DEFAULT_SEEDS,
    _build_composition,
    _build_condition,
    _build_language,
)
from fold_lm.v05.composition_task import evaluate_composition
from fold_lm.v05.condition_task import evaluate_condition
from fold_lm.v05.language_task import evaluate_language


TASKS = ("condition", "composition", "language")


@dataclass(frozen=True)
class CompressionProfile:
    """One explicit bounded V5-C candidate used by the first task benchmark."""

    block_rows: int = 4
    block_cols: int = 4
    codebook_count: int = 2
    entries_per_codebook: int = 4
    correction_fraction: float = 0.015625  # <= 1.5625% scalar entries/module.
    max_abs_correction: float = 0.10
    initial_tuning_steps: int = 80
    post_reassignment_tuning_steps: int = 40
    reassignment_sweeps: int = 2
    tuning_learning_rate: float = 0.01

    def __post_init__(self) -> None:
        for name in ("block_rows", "block_cols", "codebook_count", "entries_per_codebook"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            not isinstance(self.correction_fraction, (int, float))
            or not math.isfinite(float(self.correction_fraction))
            or not 0.0 <= float(self.correction_fraction) <= 0.05
        ):
            raise ValueError("correction_fraction must be finite and in [0, 0.05]")
        if (
            not isinstance(self.max_abs_correction, (int, float))
            or not math.isfinite(float(self.max_abs_correction))
            or not 0.0 <= float(self.max_abs_correction) <= 0.25
        ):
            raise ValueError("max_abs_correction must be finite and in [0, 0.25]")
        for name in ("initial_tuning_steps", "post_reassignment_tuning_steps", "reassignment_sweeps"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            not isinstance(self.tuning_learning_rate, (int, float))
            or not math.isfinite(float(self.tuning_learning_rate))
            or self.tuning_learning_rate <= 0
        ):
            raise ValueError("tuning_learning_rate must be positive and finite")


DEFAULT_PROFILE = CompressionProfile()


@dataclass(frozen=True)
class RoleCompressionDiagnostics:
    dense_float32_bytes: int
    encoded_payload_bytes: int
    payload_ratio: float
    initial_mse: float
    after_first_tuning_mse: float
    after_reassignment_mse: float
    final_mse: float
    changed_code_count: int
    correction_nnz: int
    correction_density: float
    max_observed_abs_correction: float

    def __post_init__(self) -> None:
        if type(self.dense_float32_bytes) is not int or self.dense_float32_bytes <= 0:
            raise ValueError("dense_float32_bytes must be positive")
        if type(self.encoded_payload_bytes) is not int or self.encoded_payload_bytes <= 0:
            raise ValueError("encoded_payload_bytes must be positive")
        for name in (
            "payload_ratio",
            "initial_mse",
            "after_first_tuning_mse",
            "after_reassignment_mse",
            "final_mse",
            "correction_density",
            "max_observed_abs_correction",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if type(self.changed_code_count) is not int or self.changed_code_count < 0:
            raise ValueError("changed_code_count must be nonnegative")
        if type(self.correction_nnz) is not int or self.correction_nnz < 0:
            raise ValueError("correction_nnz must be nonnegative")
        if self.correction_density > 0.05 + 1e-12:
            raise ValueError("correction density exceeds the benchmark hard bound")


def _stack_role_weights(core: HighPrecisionFixedRoutingCore, role: str) -> np.ndarray:
    if not isinstance(core, HighPrecisionFixedRoutingCore):
        raise TypeError("core must be HighPrecisionFixedRoutingCore")
    if role not in ("up", "down"):
        raise ValueError("role must be up or down")
    return np.stack(
        [getattr(module, role).weight.detach().cpu().numpy() for module in core.module_set],
        axis=0,
    ).astype(np.float64, copy=False)


def _reconstruction_mse(weights: np.ndarray, initialization: CompressionInitialization) -> float:
    reconstructed = np.stack([item.materialize() for item in initialization.encoded_weights], axis=0)
    error = np.asarray(weights, dtype=np.float64) - reconstructed
    return float(np.mean(error * error))


def _max_correction_entries(weights: np.ndarray, profile: CompressionProfile) -> int:
    scalars_per_module = int(weights.shape[1] * weights.shape[2])
    if profile.correction_fraction == 0.0:
        return 0
    return min(
        scalars_per_module,
        max(1, int(math.floor(scalars_per_module * profile.correction_fraction))),
    )


def _compress_role(
    weights: np.ndarray,
    profile: CompressionProfile,
    *,
    device: torch.device,
) -> tuple[CompressionInitialization, RoleCompressionDiagnostics]:
    max_entries = _max_correction_entries(weights, profile)
    initial = initialize_from_dense_weights(
        weights,
        block_rows=profile.block_rows,
        block_cols=profile.block_cols,
        codebook_count=profile.codebook_count,
        entries_per_codebook=profile.entries_per_codebook,
        max_correction_entries=max_entries,
        max_abs_correction=profile.max_abs_correction,
    )
    initial_mse = _reconstruction_mse(weights, initial)
    first_tuned = fit_fixed_codes_to_dense(
        weights,
        initial,
        steps=profile.initial_tuning_steps,
        learning_rate=profile.tuning_learning_rate,
        device=device,
    ).initialization
    first_mse = _reconstruction_mse(weights, first_tuned)
    reassigned_result = reassign_block_codes(
        weights,
        first_tuned,
        sweeps=profile.reassignment_sweeps,
    )
    reassigned = reassigned_result.initialization
    reassigned_mse = _reconstruction_mse(weights, reassigned)
    final = fit_fixed_codes_to_dense(
        weights,
        reassigned,
        steps=profile.post_reassignment_tuning_steps,
        learning_rate=profile.tuning_learning_rate,
        device=device,
    ).initialization
    final_mse = _reconstruction_mse(weights, final)

    corrections = [item.correction_values for item in final.encoded_weights]
    correction_nnz = sum(int(values.size) for values in corrections)
    total_scalars = int(weights.shape[0] * weights.shape[1] * weights.shape[2])
    max_abs = max(
        (float(np.max(np.abs(values))) for values in corrections if values.size),
        default=0.0,
    )
    accounting = final.accounting
    diagnostics = RoleCompressionDiagnostics(
        dense_float32_bytes=accounting.dense_float32_bytes,
        encoded_payload_bytes=accounting.estimated_encoded_payload_bytes,
        payload_ratio=accounting.estimated_payload_ratio,
        initial_mse=initial_mse,
        after_first_tuning_mse=first_mse,
        after_reassignment_mse=reassigned_mse,
        final_mse=final_mse,
        changed_code_count=reassigned_result.changed_code_count,
        correction_nnz=correction_nnz,
        correction_density=correction_nnz / total_scalars,
        max_observed_abs_correction=max_abs,
    )
    return final, diagnostics


def compress_trained_core(
    core: HighPrecisionFixedRoutingCore,
    profile: CompressionProfile = DEFAULT_PROFILE,
    *,
    device: str | torch.device = "cpu",
) -> tuple[CompressedFixedRoutingCore, dict]:
    if not isinstance(core, HighPrecisionFixedRoutingCore):
        raise TypeError("core must be HighPrecisionFixedRoutingCore")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    device = torch.device(device)
    up_weights = _stack_role_weights(core, "up")
    down_weights = _stack_role_weights(core, "down")
    up, up_diag = _compress_role(up_weights, profile, device=device)
    down, down_diag = _compress_role(down_weights, profile, device=device)
    initializations = CompressedModuleInitializations(up=up, down=down)
    compressed = CompressedFixedRoutingCore(core, initializations).to(device)
    dense_bytes = up_diag.dense_float32_bytes + down_diag.dense_float32_bytes
    encoded_bytes = up_diag.encoded_payload_bytes + down_diag.encoded_payload_bytes
    return compressed, {
        "up": up_diag.__dict__,
        "down": down_diag.__dict__,
        "module_dense_float32_bytes": dense_bytes,
        "module_estimated_encoded_payload_bytes": encoded_bytes,
        "module_payload_ratio": encoded_bytes / dense_bytes,
        "correction_nnz": up_diag.correction_nnz + down_diag.correction_nnz,
        "max_observed_abs_correction": max(
            up_diag.max_observed_abs_correction,
            down_diag.max_observed_abs_correction,
        ),
    }


def _train_high_precision(task: str, seed: int, device: torch.device):
    if task == "condition":
        config, model, train, validation = _build_condition(seed, "v5b", device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.0)
        sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
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
            loss.backward()
            optimizer.step()
        return model, validation, evaluate_condition, "trajectory_exact_accuracy"

    if task == "composition":
        config, model, train, validation = _build_composition(seed, "v5b", device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.0)
        sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
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
            loss.backward()
            optimizer.step()
        return model, validation, evaluate_composition, "trajectory_exact_accuracy"

    if task == "language":
        _config, model, train, validation = _build_language(seed, "v5b", device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.0)
        sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
        model.train()
        for _ in range(600):
            indices = torch.randint(train.size, (24,), generator=sampler)
            tokens = train.tokens[indices].to(device)
            tasks = train.tasks[indices].to(device)
            targets = train.targets[indices].to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(tokens, tasks)
            loss = F.cross_entropy(logits, targets)
            loss.backward()
            optimizer.step()
        return model, validation, evaluate_language, "accuracy"

    raise ValueError(f"unknown task: {task}")


def _timed_eval(evaluator, model, validation, *, repeats: int = 3) -> tuple[dict, float]:
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")
    metrics = evaluator(model, validation)
    elapsed: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        metrics = evaluator(model, validation)
        elapsed.append(time.perf_counter() - started)
    return metrics, sum(elapsed) / len(elapsed)


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
    high_metrics, high_eval_seconds = _timed_eval(evaluator, model, validation)
    source_core = model.core
    if not isinstance(source_core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained model core must remain HighPrecisionFixedRoutingCore")
    compressed_core, compression = compress_trained_core(source_core, profile, device=device)
    compressed_model = copy.deepcopy(model)
    compressed_model.core = compressed_core
    compressed_model = compressed_model.to(device)
    compressed_metrics, compressed_eval_seconds = _timed_eval(
        evaluator, compressed_model, validation
    )
    high_score = float(high_metrics[score_name])
    compressed_score = float(compressed_metrics[score_name])
    return {
        "task": task,
        "seed": seed,
        "score_name": score_name,
        "high_precision_metrics": high_metrics,
        "compressed_metrics": compressed_metrics,
        "high_precision_score": high_score,
        "compressed_score": compressed_score,
        "score_delta": compressed_score - high_score,
        "high_precision_eval_seconds": high_eval_seconds,
        "compressed_eval_seconds": compressed_eval_seconds,
        "runtime_ratio": compressed_eval_seconds / high_eval_seconds,
        "compression": compression,
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
            "min_high_precision_score": min(float(row["high_precision_score"]) for row in rows),
            "mean_compressed_score": sum(float(row["compressed_score"]) for row in rows) / len(rows),
            "min_compressed_score": min(float(row["compressed_score"]) for row in rows),
            "mean_score_delta": sum(float(row["score_delta"]) for row in rows) / len(rows),
            "worst_score_delta": min(float(row["score_delta"]) for row in rows),
            "mean_module_payload_ratio": sum(float(row["compression"]["module_payload_ratio"]) for row in rows) / len(rows),
            "mean_runtime_ratio": sum(float(row["runtime_ratio"]) for row in rows) / len(rows),
            "max_observed_abs_correction": max(float(row["compression"]["max_observed_abs_correction"]) for row in rows),
        }
    return {"tasks": tasks}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    task_names: tuple[str, ...] = TASKS,
    profile: CompressionProfile = DEFAULT_PROFILE,
    device: str | torch.device = "cpu",
) -> dict:
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("seeds must contain at least two distinct nonnegative integers")
    if not task_names or len(set(task_names)) != len(task_names) or any(task not in TASKS for task in task_names):
        raise ValueError("invalid task_names")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    records: list[dict] = []
    total = len(seeds) * len(task_names)
    completed = 0
    started = time.perf_counter()
    for task in task_names:
        for seed in seeds:
            print(
                f"[gate-c-quality] start task={task} seed={seed} ({completed + 1}/{total})",
                file=sys.stderr,
                flush=True,
            )
            row_started = time.perf_counter()
            record = run_one(task, seed, profile=profile, device=device)
            record["elapsed_seconds"] = time.perf_counter() - row_started
            records.append(record)
            completed += 1
            print(
                f"[gate-c-quality] done task={task} seed={seed} "
                f"high={record['high_precision_score']:.6f} "
                f"compressed={record['compressed_score']:.6f} "
                f"payload={record['compression']['module_payload_ratio']:.4f} "
                f"runtime={record['runtime_ratio']:.2f}x",
                file=sys.stderr,
                flush=True,
            )
    return {
        "schema": "fold-v05-gate-c-task-quality-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "task_names": list(task_names),
        "profile": profile.__dict__,
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
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        task_names=tuple(args.tasks),
        profile=DEFAULT_PROFILE,
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
