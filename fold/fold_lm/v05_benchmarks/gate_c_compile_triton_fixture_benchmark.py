"""C22: benchmark torch.compile around the fused-Triton full model.

C21 reduced the eager compact runtime substantially by replacing the routed
compressed Linear path with fused Triton kernels.  C22 asks whether Inductor can
remove additional surrounding PyTorch overhead (normalization, bias, GELU,
residual/gate work and Python/module dispatch) without changing the compact
persistent representation or retraining the candidate.

The benchmark compares four steady-state paths in one run:

- eager_dense
- compiled_dense
- eager_triton
- compiled_triton

Triton kernel first-use latency and torch.compile first-forward latency are kept
out of steady-state timing.  Outputs are checked before timing.
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

VARIANTS = ("eager_dense", "compiled_dense", "eager_triton", "compiled_triton")


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _load_initializations(fixture_path: str):
    payload = torch.load(fixture_path, map_location="cpu", weights_only=True)
    blob_tensor = payload.get("compressed_blob")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8:
        raise ValueError("fixture compressed blob is invalid")
    return deserialize_module_initializations(blob_tensor.contiguous().numpy().tobytes())


def summarize_timings(
    timings: dict[str, dict],
    compile_first_forward_seconds: dict[str, float],
) -> dict:
    if any(name not in timings for name in VARIANTS):
        raise ValueError("all four compile/runtime variants are required")
    means = {name: float(timings[name]["mean_seconds"]) for name in VARIANTS}
    if any(not math.isfinite(value) or value <= 0.0 for value in means.values()):
        raise ValueError("timing means must be positive and finite")
    for name in ("compiled_dense", "compiled_triton"):
        value = float(compile_first_forward_seconds.get(name, -1.0))
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("compiled variants require compile first-forward latency")

    eager_dense = means["eager_dense"]
    compiled_dense = means["compiled_dense"]
    eager_triton = means["eager_triton"]
    compiled_triton = means["compiled_triton"]
    variants = {}
    for name in VARIANTS:
        timing = timings[name]
        variants[name] = {
            "mean_seconds": means[name],
            "mean_milliseconds": means[name] * 1000.0,
            "median_seconds": float(timing["median_seconds"]),
            "p90_seconds": float(timing["p90_seconds"]),
            "runtime_ratio_vs_eager_dense": means[name] / eager_dense,
        }
        if name in compile_first_forward_seconds:
            variants[name]["compile_first_forward_seconds"] = float(
                compile_first_forward_seconds[name]
            )

    return {
        "variants": variants,
        "dense_compile_speedup": eager_dense / compiled_dense,
        "triton_compile_speedup": eager_triton / compiled_triton,
        "compiled_triton_ratio_vs_compiled_dense": compiled_triton / compiled_dense,
        "compiled_triton_ratio_vs_eager_dense": compiled_triton / eager_dense,
    }


def _progress(completed: int, total: int, started: float, label: str) -> None:
    elapsed = time.perf_counter() - started
    eta = "--" if completed == 0 else _format_duration(elapsed / completed * (total - completed))
    print(
        f"[gate-c-compile-triton] {completed}/{total} "
        f"elapsed={_format_duration(elapsed)} eta={eta} {label}",
        file=sys.stderr,
        flush=True,
    )


def _compile_model(model, *, backend: str, task: str, prepared, device: torch.device):
    compiled = torch.compile(model, backend=backend, fullgraph=False, dynamic=False)
    _sync(device)
    started = time.perf_counter()
    with torch.inference_mode():
        output = _forward_prepared(task, compiled, prepared)
    _sync(device)
    return compiled, output, time.perf_counter() - started


def run_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    backend: str = "inductor",
    warmup: int = 10,
    repeats: int = 100,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C22 compile+Triton benchmark requires CUDA")
    if not isinstance(backend, str) or not backend:
        raise ValueError("backend must be non-empty")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")

    started = time.perf_counter()
    total = 7  # setup, two eager timings, two compile/parity, two compiled timings
    _progress(0, total, started, f"loading fixture={fixture_path}")
    fixture = load_runtime_fixture(fixture_path, device=device)
    task = fixture["task"]
    validation = fixture["validation"]
    dense_model = fixture["models"]["dense"].eval()
    initializations = _load_initializations(fixture_path)

    triton_model = copy.deepcopy(dense_model)
    triton_model.core = TritonCompressedFixedRoutingCore(
        dense_model.core,
        initializations,
    ).to(device)
    triton_model = triton_model.to(device).eval()
    prepared = _prepared_validation(task, validation, device)

    # Trigger Triton kernel compilation before either eager steady-state timing or
    # torch.compile first-forward accounting.
    _sync(device)
    triton_first_started = time.perf_counter()
    with torch.inference_mode():
        eager_triton_output = _forward_prepared(task, triton_model, prepared)
        eager_dense_output = _forward_prepared(task, dense_model, prepared)
    _sync(device)
    triton_first_forward_seconds = time.perf_counter() - triton_first_started
    completed = 1
    _progress(
        completed,
        total,
        started,
        f"setup Triton first={triton_first_forward_seconds:.3f}s",
    )

    timings: dict[str, dict] = {}
    timings["eager_dense"] = measure_forward(
        task, dense_model, prepared, warmup=warmup, repeats=repeats, device=device
    )
    completed += 1
    _progress(
        completed,
        total,
        started,
        f"eager_dense mean={timings['eager_dense']['mean_seconds'] * 1000.0:.3f}ms",
    )

    timings["eager_triton"] = measure_forward(
        task, triton_model, prepared, warmup=warmup, repeats=repeats, device=device
    )
    completed += 1
    _progress(
        completed,
        total,
        started,
        f"eager_triton mean={timings['eager_triton']['mean_seconds'] * 1000.0:.3f}ms",
    )

    compiled_models = {}
    compile_seconds: dict[str, float] = {}
    output_gaps: dict[str, float] = {}
    for base_name, model, eager_output in (
        ("dense", dense_model, eager_dense_output),
        ("triton", triton_model, eager_triton_output),
    ):
        variant = f"compiled_{base_name}"
        _progress(completed, total, started, f"{variant} compiling backend={backend}")
        compiled, compiled_output, first_seconds = _compile_model(
            model,
            backend=backend,
            task=task,
            prepared=prepared,
            device=device,
        )
        torch.testing.assert_close(compiled_output, eager_output, rtol=1e-4, atol=1e-5)
        gap = float((compiled_output - eager_output).abs().max().item())
        compiled_models[base_name] = compiled
        compile_seconds[variant] = first_seconds
        output_gaps[variant] = gap
        completed += 1
        _progress(
            completed,
            total,
            started,
            f"{variant} first={first_seconds:.3f}s max_gap={gap:.3e}",
        )

    for base_name in ("dense", "triton"):
        variant = f"compiled_{base_name}"
        timings[variant] = measure_forward(
            task,
            compiled_models[base_name],
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
            f"{variant} mean={timings[variant]['mean_seconds'] * 1000.0:.3f}ms",
        )

    if completed != total:
        raise RuntimeError("C22 progress accounting mismatch")

    return {
        "schema": "fold-v05-gate-c-compile-triton-fixture-benchmark-v1",
        "fixture_path": fixture_path,
        "task": task,
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "backend": backend,
        "warmup": warmup,
        "repeats": repeats,
        "timings": timings,
        "compile_first_forward_seconds": compile_seconds,
        "max_abs_compiled_eager_output_gap": output_gaps,
        "triton_first_forward_seconds": triton_first_forward_seconds,
        "summary": summarize_timings(timings, compile_seconds),
        "elapsed_seconds": time.perf_counter() - started,
        "retrained": False,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
    }


def main(argv=None) -> int:
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
    result = run_benchmark(
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
