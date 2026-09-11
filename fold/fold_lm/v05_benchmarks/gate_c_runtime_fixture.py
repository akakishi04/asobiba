"""Reusable V5-C runtime fixtures for fast kernel iteration.

C15 showed that rebuilding the trained/task-aware candidate dominates benchmark
wall time, especially on CUDA.  This module separates candidate preparation from
runtime measurement.  A fixture stores only trusted tensor/primitives:

- task name / seed / task config;
- trained high-precision task-model state_dict on CPU;
- exact serialized C12 compressed module blob;
- reference scores recorded when the fixture was prepared.

Loading reconstructs fresh dense, literal-direct, and compact-vectorized runtime
models on the requested device without re-running training or task-aware tuning.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import time

import torch

from fold_lm.v05.compact_runtime import CompactVectorizedFixedRoutingCore
from fold_lm.v05.compressed_runtime import CompressedFixedRoutingCore
from fold_lm.v05.compression_serialization import (
    deserialize_module_initializations,
    serialize_module_initializations,
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


FIXTURE_SCHEMA = "fold-v05-gate-c-runtime-fixture-v1"
DEFAULT_FIXTURE_SEED = FRESH_SEEDS[0]


def _task_parts(task: str, config_dict: dict):
    if task == "condition":
        config = ConditionTaskConfig(**config_dict)
        return config, ConditionHoldUpdateModel(config), evaluate_condition
    if task == "composition":
        config = CompositionTaskConfig(**config_dict)
        return config, CompositionModel(config), evaluate_composition
    if task == "language":
        config = LanguageTaskConfig(**config_dict)
        return config, ShortByteLanguageModel(config), evaluate_language
    raise ValueError("unknown task")


def _validation_for(task: str, config, seed: int):
    if task == "condition":
        _train, validation = make_condition_splits(
            config,
            train_examples=256,
            validation_examples=128,
            seed=seed + 100,
        )
        return validation
    if task == "composition":
        _train, validation = make_composition_splits(config)
        return validation
    if task == "language":
        _train, validation = make_language_splits(config)
        return validation
    raise ValueError("unknown task")


def _score_name(task: str) -> str:
    if task in ("condition", "composition"):
        return "trajectory_exact_accuracy"
    if task == "language":
        return "accuracy"
    raise ValueError("unknown task")


def _cpu_state_dict(model) -> dict[str, torch.Tensor]:
    return {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }


def save_runtime_fixture(
    path: str | Path,
    *,
    task: str,
    seed: int,
    dense_model,
    compressed_initializations,
    scores: dict[str, float],
) -> Path:
    if task not in TASKS:
        raise ValueError("unknown task")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if seed in EXPLORATORY_SEEDS:
        raise ValueError("runtime fixture seed must be disjoint from exploratory seeds")
    if not hasattr(dense_model, "config") or not isinstance(
        getattr(dense_model, "core", None), HighPrecisionFixedRoutingCore
    ):
        raise TypeError("dense_model must expose the trained high-precision V5-B core")
    if not isinstance(scores, dict) or any(
        name not in scores for name in ("dense", "direct", "compact")
    ):
        raise ValueError("scores must contain dense/direct/compact")
    score_payload: dict[str, float] = {}
    for name in ("dense", "direct", "compact"):
        value = float(scores[name])
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("fixture scores must be finite and nonnegative")
        score_payload[name] = value

    blob = serialize_module_initializations(compressed_initializations)
    blob_tensor = torch.tensor(list(blob), dtype=torch.uint8)
    payload = {
        "schema": FIXTURE_SCHEMA,
        "task": task,
        "seed": seed,
        "config": asdict(dense_model.config),
        "dense_state_dict": _cpu_state_dict(dense_model),
        "compressed_blob": blob_tensor,
        "scores": score_payload,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return destination


def load_runtime_fixture(
    path: str | Path,
    *,
    device: str | torch.device = "cpu",
) -> dict:
    source = Path(path)
    payload = torch.load(source, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("schema") != FIXTURE_SCHEMA:
        raise ValueError("unsupported V5-C runtime fixture schema")
    task = payload.get("task")
    seed = payload.get("seed")
    config_dict = payload.get("config")
    state_dict = payload.get("dense_state_dict")
    blob_tensor = payload.get("compressed_blob")
    scores = payload.get("scores")
    if task not in TASKS or type(seed) is not int or seed < 0:
        raise ValueError("invalid runtime fixture identity")
    if not isinstance(config_dict, dict) or not isinstance(state_dict, dict):
        raise ValueError("invalid runtime fixture model payload")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8 or blob_tensor.ndim != 1:
        raise ValueError("invalid runtime fixture compressed blob")
    if not isinstance(scores, dict):
        raise ValueError("invalid runtime fixture scores")

    config, dense_model, evaluator = _task_parts(task, config_dict)
    dense_model.load_state_dict(state_dict, strict=True)
    device = torch.device(device)
    dense_model = dense_model.to(device)
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("loaded dense fixture core must remain high precision")

    blob = blob_tensor.contiguous().numpy().tobytes()
    compressed = deserialize_module_initializations(blob)
    source_core = dense_model.core

    direct_model = copy.deepcopy(dense_model)
    direct_model.core = CompressedFixedRoutingCore(source_core, compressed).to(device)
    direct_model = direct_model.to(device)

    compact_model = copy.deepcopy(dense_model)
    compact_model.core = CompactVectorizedFixedRoutingCore(source_core, compressed).to(device)
    compact_model = compact_model.to(device)

    validation = _validation_for(task, config, seed)
    return {
        "task": task,
        "seed": seed,
        "config": config,
        "validation": validation,
        "evaluator": evaluator,
        "score_name": _score_name(task),
        "scores": {name: float(value) for name, value in scores.items()},
        "models": {
            "dense": dense_model,
            "direct": direct_model,
            "compact": compact_model,
        },
    }


def prepare_runtime_fixture(
    path: str | Path,
    *,
    task: str,
    seed: int = DEFAULT_FIXTURE_SEED,
    device: str | torch.device = "cpu",
) -> dict:
    if task not in TASKS:
        raise ValueError("unknown task")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if seed in EXPLORATORY_SEEDS:
        raise ValueError("runtime fixture seed must be disjoint from exploratory seeds")
    device = torch.device(device)
    started = time.perf_counter()

    print(f"[gate-c-fixture] task={task} high-precision training", file=sys.stderr, flush=True)
    model, validation, evaluator, score_name = _train_high_precision(task, seed, device)
    source_core = model.core
    if not isinstance(source_core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained fixture core must remain high precision")
    dense_score = float(evaluator(model, validation)[score_name])
    print(
        f"[gate-c-fixture] task={task} dense ready score={dense_score:.6f} "
        f"elapsed={time.perf_counter() - started:.1f}s",
        file=sys.stderr,
        flush=True,
    )

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
    marks = sorted({max(1, math.ceil(steps * part / 4)) for part in range(1, 5)})
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
            raise ValueError("runtime fixture tuning produced non-finite loss")
        loss.backward()
        optimizer.step()
        if step in marks:
            elapsed = time.perf_counter() - started
            print(
                f"[gate-c-fixture] task={task} tuning={step}/{steps} "
                f"elapsed={elapsed:.1f}s",
                file=sys.stderr,
                flush=True,
            )

    exported = tunable_core.export_initializations()
    direct_model = copy.deepcopy(model)
    direct_model.core = CompressedFixedRoutingCore(source_core, exported).to(device)
    compact_model = copy.deepcopy(model)
    compact_model.core = CompactVectorizedFixedRoutingCore(source_core, exported).to(device)
    direct_score = float(evaluator(direct_model, validation)[score_name])
    compact_score = float(evaluator(compact_model, validation)[score_name])
    tuned_score = float(evaluator(tuned_model, validation)[score_name])
    if abs(direct_score - tuned_score) > 1e-7 or abs(compact_score - tuned_score) > 1e-7:
        raise RuntimeError("fixture runtime variants changed task score")

    destination = save_runtime_fixture(
        path,
        task=task,
        seed=seed,
        dense_model=model,
        compressed_initializations=exported,
        scores={"dense": dense_score, "direct": direct_score, "compact": compact_score},
    )
    elapsed = time.perf_counter() - started
    result = {
        "task": task,
        "seed": seed,
        "path": str(destination),
        "dense_score": dense_score,
        "direct_score": direct_score,
        "compact_score": compact_score,
        "elapsed_seconds": elapsed,
    }
    print(
        f"[gate-c-fixture] task={task} saved={destination} elapsed={elapsed:.1f}s",
        file=sys.stderr,
        flush=True,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_FIXTURE_SEED)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = prepare_runtime_fixture(
        args.output,
        task=args.task,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
