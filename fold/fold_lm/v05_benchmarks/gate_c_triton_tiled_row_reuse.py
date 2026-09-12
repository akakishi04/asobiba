"""C28: compare row-wise and batch-tiled no-E Triton compressed Linear runtimes.

C27 showed that the existing no-E row-wise kernel is already expensive for one
row and becomes substantially worse at 216 rows.  C28 keeps width=256 and the
same compact representation but adds a tiled execution mapping that decodes one
weight tile once for several input rows.

Diagnostic only.  The no-E representation is used so the experiment isolates
batch-axis decode reuse before sparse correction E is reintroduced.
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
from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

VARIANTS = ("dense", "rowwise_no_e", "tiled_no_e")
DEFAULT_ROWS = (1, 8, 32, 216)
DEFAULT_WIDTH = 256


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
    identities = sorted({(int(r["rows"]), str(r["role"])) for r in records})
    for rows_count, role in identities:
        rows = [r for r in records if int(r["rows"]) == rows_count and r["role"] == role]
        rounds = sorted({int(r["round"]) for r in rows})
        dense_values = []
        rowwise_values = []
        tiled_values = []
        rowwise_vs_dense = []
        tiled_vs_dense = []
        rowwise_to_tiled = []
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("every row/role round must contain all variants")
            dense = float(group["dense"]["device_per_forward_ms"])
            rowwise = float(group["rowwise_no_e"]["device_per_forward_ms"])
            tiled = float(group["tiled_no_e"]["device_per_forward_ms"])
            dense_values.append(dense)
            rowwise_values.append(rowwise)
            tiled_values.append(tiled)
            rowwise_vs_dense.append(rowwise / dense)
            tiled_vs_dense.append(tiled / dense)
            rowwise_to_tiled.append(rowwise / tiled)
        points[f"r{rows_count}_{role}"] = {
            "rows": rows_count,
            "role": role,
            "rounds": len(rounds),
            "dense_device_median_ms": _median(dense_values),
            "rowwise_no_e_device_median_ms": _median(rowwise_values),
            "tiled_no_e_device_median_ms": _median(tiled_values),
            "rowwise_vs_dense_paired_median": _median(rowwise_vs_dense),
            "tiled_vs_dense_paired_median": _median(tiled_vs_dense),
            "rowwise_to_tiled_speedup_paired_median": _median(rowwise_to_tiled),
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
        raise RuntimeError("C28 tiled row-reuse diagnostic requires CUDA")
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
    records: list[dict] = []
    structures = {}
    total = len(row_counts) * len(ROLES) * 2 * rounds * len(VARIANTS)
    completed = 0
    generator = torch.Generator(device="cpu").manual_seed(20260912)

    for role in ROLES:
        input_width, output_width = role_shape(width, role)
        full_init = build_synthetic_initialization(input_width, output_width)
        no_e_init = without_correction(full_init)
        rowwise_bank = TritonCompressedLinearBank(no_e_init).to(device)
        tiled_bank = TiledNoECompressedLinearBank(no_e_init).to(device)
        structures[role] = {
            "width": width,
            "input_width": input_width,
            "output_width": output_width,
            "module_count": len(no_e_init.encoded_weights),
            "codebook_count": int(no_e_init.template.codebook_count),
            "entries_per_codebook": int(no_e_init.template.entries_per_codebook),
            "block_rows": int(no_e_init.template.block_rows),
            "block_cols": int(no_e_init.template.block_cols),
            "tile_rows": 16,
            "tile_outputs": 16,
            "tile_k": 32,
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
                rowwise_out = rowwise_bank(value, module_index=module_index)
                tiled_out = tiled_bank(value, module_index=module_index)
                torch.cuda.synchronize()
                torch.testing.assert_close(rowwise_out, dense_out, rtol=1e-4, atol=1e-5)
                torch.testing.assert_close(tiled_out, dense_out, rtol=1e-4, atol=1e-5)

                callables = {
                    "dense": lambda v=value, w=dense_weight: F.linear(v, w, None),
                    "rowwise_no_e": lambda v=value, b=rowwise_bank, mi=module_index: b(v, module_index=mi),
                    "tiled_no_e": lambda v=value, b=tiled_bank, mi=module_index: b(v, module_index=mi),
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
                            "rows": rows_count,
                            "role": role,
                            "module_index": module_index,
                            "round": round_index,
                            "variant": variant,
                            "device_per_forward_ms": per_forward_ms,
                        })
                        completed += 1
                        print(
                            f"[gate-c-triton-tiled-row] {completed}/{total} "
                            f"width={width} rows={rows_count} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={per_forward_ms:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-triton-tiled-row-reuse-v1",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "width": width,
        "row_counts": list(row_counts),
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
