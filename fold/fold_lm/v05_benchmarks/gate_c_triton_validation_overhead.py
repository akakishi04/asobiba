"""C32: isolate synchronizing validation overhead in V5-C Triton runtimes.

The C31 measurement audit established two benchmark defects:

1. the inherited compact ``_validate`` performs ``torch.isfinite(value).all()``
   and therefore synchronizes CPU/GPU on every CUDA forward;
2. several diagnostic summaries grouped only by ``round`` and silently
   overwrote module 0 with module 1.

C32 does not change the production runtime.  It compares the existing tiled and
hybrid no-E paths against diagnostic subclasses that keep only structural input
validation (type/dtype/shape/module bounds) and skip the per-call finite scan.
Both CUDA-event time and wall time are reported.  Summaries pair by
``(module_index, round)`` so every module contributes.

This is diagnostic only.  A production validation-policy change should be made
only after this experiment quantifies the cost and confirms numerical parity.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

from fold_lm.v05.triton_hybrid_runtime import HybridNoECompressedLinearBank
from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

VARIANTS = (
    "dense",
    "tiled_full_validation",
    "tiled_structural_validation",
    "hybrid_full_validation",
    "hybrid_structural_validation",
)
DEFAULT_WIDTH = 256
DEFAULT_ROWS = (1, 216)


class _StructuralValidationMixin:
    """Benchmark-only validation without any device reduction/synchronization."""

    def _validate(self, value: torch.Tensor, module_index: int) -> None:
        if type(module_index) is not int or not 0 <= module_index < self.module_count:
            raise ValueError("module_index out of range")
        if not isinstance(value, torch.Tensor):
            raise TypeError("value must be torch.Tensor")
        if not value.is_floating_point():
            raise TypeError("value must use a floating dtype")
        if value.ndim < 2 or value.shape[-1] != self.input_width:
            raise ValueError("value must end with compressed input width")


class StructuralValidationTiledNoECompressedLinearBank(
    _StructuralValidationMixin,
    TiledNoECompressedLinearBank,
):
    pass


class StructuralValidationHybridNoECompressedLinearBank(
    _StructuralValidationMixin,
    HybridNoECompressedLinearBank,
):
    pass


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


def summarize_records(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    points = {}
    identities = sorted({(int(r["rows"]), str(r["role"])) for r in records})
    for rows_count, role in identities:
        rows = [r for r in records if int(r["rows"]) == rows_count and r["role"] == role]
        keys = sorted({(int(r["module_index"]), int(r["round"])) for r in rows})
        by_key = {key: {} for key in keys}
        for row in rows:
            key = (int(row["module_index"]), int(row["round"]))
            variant = row["variant"]
            if variant not in VARIANTS:
                raise ValueError("unknown variant")
            if variant in by_key[key]:
                raise ValueError("duplicate variant for module/round")
            by_key[key][variant] = row
        if any(set(group) != set(VARIANTS) for group in by_key.values()):
            raise ValueError("every module/round must contain all variants")

        medians = {}
        for variant in VARIANTS:
            medians[variant] = {
                "device_ms": _median([
                    float(r["device_per_forward_ms"])
                    for r in rows if r["variant"] == variant
                ]),
                "wall_ms": _median([
                    float(r["wall_per_forward_ms"])
                    for r in rows if r["variant"] == variant
                ]),
            }

        def paired(numerator: str, denominator: str, metric: str) -> float:
            return _median([
                float(group[numerator][metric]) / float(group[denominator][metric])
                for group in by_key.values()
            ])

        points[f"r{rows_count}_{role}"] = {
            "rows": rows_count,
            "role": role,
            "paired_samples": len(keys),
            "variants": medians,
            "paired_ratios": {
                "tiled_full_vs_dense_device": paired(
                    "tiled_full_validation", "dense", "device_per_forward_ms"
                ),
                "tiled_structural_vs_dense_device": paired(
                    "tiled_structural_validation", "dense", "device_per_forward_ms"
                ),
                "tiled_full_to_structural_device": paired(
                    "tiled_full_validation", "tiled_structural_validation", "device_per_forward_ms"
                ),
                "hybrid_full_vs_dense_device": paired(
                    "hybrid_full_validation", "dense", "device_per_forward_ms"
                ),
                "hybrid_structural_vs_dense_device": paired(
                    "hybrid_structural_validation", "dense", "device_per_forward_ms"
                ),
                "hybrid_full_to_structural_device": paired(
                    "hybrid_full_validation", "hybrid_structural_validation", "device_per_forward_ms"
                ),
                "tiled_full_vs_dense_wall": paired(
                    "tiled_full_validation", "dense", "wall_per_forward_ms"
                ),
                "tiled_structural_vs_dense_wall": paired(
                    "tiled_structural_validation", "dense", "wall_per_forward_ms"
                ),
                "tiled_full_to_structural_wall": paired(
                    "tiled_full_validation", "tiled_structural_validation", "wall_per_forward_ms"
                ),
                "hybrid_full_vs_dense_wall": paired(
                    "hybrid_full_validation", "dense", "wall_per_forward_ms"
                ),
                "hybrid_structural_vs_dense_wall": paired(
                    "hybrid_structural_validation", "dense", "wall_per_forward_ms"
                ),
                "hybrid_full_to_structural_wall": paired(
                    "hybrid_full_validation", "hybrid_structural_validation", "wall_per_forward_ms"
                ),
            },
        }
    return {"points": points}


def run_benchmark(
    *,
    width: int = DEFAULT_WIDTH,
    row_counts: tuple[int, ...] = DEFAULT_ROWS,
    device: str | torch.device = "cuda",
    warmup: int = 20,
    rounds: int = 7,
    iterations: int = 100,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C32 validation-overhead diagnostic requires CUDA")
    if type(width) is not int or width <= 0:
        raise ValueError("width must be positive")
    if not row_counts or any(type(r) is not int or r <= 0 for r in row_counts):
        raise ValueError("row_counts must contain positive integers")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(rounds) is not int or rounds <= 0:
        raise ValueError("rounds must be positive")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")

    started = time.perf_counter()
    generator = torch.Generator(device="cpu").manual_seed(20260913)
    records: list[dict] = []
    structures = {}
    output_gaps = {}
    total = len(row_counts) * len(ROLES) * 2 * rounds * len(VARIANTS)
    completed = 0

    for role in ROLES:
        input_width, output_width = role_shape(width, role)
        full_init = build_synthetic_initialization(input_width, output_width)
        no_e_init = without_correction(full_init)
        tiled_full = TiledNoECompressedLinearBank(no_e_init).to(device)
        tiled_structural = StructuralValidationTiledNoECompressedLinearBank(no_e_init).to(device)
        hybrid_full = HybridNoECompressedLinearBank(no_e_init).to(device)
        hybrid_structural = StructuralValidationHybridNoECompressedLinearBank(no_e_init).to(device)
        structures[role] = {
            "width": width,
            "input_width": input_width,
            "output_width": output_width,
            "module_count": len(no_e_init.encoded_weights),
            "full_validation": "structural checks + torch.isfinite(value).all()",
            "structural_validation": "type/dtype/shape/module checks only",
        }

        for module_index, encoded in enumerate(no_e_init.encoded_weights):
            dense_weight = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device=device,
            )
            for rows_count in row_counts:
                value = torch.randn(
                    rows_count,
                    input_width,
                    generator=generator,
                    dtype=torch.float32,
                ).to(device)
                dense_out = F.linear(value, dense_weight, None)
                outputs = {
                    "tiled_full_validation": tiled_full(value, module_index=module_index),
                    "tiled_structural_validation": tiled_structural(value, module_index=module_index),
                    "hybrid_full_validation": hybrid_full(value, module_index=module_index),
                    "hybrid_structural_validation": hybrid_structural(value, module_index=module_index),
                }
                torch.cuda.synchronize()
                for name, output in outputs.items():
                    torch.testing.assert_close(output, dense_out, rtol=1e-4, atol=1e-5)
                    output_gaps[f"r{rows_count}_{role}_m{module_index}_{name}"] = float(
                        (output - dense_out).abs().max().item()
                    )

                callables = {
                    "dense": lambda v=value, w=dense_weight: F.linear(v, w, None),
                    "tiled_full_validation": lambda v=value, b=tiled_full, mi=module_index: b(v, module_index=mi),
                    "tiled_structural_validation": lambda v=value, b=tiled_structural, mi=module_index: b(v, module_index=mi),
                    "hybrid_full_validation": lambda v=value, b=hybrid_full, mi=module_index: b(v, module_index=mi),
                    "hybrid_structural_validation": lambda v=value, b=hybrid_structural, mi=module_index: b(v, module_index=mi),
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
                            "width": width,
                            "rows": rows_count,
                            "role": role,
                            "module_index": module_index,
                            "round": round_index,
                            "variant": variant,
                            **timing,
                        })
                        completed += 1
                        print(
                            f"[gate-c-validation-overhead] {completed}/{total} "
                            f"rows={rows_count} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={timing['device_per_forward_ms']:.4f}ms "
                            f"wall={timing['wall_per_forward_ms']:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-triton-validation-overhead-v1",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "width": width,
        "row_counts": list(row_counts),
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_sample": iterations,
        "structures": structures,
        "max_abs_output_gap_by_case": output_gaps,
        "summary": summarize_records(records),
        "elapsed_seconds": time.perf_counter() - started,
        "diagnostic_only": True,
        "production_runtime_modified": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--rows", nargs="+", type=int, default=list(DEFAULT_ROWS))
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
        row_counts=tuple(args.rows),
        device=args.device,
        warmup=args.warmup,
        rounds=args.rounds,
        iterations=args.iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
