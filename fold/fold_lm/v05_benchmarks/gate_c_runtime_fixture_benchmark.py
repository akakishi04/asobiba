"""Fast V5-C runtime benchmark from a prepared reusable fixture.

C16 separates expensive candidate training/task-aware tuning from runtime
measurement.  This benchmark loads one trusted runtime fixture and times selected
runtime variants on the requested device without retraining.

By default only dense and compact-vectorized variants are measured.  The old
literal-direct path remains available explicitly for diagnostics but is omitted
from the default because C15 showed that it is hundreds of times slower on CUDA.
Progress is emitted to stderr so JSON stdout can be redirected to a file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time

import torch

from fold_lm.v05_benchmarks.gate_c_runtime_benchmark import (
    VARIANTS,
    _format_duration,
    _prepared_validation,
    measure_forward,
)
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture


DEFAULT_VARIANTS = ("dense", "compact")


def _validated_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA fixture benchmark requested but CUDA is unavailable")
    return result


def _validate_variants(variants: tuple[str, ...]) -> tuple[str, ...]:
    if not variants or len(set(variants)) != len(variants):
        raise ValueError("variants must be non-empty and distinct")
    if any(variant not in VARIANTS for variant in variants):
        raise ValueError("unknown runtime variant")
    if "dense" not in variants:
        raise ValueError("fixture runtime benchmark requires dense baseline")
    return variants


def _progress_line(completed: int, total: int, elapsed: float, label: str) -> str:
    if type(completed) is not int or type(total) is not int or total <= 0:
        raise ValueError("invalid progress counters")
    if completed < 0 or completed > total:
        raise ValueError("completed must be in [0, total]")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(float(elapsed)) or elapsed < 0:
        raise ValueError("elapsed must be finite and nonnegative")
    if not isinstance(label, str) or not label:
        raise ValueError("label must be non-empty")
    elapsed = float(elapsed)
    if completed == 0:
        eta = "--"
    else:
        eta = _format_duration(elapsed / completed * (total - completed))
    return (
        f"[gate-c-fixture-runtime] {completed}/{total} "
        f"({100.0 * completed / total:5.1f}%) "
        f"elapsed={_format_duration(elapsed)} eta={eta} {label}"
    )


def summarize_timings(timings: dict[str, dict], scores: dict[str, float]) -> dict:
    if not timings:
        raise ValueError("timings must be non-empty")
    if "dense" not in timings:
        raise ValueError("dense timing is required")
    dense = float(timings["dense"]["mean_seconds"])
    if not math.isfinite(dense) or dense <= 0.0:
        raise ValueError("dense mean_seconds must be positive and finite")
    variants: dict[str, dict] = {}
    for name, timing in timings.items():
        if name not in VARIANTS:
            raise ValueError("unknown runtime variant")
        mean_seconds = float(timing["mean_seconds"])
        if not math.isfinite(mean_seconds) or mean_seconds <= 0.0:
            raise ValueError("mean_seconds must be positive and finite")
        if name not in scores:
            raise ValueError("score missing for timed variant")
        variants[name] = {
            "mean_seconds": mean_seconds,
            "mean_milliseconds": mean_seconds * 1000.0,
            "runtime_ratio_vs_dense": mean_seconds / dense,
            "score": float(scores[name]),
            "median_seconds": float(timing["median_seconds"]),
            "p90_seconds": float(timing["p90_seconds"]),
        }
    return {"variants": variants}


def run_fixture_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cpu",
    variants: tuple[str, ...] = DEFAULT_VARIANTS,
    warmup: int = 10,
    repeats: int = 100,
) -> dict:
    variants = _validate_variants(variants)
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")
    device = _validated_device(device)
    started = time.perf_counter()

    print(
        _progress_line(0, len(variants), 0.0, f"loading fixture={fixture_path}"),
        file=sys.stderr,
        flush=True,
    )
    fixture = load_runtime_fixture(fixture_path, device=device)
    task = fixture["task"]
    validation = fixture["validation"]
    evaluator = fixture["evaluator"]
    score_name = fixture["score_name"]
    models = fixture["models"]
    stored_scores = fixture["scores"]

    # Verify fixture reconstruction before timing.  This is deliberately outside
    # the timed forward loop.
    verified_scores: dict[str, float] = {}
    for variant in variants:
        score = float(evaluator(models[variant], validation)[score_name])
        if abs(score - float(stored_scores[variant])) > 1e-7:
            raise RuntimeError("fixture reconstruction changed stored task score")
        verified_scores[variant] = score

    prepared = _prepared_validation(task, validation, device)
    timings: dict[str, dict] = {}
    completed = 0
    for variant in variants:
        elapsed = time.perf_counter() - started
        print(
            _progress_line(completed, len(variants), elapsed, f"variant={variant} timing"),
            file=sys.stderr,
            flush=True,
        )
        timings[variant] = measure_forward(
            task,
            models[variant],
            prepared,
            warmup=warmup,
            repeats=repeats,
            device=device,
        )
        completed += 1
        elapsed = time.perf_counter() - started
        print(
            _progress_line(
                completed,
                len(variants),
                elapsed,
                f"variant={variant} mean={timings[variant]['mean_seconds'] * 1000.0:.3f}ms",
            ),
            file=sys.stderr,
            flush=True,
        )

    elapsed = time.perf_counter() - started
    device_name = "cpu" if device.type == "cpu" else torch.cuda.get_device_name(device)
    return {
        "schema": "fold-v05-gate-c-runtime-fixture-benchmark-v1",
        "fixture_path": fixture_path,
        "task": task,
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": device_name,
        "variants": list(variants),
        "warmup": warmup,
        "repeats": repeats,
        "verified_scores": verified_scores,
        "timings": timings,
        "summary": summarize_timings(timings, verified_scores),
        "elapsed_seconds": elapsed,
        "retrained": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(DEFAULT_VARIANTS))
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_fixture_benchmark(
        args.fixture,
        device=args.device,
        variants=tuple(args.variants),
        warmup=args.warmup,
        repeats=args.repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
