"""C21: benchmark full-model dense, compact PyTorch, and fused Triton runtimes.

Uses a prepared C16 runtime fixture, so no training or task-aware recovery is
repeated.  The fused Triton model preserves the compact serialized/resident
representation and replaces only the compressed routed Linear execution path.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time

import torch

from fold_lm.v05.compression_serialization import deserialize_module_initializations
from fold_lm.v05.triton_runtime import TritonCompressedFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_runtime_benchmark import (
    _format_duration,
    _forward_prepared,
    _prepared_validation,
    measure_forward,
)
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture

VARIANTS = ("dense", "compact", "triton")


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _load_initializations(fixture_path: str):
    payload = torch.load(fixture_path, map_location="cpu", weights_only=True)
    blob_tensor = payload.get("compressed_blob")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8:
        raise ValueError("fixture compressed blob is invalid")
    return deserialize_module_initializations(blob_tensor.contiguous().numpy().tobytes())


def summarize_timings(timings: dict[str, dict], scores: dict[str, float]) -> dict:
    if any(name not in timings for name in VARIANTS):
        raise ValueError("dense, compact, and triton timings are required")
    if any(name not in scores for name in VARIANTS):
        raise ValueError("dense, compact, and triton scores are required")
    means = {name: float(timings[name]["mean_seconds"]) for name in VARIANTS}
    if any(not math.isfinite(value) or value <= 0.0 for value in means.values()):
        raise ValueError("timing means must be positive and finite")
    dense = means["dense"]
    compact = means["compact"]
    triton = means["triton"]
    variants = {}
    for name in VARIANTS:
        timing = timings[name]
        variants[name] = {
            "mean_seconds": means[name],
            "mean_milliseconds": means[name] * 1000.0,
            "median_seconds": float(timing["median_seconds"]),
            "p90_seconds": float(timing["p90_seconds"]),
            "runtime_ratio_vs_dense": means[name] / dense,
            "score": float(scores[name]),
        }
    return {
        "variants": variants,
        "compact_to_triton_speedup": compact / triton,
        "triton_ratio_vs_dense": triton / dense,
    }


def _progress(completed: int, total: int, started: float, label: str) -> None:
    elapsed = time.perf_counter() - started
    eta = "--" if completed == 0 else _format_duration(elapsed / completed * (total - completed))
    print(
        f"[gate-c-triton-fixture] {completed}/{total} "
        f"elapsed={_format_duration(elapsed)} eta={eta} {label}",
        file=sys.stderr,
        flush=True,
    )


def run_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    warmup: int = 10,
    repeats: int = 100,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C21 Triton full-model benchmark requires CUDA")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")

    started = time.perf_counter()
    total = 4  # setup/parity + three runtime variants
    _progress(0, total, started, f"loading fixture={fixture_path}")
    fixture = load_runtime_fixture(fixture_path, device=device)
    task = fixture["task"]
    validation = fixture["validation"]
    evaluator = fixture["evaluator"]
    score_name = fixture["score_name"]
    dense_model = fixture["models"]["dense"]
    compact_model = fixture["models"]["compact"]
    initializations = _load_initializations(fixture_path)

    triton_model = copy.deepcopy(dense_model)
    triton_model.core = TritonCompressedFixedRoutingCore(
        dense_model.core,
        initializations,
    ).to(device)
    triton_model = triton_model.to(device).eval()

    prepared = _prepared_validation(task, validation, device)
    _sync(device)
    first_started = time.perf_counter()
    with torch.inference_mode():
        triton_output = _forward_prepared(task, triton_model, prepared)
    _sync(device)
    triton_first_forward_seconds = time.perf_counter() - first_started
    with torch.inference_mode():
        compact_output = _forward_prepared(task, compact_model, prepared)
    torch.testing.assert_close(triton_output, compact_output, rtol=1e-4, atol=1e-5)
    max_abs_output_gap = float((triton_output - compact_output).abs().max().item())

    stored_scores = fixture["scores"]
    scores = {
        "dense": float(evaluator(dense_model, validation)[score_name]),
        "compact": float(evaluator(compact_model, validation)[score_name]),
        "triton": float(evaluator(triton_model, validation)[score_name]),
    }
    if abs(scores["dense"] - float(stored_scores["dense"])) > 1e-7:
        raise RuntimeError("dense fixture reconstruction changed score")
    if abs(scores["compact"] - float(stored_scores["compact"])) > 1e-7:
        raise RuntimeError("compact fixture reconstruction changed score")
    if abs(scores["triton"] - scores["compact"]) > 1e-7:
        raise RuntimeError("Triton runtime changed task score")

    completed = 1
    _progress(
        completed,
        total,
        started,
        f"parity max_gap={max_abs_output_gap:.3e} first={triton_first_forward_seconds:.3f}s",
    )

    models = {"dense": dense_model, "compact": compact_model, "triton": triton_model}
    timings: dict[str, dict] = {}
    for name in VARIANTS:
        timings[name] = measure_forward(
            task,
            models[name],
            prepared,
            warmup=warmup,
            repeats=repeats,
            device=device,
        )
        completed += 1
        _progress(
            completed,
            total,
            started,
            f"{name} mean={timings[name]['mean_seconds'] * 1000.0:.3f}ms",
        )

    return {
        "schema": "fold-v05-gate-c-triton-fixture-benchmark-v1",
        "fixture_path": fixture_path,
        "task": task,
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "warmup": warmup,
        "repeats": repeats,
        "scores": scores,
        "timings": timings,
        "summary": summarize_timings(timings, scores),
        "triton_first_forward_seconds": triton_first_forward_seconds,
        "max_abs_triton_compact_output_gap": max_abs_output_gap,
        "elapsed_seconds": time.perf_counter() - started,
        "retrained": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        args.fixture,
        device=args.device,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
