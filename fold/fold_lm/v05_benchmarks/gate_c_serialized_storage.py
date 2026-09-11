"""V5-C exact serialized/resident storage benchmark for the fixed candidate.

C11 established that the fixed high-fidelity compressed structure plus task-aware
continuous tuning preserves held-out quality on fresh seeds.  This benchmark
rebuilds that exact candidate, exports it to the direct runtime-neutral
representation, serializes it with the C12 binary format, and records exact
storage ratios.

The following quantities remain distinct:

- dense module float32 bytes: the two routed MLP Linear weight banks before
  compression;
- serialized bytes: actual ``len(blob)`` including metadata and bit-packed codes;
- compact resident tensor bytes: float32 continuous values with minimally sized
  unpacked integer codes and uint32 sparse-correction coordinates;
- reference-runtime resident tensor bytes: what ``DirectCompressedLinearBank``
  owns today, including int64 codes/coordinates.

Whole-model size is still outside this benchmark; these ratios cover only the
module-specific ``up.weight`` and ``down.weight`` banks compressed in V5-C.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import (
    CompressedFixedRoutingCore,
    CompressedModuleInitializations,
)
from fold_lm.v05.compression_serialization import (
    accounting_for_modules,
    deserialize_module_initializations,
    serialize_module_initializations,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_task_aware_revalidation import (
    EXPLORATORY_SEEDS,
    FRESH_SEEDS,
    TASKS,
    TUNING_SPECS,
    _assert_structure_unchanged,
    _structure_snapshot,
    _task_loss,
    _training_examples,
)
from fold_lm.v05_benchmarks.gate_c_task_aware_recovery import (
    DEFAULT_PROFILE,
    TaskTunableCompressedCore,
    _freeze_except_compressed,
    _initializations_from_core,
)
from fold_lm.v05_benchmarks.gate_c_task_quality import _train_high_precision


def _tune_and_export(
    task: str,
    seed: int,
    *,
    device: torch.device,
) -> tuple[object, object, object, str, CompressedModuleInitializations]:
    model, validation, evaluator, score_name = _train_high_precision(task, seed, device)
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained model core must remain HighPrecisionFixedRoutingCore")
    source_core = model.core
    initializations, _diagnostics = _initializations_from_core(
        source_core, DEFAULT_PROFILE, device=device
    )
    structure = _structure_snapshot(initializations)

    tuned_model = copy.deepcopy(model)
    tunable_core = TaskTunableCompressedCore(source_core, initializations).to(device)
    tuned_model.core = tunable_core
    tuned_model = tuned_model.to(device)
    _freeze_except_compressed(tuned_model, tunable_core)

    train = _training_examples(task, tuned_model, seed)
    spec = TUNING_SPECS[task]
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
            raise ValueError("serialized-storage task tuning produced non-finite loss")
        loss.backward()
        optimizer.step()

    exported = tunable_core.export_initializations()
    _assert_structure_unchanged(structure, exported)
    return model, validation, evaluator, score_name, exported


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
        raise ValueError("serialized-storage benchmark requires a non-exploratory seed")
    device = torch.device(device)

    model, validation, evaluator, score_name, exported = _tune_and_export(
        task, seed, device=device
    )
    source_core = model.core
    if not isinstance(source_core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained source core changed unexpectedly")

    accounting = accounting_for_modules(exported)
    blob = serialize_module_initializations(exported)
    if len(blob) != accounting.serialized_bytes:
        raise RuntimeError("serialized module blob length does not match accounting")
    restored = deserialize_module_initializations(blob)
    if serialize_module_initializations(restored) != blob:
        raise RuntimeError("serialized module round-trip is not byte-stable")

    direct_model = copy.deepcopy(model)
    direct_model.core = CompressedFixedRoutingCore(source_core, restored).to(device)
    direct_model = direct_model.to(device)
    direct_score = float(evaluator(direct_model, validation)[score_name])

    return {
        "task": task,
        "seed": seed,
        "score_name": score_name,
        "direct_export_score": direct_score,
        "dense_module_float32_bytes": accounting.dense_float32_bytes,
        "serialized_bytes": accounting.serialized_bytes,
        "serialized_ratio": accounting.serialized_ratio,
        "compact_resident_tensor_bytes": accounting.compact_resident_tensor_bytes,
        "compact_resident_ratio": accounting.compact_resident_ratio,
        "reference_runtime_tensor_bytes": accounting.reference_runtime_tensor_bytes,
        "reference_runtime_resident_ratio": accounting.reference_runtime_resident_ratio,
        "pair_metadata_bytes": accounting.pair_metadata_bytes,
        "blob_length_matches_accounting": len(blob) == accounting.serialized_bytes,
        "byte_stable_round_trip": serialize_module_initializations(restored) == blob,
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
            "mean_direct_export_score": sum(float(row["direct_export_score"]) for row in rows)
            / len(rows),
            "min_direct_export_score": min(float(row["direct_export_score"]) for row in rows),
            "dense_module_float32_bytes": rows[0]["dense_module_float32_bytes"],
            "serialized_bytes": rows[0]["serialized_bytes"],
            "serialized_ratio": rows[0]["serialized_ratio"],
            "compact_resident_tensor_bytes": rows[0]["compact_resident_tensor_bytes"],
            "compact_resident_ratio": rows[0]["compact_resident_ratio"],
            "reference_runtime_tensor_bytes": rows[0]["reference_runtime_tensor_bytes"],
            "reference_runtime_resident_ratio": rows[0]["reference_runtime_resident_ratio"],
            "all_blob_lengths_match_accounting": all(
                bool(row["blob_length_matches_accounting"]) for row in rows
            ),
            "all_round_trips_byte_stable": all(
                bool(row["byte_stable_round_trip"]) for row in rows
            ),
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
        raise ValueError("serialized-storage seeds must be disjoint from exploratory seeds")
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
                f"[gate-c-storage] start task={task} seed={seed} ({completed + 1}/{total})",
                file=sys.stderr,
                flush=True,
            )
            record = run_one(task, seed, device=device)
            records.append(record)
            completed += 1
            print(
                f"[gate-c-storage] done task={task} seed={seed} "
                f"score={record['direct_export_score']:.6f} "
                f"serialized={record['serialized_ratio']:.6f} "
                f"resident={record['reference_runtime_resident_ratio']:.6f}",
                file=sys.stderr,
                flush=True,
            )
    return {
        "schema": "fold-v05-gate-c-serialized-storage-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "task_names": list(task_names),
        "profile": "high_fidelity_fixed_after_c10",
        "records": records,
        "summary": summarize(records),
        "scope": "module-specific up/down Linear weights only",
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
