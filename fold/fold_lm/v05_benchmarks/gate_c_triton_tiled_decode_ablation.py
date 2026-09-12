"""C29: separate tiled matmul cost from additive codebook decode cost.

C28 proved that row tiling/reuse helps at large row counts, but its no-E compressed
kernel still remains much slower than Dense.  C29 keeps the same width, tile
geometry and compact representation while comparing:

- dense_base: PyTorch F.linear over the shared base matrix only;
- tiled_base: the same base-only transform through the C28-style Triton tiling;
- tiled_codebook: the real tiled no-E compressed transform, base + codebooks.

The benchmark therefore isolates whether the remaining gap is primarily the tiled
matmul/mapping itself or the additive codebook decode performed inside each K tile.
Diagnostic only; no quality/storage conclusion is drawn from the base-only path.
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

from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05.triton_tiled_ablation_runtime import TiledBaseOnlyLinearBank
from fold_lm.v05.benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05.benchmarks.gate_c_triton_width_scale import (
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

VARIANTS = ("dense_base", "tiled_base", "tiled_codebook")
DEFAULT_ROWS = (1, 32, 216)
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
        values = {variant: [] for variant in VARIANTS}
        tiled_base_vs_dense = []
        codebook_to_base = []
        tiled_codebook_vs_dense = []
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("every row/role round must contain all variants")
            dense = float(group["dense_base"]["device_per_forward_ms"])
            base = float(group["tiled_base"]["device_per_forward_ms"])
            codebook = float(group["tiled_codebook"]["device_per_forward_ms"])
            values["dense_base"].append(dense)
            values["tiled_base"].append(base)
            values["tiled_codebook"].append(codebook)
            tiled_base_vs_dense.append(base / dense)
            codebook_to_base.append(codebook / base)
            tiled_codebook_vs_dense.append(codebook / dense)
        points[f"r{rows_count}_{role}"] = {
            "rows": rows_count,
            "role": role,
            "rounds": len(rounds),
            "dense_base_device_median_ms": _median(values["dense_base"]),
            "tiled_base_device_median_ms": _median(values["tiled_base"]),
            "tiled_codebook_device_median_ms": _median(values["tiled_codebook"]),
            "tiled_base_vs_dense_paired_median": _median(tiled_base_vs_dense),
            "codebook_to_base_slowdown_paired_median": _median(codebook_to_base),
            "tiled_codebook_vs_dense_paired_median": _median(tiled_codebook_vs_dense),
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
        raise RuntimeError("C29 tiled decode ablation requires CUDA")
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
        base_bank = TiledBaseOnlyLinearBank(no_e_init).to(device)
        codebook_bank = TiledNoECompressedLinearBank(no_e_init).to(device)
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
            codebook_dense_weight = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device=device,
            )
            base_weight = base_bank.base
            for rows_count in row_counts:
                value = torch.randn(
                    rows_count,
                    input_width,
                    generator=generator,
                    dtype=torch.float32,
                ).to(device)

                dense_base_out = F.linear(value, base_weight, None)
                tiled_base_out = base_bank(value, module_index=module_index)
                dense_codebook_out = F.linear(value, codebook_dense_weight, None)
                tiled_codebook_out = codebook_bank(value, module_index=module_index)
                torch.cuda.synchronize()
                torch.testing.assert_close(tiled_base_out, dense_base_out, rtol=1e-4, atol=1e-5)
                torch.testing.assert_close(tiled_codebook_out, dense_codebook_out, rtol=1e-4, atol=1e-5)

                callables = {
                    "dense_base": lambda v=value, w=base_weight: F.linear(v, w, None),
                    "tiled_base": lambda v=value, b=base_bank, mi=module_index: b(v, module_index=mi),
                    "tiled_codebook": lambda v=value, b=codebook_bank, mi=module_index: b(v, module_index=mi),
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
                            f"[gate-c-triton-tiled-decode] {completed}/{total} "
                            f"width={width} rows={rows_count} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={per_forward_ms:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-triton-tiled-decode-ablation-v1",
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
