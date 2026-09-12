"""C26: width-scale ablation for sparse correction E in the fused Triton runtime.

C25 showed that the current row-wise fused Triton kernel scales poorly as width
grows.  C24 showed that E is cheap at width 32, but C25 keeps correction density
fixed at 3.125%, so correction nnz grows quadratically with width.  C26 isolates
whether that E scan becomes the dominant width-scaling bottleneck.

Diagnostic only: compares dense, full Triton, and Triton with E removed for the
same synthetic width sweep.  The no-E path is not a quality/storage candidate.
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

from fold_lm.v05.triton_runtime import TritonCompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    DEFAULT_WIDTHS,
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

VARIANTS = ("dense", "triton_full", "triton_no_e")


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


def summarize_records(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    points = {}
    identities = sorted({(int(r["width"]), str(r["role"])) for r in records})
    for width, role in identities:
        rows = [r for r in records if int(r["width"]) == width and r["role"] == role]
        rounds = sorted({int(r["round"]) for r in rows})
        by_round = {}
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("each width/role round must contain all variants")
            by_round[round_index] = group

        medians = {
            variant: _median([
                float(r["device_per_forward_ms"])
                for r in rows if r["variant"] == variant
            ])
            for variant in VARIANTS
        }
        full_to_no_e = []
        full_vs_dense = []
        no_e_vs_dense = []
        for group in by_round.values():
            dense = float(group["dense"]["device_per_forward_ms"])
            full = float(group["triton_full"]["device_per_forward_ms"])
            no_e = float(group["triton_no_e"]["device_per_forward_ms"])
            full_to_no_e.append(full / no_e)
            full_vs_dense.append(full / dense)
            no_e_vs_dense.append(no_e / dense)

        points[f"w{width}_{role}"] = {
            "width": width,
            "role": role,
            "rounds": len(rounds),
            "dense_device_median_ms": medians["dense"],
            "triton_full_device_median_ms": medians["triton_full"],
            "triton_no_e_device_median_ms": medians["triton_no_e"],
            "full_to_no_e_slowdown_paired_median": _median(full_to_no_e),
            "triton_full_vs_dense_paired_median": _median(full_vs_dense),
            "triton_no_e_vs_dense_paired_median": _median(no_e_vs_dense),
        }
    return {"points": points}


def run_benchmark(
    *,
    widths: tuple[int, ...] = DEFAULT_WIDTHS,
    device: str | torch.device = "cuda",
    rows: int = 216,
    warmup: int = 20,
    rounds: int = 7,
    iterations: int = 100,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C26 width-scale E ablation requires CUDA")
    if not widths or any(type(w) is not int or w <= 0 for w in widths):
        raise ValueError("widths must contain positive integers")
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
    structures = {}
    total = len(widths) * len(ROLES) * 2 * rounds * len(VARIANTS)
    completed = 0
    generator = torch.Generator(device="cpu").manual_seed(20260912)

    for width in widths:
        for role in ROLES:
            input_width, output_width = role_shape(width, role)
            full_init = build_synthetic_initialization(input_width, output_width)
            no_e_init = without_correction(full_init)
            full_bank = TritonCompressedLinearBank(full_init).to(device)
            no_e_bank = TritonCompressedLinearBank(no_e_init).to(device)
            correction_nnz_per_module = int(full_init.encoded_weights[0].correction_nnz)
            structures[f"w{width}_{role}"] = {
                "input_width": input_width,
                "output_width": output_width,
                "module_count": len(full_init.encoded_weights),
                "correction_density": full_init.metrics[0].correction_density,
                "correction_nnz_per_module": correction_nnz_per_module,
                "estimated_payload_ratio": full_init.accounting.estimated_payload_ratio,
            }

            for module_index, encoded in enumerate(full_init.encoded_weights):
                dense_weight = torch.tensor(
                    np.array(encoded.materialize(), copy=True),
                    dtype=torch.float32,
                    device=device,
                )
                value = torch.randn(rows, input_width, generator=generator, dtype=torch.float32).to(device)
                full_out = full_bank(value, module_index=module_index)
                dense_out = F.linear(value, dense_weight, None)
                no_e_out = no_e_bank(value, module_index=module_index)
                torch.cuda.synchronize()
                torch.testing.assert_close(full_out, dense_out, rtol=1e-4, atol=1e-5)
                if not torch.isfinite(no_e_out).all():
                    raise RuntimeError("no-E diagnostic produced non-finite output")

                callables = {
                    "dense": lambda v=value, w=dense_weight: F.linear(v, w, None),
                    "triton_full": lambda v=value, b=full_bank, mi=module_index: b(v, module_index=mi),
                    "triton_no_e": lambda v=value, b=no_e_bank, mi=module_index: b(v, module_index=mi),
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
                            "width": width,
                            "role": role,
                            "module_index": module_index,
                            "round": round_index,
                            "variant": variant,
                            "device_per_forward_ms": per_forward_ms,
                        })
                        completed += 1
                        print(
                            f"[gate-c-width-e-ablation] {completed}/{total} "
                            f"width={width} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={per_forward_ms:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-width-scale-e-ablation-v1",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "widths": list(widths),
        "rows": rows,
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_sample": iterations,
        "structures": structures,
        "summary": summarize_records(records),
        "elapsed_seconds": time.perf_counter() - started,
        "diagnostic_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--widths", nargs="+", type=int, default=list(DEFAULT_WIDTHS))
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--rows", type=int, default=216)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        widths=tuple(args.widths),
        device=args.device,
        rows=args.rows,
        warmup=args.warmup,
        rounds=args.rounds,
        iterations=args.iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
