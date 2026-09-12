"""V5-C torch.compile runtime benchmark from a reusable fixture.

C17 made runtime iteration cheap by separating candidate training from timing.
C18 measures whether PyTorch Inductor/Triton can reduce the eager compact-runtime
overhead without rebuilding the candidate.

The benchmark keeps four paths separate:

- eager_dense
- eager_compact
- compiled_dense
- compiled_compact

Compilation latency is recorded separately from steady-state forward latency.
The first compiled forward is never included in the runtime samples.  Compiled
outputs are checked against their eager counterparts before timing.

This benchmark intentionally leaves float32 matmul precision unchanged.  TF32 or
other precision-policy changes are a separate experiment rather than being mixed
into the compile comparison.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time

import torch

from fold_lm.v05_benchmarks.gate_c_runtime_benchmark import (
    _format_duration,
    _forward_prepared,
    _prepared_validation,
)
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture


VARIANTS = (
    "eager_dense",
    "eager_compact",
    "compiled_dense",
    "compiled_compact",
)
DEFAULT_VARIANTS = VARIANTS


def _validated_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA compile benchmark requested but CUDA is unavailable")
    return result


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


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
    eta = "--" if completed == 0 else _format_duration(elapsed / completed * (total - completed))
    return (
        f"[gate-c-compile] {completed}/{total} "
        f"({100.0 * completed / total:5.1f}%) "
        f"elapsed={_format_duration(elapsed)} eta={eta} {label}"
    )


@torch.inference_mode()
def _measure_forward(
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


def _compile_model(model, *, backend: str, device: torch.device, task: str, prepared):
    if not hasattr(torch, "compile"):
        raise RuntimeError("torch.compile is unavailable")
    compiled = torch.compile(model, backend=backend, fullgraph=False, dynamic=False)
    _sync(device)
    started = time.perf_counter()
    output = _forward_prepared(task, compiled, prepared)
    _sync(device)
    compile_first_forward_seconds = time.perf_counter() - started
    return compiled, output, compile_first_forward_seconds


def summarize_timings(timings: dict[str, dict], compile_seconds: dict[str, float]) -> dict:
    if not timings or any(name not in timings for name in VARIANTS):
        raise ValueError("all four runtime variants are required")
    eager_dense = float(timings["eager_dense"]["mean_seconds"])
    compiled_dense = float(timings["compiled_dense"]["mean_seconds"])
    eager_compact = float(timings["eager_compact"]["mean_seconds"])
    compiled_compact = float(timings["compiled_compact"]["mean_seconds"])
    if any(
        not math.isfinite(value) or value <= 0.0
        for value in (eager_dense, compiled_dense, eager_compact, compiled_compact)
    ):
        raise ValueError("timing means must be positive and finite")
    for name in ("compiled_dense", "compiled_compact"):
        value = float(compile_seconds.get(name, -1.0))
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("compiled variants require finite nonnegative compile latency")

    variants: dict[str, dict] = {}
    for name in VARIANTS:
        mean_seconds = float(timings[name]["mean_seconds"])
        variants[name] = {
            "mean_seconds": mean_seconds,
            "mean_milliseconds": mean_seconds * 1000.0,
            "runtime_ratio_vs_eager_dense": mean_seconds / eager_dense,
            "median_seconds": float(timings[name]["median_seconds"]),
            "p90_seconds": float(timings[name]["p90_seconds"]),
        }
        if name in compile_seconds:
            variants[name]["compile_first_forward_seconds"] = float(compile_seconds[name])

    return {
        "variants": variants,
        "compiled_compact_ratio_vs_compiled_dense": compiled_compact / compiled_dense,
        "dense_compile_speedup": eager_dense / compiled_dense,
        "compact_compile_speedup": eager_compact / compiled_compact,
    }


def run_compile_fixture_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    backend: str = "inductor",
    warmup: int = 10,
    repeats: int = 100,
) -> dict:
    if not isinstance(backend, str) or not backend:
        raise ValueError("backend must be non-empty")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")
    device = _validated_device(device)
    started = time.perf_counter()
    total = 7  # load + two eager timings + two compile/parity steps + two compiled timings.
    completed = 0

    print(
        _progress_line(completed, total, 0.0, f"loading fixture={fixture_path}"),
        file=sys.stderr,
        flush=True,
    )
    fixture = load_runtime_fixture(fixture_path, device=device)
    task = fixture["task"]
    validation = fixture["validation"]
    models = fixture["models"]
    prepared = _prepared_validation(task, validation, device)
    completed += 1
    print(
        _progress_line(completed, total, time.perf_counter() - started, "fixture loaded"),
        file=sys.stderr,
        flush=True,
    )

    eager_outputs: dict[str, torch.Tensor] = {}
    timings: dict[str, dict] = {}
    for base_name in ("dense", "compact"):
        variant = f"eager_{base_name}"
        models[base_name].eval()
        with torch.inference_mode():
            eager_outputs[base_name] = _forward_prepared(task, models[base_name], prepared)
        timings[variant] = _measure_forward(
            task,
            models[base_name],
            prepared,
            warmup=warmup,
            repeats=repeats,
            device=device,
        )
        completed += 1
        print(
            _progress_line(
                completed,
                total,
                time.perf_counter() - started,
                f"{variant} mean={timings[variant]['mean_seconds'] * 1000.0:.3f}ms",
            ),
            file=sys.stderr,
            flush=True,
        )

    compiled_models: dict[str, object] = {}
    compile_seconds: dict[str, float] = {}
    max_abs_output_gap: dict[str, float] = {}
    for base_name in ("dense", "compact"):
        variant = f"compiled_{base_name}"
        print(
            _progress_line(
                completed,
                total,
                time.perf_counter() - started,
                f"{variant} compiling backend={backend}",
            ),
            file=sys.stderr,
            flush=True,
        )
        compiled, compiled_output, first_seconds = _compile_model(
            models[base_name],
            backend=backend,
            device=device,
            task=task,
            prepared=prepared,
        )
        torch.testing.assert_close(
            compiled_output,
            eager_outputs[base_name],
            rtol=1e-4,
            atol=1e-5,
        )
        gap = float((compiled_output - eager_outputs[base_name]).abs().max().item())
        compiled_models[base_name] = compiled
        compile_seconds[variant] = first_seconds
        max_abs_output_gap[variant] = gap
        completed += 1
        print(
            _progress_line(
                completed,
                total,
                time.perf_counter() - started,
                f"{variant} first={first_seconds:.3f}s max_gap={gap:.3e}",
            ),
            file=sys.stderr,
            flush=True,
        )

    for base_name in ("dense", "compact"):
        variant = f"compiled_{base_name}"
        timings[variant] = _measure_forward(
            task,
            compiled_models[base_name],
            prepared,
            warmup=warmup,
            repeats=repeats,
            device=device,
        )
        completed += 1
        print(
            _progress_line(
                completed,
                total,
                time.perf_counter() - started,
                f"{variant} mean={timings[variant]['mean_seconds'] * 1000.0:.3f}ms",
            ),
            file=sys.stderr,
            flush=True,
        )

    if completed != total:
        raise RuntimeError("compile benchmark progress accounting mismatch")
    elapsed = time.perf_counter() - started
    device_name = "cpu" if device.type == "cpu" else torch.cuda.get_device_name(device)
    return {
        "schema": "fold-v05-gate-c-compile-fixture-benchmark-v1",
        "fixture_path": fixture_path,
        "task": task,
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": device_name,
        "backend": backend,
        "warmup": warmup,
        "repeats": repeats,
        "timings": timings,
        "compile_first_forward_seconds": compile_seconds,
        "max_abs_compiled_eager_output_gap": max_abs_output_gap,
        "summary": summarize_timings(timings, compile_seconds),
        "elapsed_seconds": elapsed,
        "retrained": False,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--backend", default="inductor")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_compile_fixture_benchmark(
        args.fixture,
        device=args.device,
        backend=args.backend,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
