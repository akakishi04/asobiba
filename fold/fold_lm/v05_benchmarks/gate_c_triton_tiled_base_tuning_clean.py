"""C33: re-run the bounded tiled-base sweep without synchronizing finite scans.

C32 proved that the inherited per-call ``torch.isfinite(value).all()`` dominates
much of the measured Triton overhead on CUDA.  C30 therefore cannot be used as a
pure kernel comparison: every Triton variant paid a host/device synchronization
that the Dense control did not.

C33 repeats the same bounded five-config sweep with structural validation only.
The production runtime is not changed.  CUDA-event and wall-clock medians are
reported separately, and the sweep remains intentionally bounded.
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


class StructuralValidationTunedTiledBaseOnlyLinearBank(TunedTiledBaseOnlyLinearBank):
    """Benchmark-only bank that avoids device reductions during validation."""

    def _validate(self, value: torch.Tensor, module_index: int) -> None:
        if type(module_index) is not int or not 0 <= module_index < self.module_count:
            raise ValueError("module_index out of range")
        if not isinstance(value, torch.Tensor):
            raise TypeError("value must be torch.Tensor")
        if not value.is_floating_point():
            raise TypeError("value must use a floating dtype")
        if value.ndim < 2 or value.shape[-1] != self.input_width:
            raise ValueError("value must end with compressed input width")


def order_for_round(round_index: int) -> tuple[str, ...]:
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    offset = round_index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


@torch.inference_mode()
def _measure_batch(callable_, *, iterations: int) -> dict:
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    wall_started = time.perf_counter()
    start.record()
    for _ in range(iterations):
        callable_()
    end.record()
    end.synchronize()
    wall_seconds = time.perf_counter() - wall_started
    device_ms = float(start.elapsed_time(end))
    return {
        "device_per_forward_ms": device_ms / iterations,
        "wall_per_forward_ms": wall_seconds * 1000.0 / iterations,
    }


def _median(values: list[float]) -> float:
    if not values or any(not math.isfinite(float(v)) or float(v) <= 0.0 for v in values):
        raise ValueError("timing values must be positive and finite")
    return float(statistics.median(float(v) for v in values))


def summarize_records(records: list[dict], output_gaps: dict[str, float]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    roles = {}
    for role in ROLES:
        rows = [r for r in records if r.get("role") == role]
        if not rows:
            continue
        rounds = sorted({int(r["round"]) for r in rows})
        by_round = {}
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("every role/round must contain all variants")
            by_round[round_index] = group

        medians = {}
        for variant in VARIANTS:
            vrows = [r for r in rows if r["variant"] == variant]
            medians[variant] = {
                "device_ms": _median([float(r["device_per_forward_ms"]) for r in vrows]),
                "wall_ms": _median([float(r["wall_per_forward_ms"]) for r in vrows]),
            }

        variants = {}
        for variant in CONFIGS:
            device_ratios = [
                float(group[variant]["device_per_forward_ms"])
                / float(group["dense"]["device_per_forward_ms"])
                for group in by_round.values()
            ]
            wall_ratios = [
                float(group[variant]["wall_per_forward_ms"])
                / float(group["dense"]["wall_per_forward_ms"])
                for group in by_round.values()
            ]
            variants[variant] = {
                "device_median_ms": medians[variant]["device_ms"],
                "wall_median_ms": medians[variant]["wall_ms"],
                "vs_dense_device_paired_median": _median(device_ratios),
                "vs_dense_wall_paired_median": _median(wall_ratios),
                "max_abs_output_gap": float(output_gaps[f"{role}:{variant}"]),
            }
        roles[role] = {
            "dense_device_median_ms": medians["dense"]["device_ms"],
            "dense_wall_median_ms": medians["dense"]["wall_ms"],
            "variants": variants,
        }
    if set(roles) != set(ROLES):
        raise ValueError("records must contain both roles")
    return {"roles": roles}


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
        raise RuntimeError("C33 sync-clean tiled base tuning requires CUDA")
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
    generator = torch.Generator(device="cpu").manual_seed(20260913)
    records: list[dict] = []
    output_gaps: dict[str, float] = {}
    total = len(ROLES) * rounds * len(VARIANTS)
    completed = 0

    for role in ROLES:
        input_width, output_width = role_shape(width, role)
        init = build_synthetic_initialization(input_width, output_width)
        banks = {
            name: StructuralValidationTunedTiledBaseOnlyLinearBank(init, config).to(device)
            for name, config in CONFIGS.items()
        }
        base_weight = next(iter(banks.values())).base
        value = torch.randn(rows, input_width, generator=generator, dtype=torch.float32).to(device)
        dense_out = F.linear(value, base_weight, None)
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
                timing = _measure_batch(callables[variant], iterations=iterations)
                records.append({
                    "role": role,
                    "round": round_index,
                    "variant": variant,
                    **timing,
                })
                completed += 1
                print(
                    f"[gate-c-sync-clean-base-tuning] {completed}/{total} "
                    f"role={role} round={round_index + 1}/{rounds} variant={variant} "
                    f"device={timing['device_per_forward_ms']:.4f}ms "
                    f"wall={timing['wall_per_forward_ms']:.4f}ms",
                    file=sys.stderr,
                    flush=True,
                )

    return {
        "schema": "fold-v05-gate-c-sync-clean-tiled-base-tuning-v1",
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
        "summary": summarize_records(records, output_gaps),
        "elapsed_seconds": time.perf_counter() - started,
        "diagnostic_only": True,
        "production_runtime_modified": False,
        "validation_policy": "structural-only inside measured Triton variants",
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
