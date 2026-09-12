"""C30: bounded tile/precision sweep for the base-only tiled Triton matmul.

C29 showed that the additive codebook path adds only a modest increment over the
base-only tiled runtime; most of the remaining Dense gap is already present in the
custom Triton matmul itself.  C30 therefore tests a small fixed set of execution
configurations at width=256, rows=216 before any more codebook-specific work.

Diagnostic only.  It compares cuBLAS-backed ``F.linear`` over the shared base with
five Triton base-only configurations.  Both runtime and numerical deviation from
the Dense reference are reported.  The sweep is intentionally bounded so it does
not turn into open-ended benchmark fitting.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.triton_tiled_tuning_runtime import (
    TiledBaseKernelConfig,
    TunedTiledBaseOnlyLinearBank,
)
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

DEFAULT_WIDTH = 256
DEFAULT_ROWS = 216

CONFIGS = {
    "ieee_16x16x32": TiledBaseKernelConfig(16, 16, 32, 4, "ieee"),
    "ieee_32x32x32": TiledBaseKernelConfig(32, 32, 32, 4, "ieee"),
    "tf32x3_32x32x32": TiledBaseKernelConfig(32, 32, 32, 4, "tf32x3"),
    "tf32_32x32x32": TiledBaseKernelConfig(32, 32, 32, 4, "tf32"),
    "tf32_32x64x32": TiledBaseKernelConfig(32, 64, 32, 4, "tf32"),
}
VARIANTS = ("dense", *CONFIGS.keys())


def order_for_round(round_index: int) -> tuple[str, ...]:
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    offset = round_index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


@torch.inference_mode()
def _measure_batch(callable_, *, iterations: int) -> float:
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(iterations):
        callable_()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / iterations


def _median(values: list[float]) -> float:
    if not values or any(not math.isfinite(float(v)) or float(v) <= 0.0 for v in values):
        raise ValueError("timing values must be positive and finite")
    return float(statistics.median(float(v) for v in values))


def summarize_records(records: list[dict], output_gaps: dict[str, float]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    points = {}
    for role in ROLES:
        rows = [r for r in records if r.get("role") == role]
        if not rows:
            continue
        rounds = sorted({int(r["round"]) for r in rows})
        medians = {}
        ratios = {}
        for variant in VARIANTS:
            values = [float(r["device_per_forward_ms"]) for r in rows if r["variant"] == variant]
            medians[variant] = _median(values)
        for variant in CONFIGS:
            paired = []
            for round_index in rounds:
                group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
                if set(group) != set(VARIANTS):
                    raise ValueError("every role/round must contain all variants")
                paired.append(
                    float(group[variant]["device_per_forward_ms"])
                    / float(group["dense"]["device_per_forward_ms"])
                )
            ratios[variant] = _median(paired)
        points[role] = {
            "dense_device_median_ms": medians["dense"],
            "variants": {
                variant: {
                    "device_median_ms": medians[variant],
                    "vs_dense_paired_median": ratios[variant],
                    "max_abs_output_gap": float(output_gaps[f"{role}:{variant}"]),
                }
                for variant in CONFIGS
            },
        }
    if set(points) != set(ROLES):
        raise ValueError("records must contain both roles")
    return {"roles": points}


def run_benchmark(
    *,
    width: int = DEFAULT_WIDTH,
    rows: int = DEFAULT_ROWS,
    device: str | torch.device = "cuda",
    warmup: int = 20,
    rounds: int = 7,
    iterations: int = 100,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C30 tiled base tuning requires CUDA")
    if type(width) is not int or width <= 0:
        raise ValueError("width must be positive")
    if type(rows) is not int or rows <= 0:
        raise ValueError("rows must be positive")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(rounds) is not int or rounds <= 0:
        raise ValueError("rounds must be positive")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")

    started = time.perf_counter()
    records: list[dict] = []
    output_gaps: dict[str, float] = {}
    structures = {}
    total = len(ROLES) * rounds * len(VARIANTS)
    completed = 0
    generator = torch.Generator(device="cpu").manual_seed(20260912)

    for role in ROLES:
        input_width, output_width = role_shape(width, role)
        init = build_synthetic_initialization(input_width, output_width)
        banks = {
            name: TunedTiledBaseOnlyLinearBank(init, config).to(device)
            for name, config in CONFIGS.items()
        }
        base_weight = next(iter(banks.values())).base
        value = torch.randn(rows, input_width, generator=generator, dtype=torch.float32).to(device)
        dense_out = F.linear(value, base_weight, None)

        structures[role] = {
            "width": width,
            "rows": rows,
            "input_width": input_width,
            "output_width": output_width,
        }
        for name, bank in banks.items():
            out = bank(value, module_index=0)
            torch.cuda.synchronize()
            if not torch.isfinite(out).all():
                raise RuntimeError(f"{name} produced non-finite output")
            output_gaps[f"{role}:{name}"] = float((out - dense_out).abs().max().item())

        callables = {
            "dense": lambda v=value, w=base_weight: F.linear(v, w, None),
            **{
                name: (lambda b=bank, v=value: b(v, module_index=0))
                for name, bank in banks.items()
            },
        }
        with torch.inference_mode():
            for variant in VARIANTS:
                for _ in range(warmup):
                    callables[variant]()
        torch.cuda.synchronize()

        for round_index in range(rounds):
            for variant in order_for_round(round_index):
                per_forward_ms = _measure_batch(callables[variant], iterations=iterations)
                records.append({
                    "role": role,
                    "round": round_index,
                    "variant": variant,
                    "device_per_forward_ms": per_forward_ms,
                })
                completed += 1
                print(
                    f"[gate-c-triton-tiled-base-tuning] {completed}/{total} "
                    f"role={role} round={round_index + 1}/{rounds} variant={variant} "
                    f"device={per_forward_ms:.4f}ms",
                    file=sys.stderr,
                    flush=True,
                )

    return {
        "schema": "fold-v05-gate-c-triton-tiled-base-tuning-v1",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "width": width,
        "rows": rows,
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_sample": iterations,
        "configs": {
            name: {
                "block_n": cfg.block_n,
                "block_m": cfg.block_m,
                "block_k": cfg.block_k,
                "num_warps": cfg.num_warps,
                "input_precision": cfg.input_precision,
            }
            for name, cfg in CONFIGS.items()
        },
        "structures": structures,
        "summary": summarize_records(records, output_gaps),
        "elapsed_seconds": time.perf_counter() - started,
        "diagnostic_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        width=args.width,
        rows=args.rows,
        device=args.device,
        warmup=args.warmup,
        rounds=args.rounds,
        iterations=args.iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
