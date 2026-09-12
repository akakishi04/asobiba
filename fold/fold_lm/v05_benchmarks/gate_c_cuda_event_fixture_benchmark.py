"""C23: robust CUDA-event runtime benchmark for the V5-C compression candidate.

Earlier C21/C22 wall-clock measurements showed large run-to-run variance on a
Windows/WDDM desktop.  This benchmark reduces that measurement noise without
changing the model or optimization candidate:

- each timing sample contains many consecutive forwards;
- CUDA Events measure device elapsed time for the whole batch;
- wall-clock time for the same batch is reported separately;
- dense / compact / Triton order rotates every round;
- final ratios use paired same-round measurements and medians.

The benchmark still measures real model forwards and does not materialize dense
compressed weights or retrain the candidate.
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

from fold_lm.v05.compression_serialization import deserialize_module_initializations
from fold_lm.v05.triton_runtime import TritonCompressedFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_runtime_benchmark import (
    _forward_prepared,
    _prepared_validation,
)
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture


VARIANTS = ("dense", "compact", "triton")


def order_for_round(round_index: int) -> tuple[str, ...]:
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    offset = round_index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


def _load_initializations(fixture_path: str):
    payload = torch.load(fixture_path, map_location="cpu", weights_only=True)
    blob_tensor = payload.get("compressed_blob")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8:
        raise ValueError("fixture compressed blob is invalid")
    return deserialize_module_initializations(blob_tensor.contiguous().numpy().tobytes())


@torch.inference_mode()
def _measure_batch(
    task: str,
    model,
    prepared: tuple[torch.Tensor, ...],
    *,
    iterations: int,
) -> dict:
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")
    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    wall_started = time.perf_counter()
    start_event.record()
    for _ in range(iterations):
        _forward_prepared(task, model, prepared)
    end_event.record()
    end_event.synchronize()
    wall_seconds = time.perf_counter() - wall_started
    device_ms = float(start_event.elapsed_time(end_event))
    return {
        "iterations": iterations,
        "device_total_ms": device_ms,
        "device_per_forward_ms": device_ms / iterations,
        "wall_total_seconds": wall_seconds,
        "wall_per_forward_ms": wall_seconds * 1000.0 / iterations,
    }


def _median(values: list[float]) -> float:
    if not values or any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in values):
        raise ValueError("timing values must be positive and finite")
    return float(statistics.median(float(value) for value in values))


def summarize_rounds(records: list[dict], scores: dict[str, float]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    if any(name not in scores for name in VARIANTS):
        raise ValueError("scores must contain dense, compact, and triton")

    rounds = sorted({int(row["round"]) for row in records})
    if rounds != list(range(len(rounds))):
        raise ValueError("round indices must be contiguous from zero")

    variants: dict[str, dict] = {}
    by_round: dict[int, dict[str, dict]] = {round_index: {} for round_index in rounds}
    for row in records:
        variant = row.get("variant")
        round_index = int(row.get("round"))
        if variant not in VARIANTS:
            raise ValueError("unknown runtime variant")
        if variant in by_round[round_index]:
            raise ValueError("duplicate variant in a round")
        by_round[round_index][variant] = row

    if any(set(rows) != set(VARIANTS) for rows in by_round.values()):
        raise ValueError("every round must contain all runtime variants")

    for variant in VARIANTS:
        device = [
            float(by_round[round_index][variant]["device_per_forward_ms"])
            for round_index in rounds
        ]
        wall = [
            float(by_round[round_index][variant]["wall_per_forward_ms"])
            for round_index in rounds
        ]
        variants[variant] = {
            "score": float(scores[variant]),
            "device_median_ms": _median(device),
            "device_min_ms": min(device),
            "device_max_ms": max(device),
            "wall_median_ms": _median(wall),
            "wall_min_ms": min(wall),
            "wall_max_ms": max(wall),
        }

    paired_triton_dense_device = []
    paired_triton_dense_wall = []
    paired_compact_triton_device = []
    paired_compact_triton_wall = []
    for round_index in rounds:
        dense = by_round[round_index]["dense"]
        compact = by_round[round_index]["compact"]
        triton = by_round[round_index]["triton"]
        paired_triton_dense_device.append(
            float(triton["device_per_forward_ms"]) / float(dense["device_per_forward_ms"])
        )
        paired_triton_dense_wall.append(
            float(triton["wall_per_forward_ms"]) / float(dense["wall_per_forward_ms"])
        )
        paired_compact_triton_device.append(
            float(compact["device_per_forward_ms"]) / float(triton["device_per_forward_ms"])
        )
        paired_compact_triton_wall.append(
            float(compact["wall_per_forward_ms"]) / float(triton["wall_per_forward_ms"])
        )

    return {
        "rounds": len(rounds),
        "variants": variants,
        "paired_ratios": {
            "triton_vs_dense_device_median": _median(paired_triton_dense_device),
            "triton_vs_dense_device_min": min(paired_triton_dense_device),
            "triton_vs_dense_device_max": max(paired_triton_dense_device),
            "triton_vs_dense_wall_median": _median(paired_triton_dense_wall),
            "triton_vs_dense_wall_min": min(paired_triton_dense_wall),
            "triton_vs_dense_wall_max": max(paired_triton_dense_wall),
            "compact_to_triton_device_speedup_median": _median(paired_compact_triton_device),
            "compact_to_triton_wall_speedup_median": _median(paired_compact_triton_wall),
        },
    }


def run_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    warmup: int = 20,
    rounds: int = 9,
    iterations: int = 50,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C23 CUDA-event benchmark requires CUDA")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(rounds) is not int or rounds <= 0:
        raise ValueError("rounds must be positive")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")

    started = time.perf_counter()
    fixture = load_runtime_fixture(fixture_path, device=device)
    task = fixture["task"]
    validation = fixture["validation"]
    evaluator = fixture["evaluator"]
    score_name = fixture["score_name"]
    dense_model = fixture["models"]["dense"].eval()
    compact_model = fixture["models"]["compact"].eval()
    initializations = _load_initializations(fixture_path)

    triton_model = copy.deepcopy(dense_model)
    triton_model.core = TritonCompressedFixedRoutingCore(
        dense_model.core,
        initializations,
    ).to(device)
    triton_model = triton_model.to(device).eval()
    models = {
        "dense": dense_model,
        "compact": compact_model,
        "triton": triton_model,
    }
    prepared = _prepared_validation(task, validation, device)

    # First Triton use plus parity is intentionally outside measured rounds.
    with torch.inference_mode():
        triton_output = _forward_prepared(task, triton_model, prepared)
        compact_output = _forward_prepared(task, compact_model, prepared)
    torch.cuda.synchronize()
    torch.testing.assert_close(triton_output, compact_output, rtol=1e-4, atol=1e-5)
    max_abs_output_gap = float((triton_output - compact_output).abs().max().item())

    scores = {
        "dense": float(evaluator(dense_model, validation)[score_name]),
        "compact": float(evaluator(compact_model, validation)[score_name]),
        "triton": float(evaluator(triton_model, validation)[score_name]),
    }
    stored_scores = fixture["scores"]
    if abs(scores["dense"] - float(stored_scores["dense"])) > 1e-7:
        raise RuntimeError("dense fixture reconstruction changed score")
    if abs(scores["compact"] - float(stored_scores["compact"])) > 1e-7:
        raise RuntimeError("compact fixture reconstruction changed score")
    if abs(scores["triton"] - scores["compact"]) > 1e-7:
        raise RuntimeError("Triton runtime changed task score")

    # Warm all paths before measured rounds to reduce first-use and clock-state effects.
    with torch.inference_mode():
        for variant in VARIANTS:
            for _ in range(warmup):
                _forward_prepared(task, models[variant], prepared)
    torch.cuda.synchronize()

    records: list[dict] = []
    total = rounds * len(VARIANTS)
    completed = 0
    for round_index in range(rounds):
        order = order_for_round(round_index)
        for variant in order:
            timing = _measure_batch(
                task,
                models[variant],
                prepared,
                iterations=iterations,
            )
            record = {
                "round": round_index,
                "order": list(order),
                "variant": variant,
                **timing,
            }
            records.append(record)
            completed += 1
            elapsed = time.perf_counter() - started
            print(
                f"[gate-c-cuda-event] {completed}/{total} "
                f"round={round_index + 1}/{rounds} variant={variant} "
                f"device={timing['device_per_forward_ms']:.3f}ms "
                f"wall={timing['wall_per_forward_ms']:.3f}ms "
                f"elapsed={elapsed:.1f}s",
                file=sys.stderr,
                flush=True,
            )

    summary = summarize_rounds(records, scores)
    return {
        "schema": "fold-v05-gate-c-cuda-event-fixture-benchmark-v1",
        "fixture_path": fixture_path,
        "task": task,
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_round": iterations,
        "scores": scores,
        "max_abs_triton_compact_output_gap": max_abs_output_gap,
        "records": records,
        "summary": summary,
        "elapsed_seconds": time.perf_counter() - started,
        "retrained": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        args.fixture,
        device=args.device,
        warmup=args.warmup,
        rounds=args.rounds,
        iterations=args.iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
