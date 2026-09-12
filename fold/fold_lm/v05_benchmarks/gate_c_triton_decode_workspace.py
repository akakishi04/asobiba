"""C31: compare fused tiled execution with decode-to-workspace plus cuBLAS.

C29/C30 showed that most of the remaining gap comes from the custom Triton GEMM,
not from additive codebook lookup.  C31 therefore measures a bounded alternative:
materialize one active no-E module into a reusable dense workspace, then execute
``F.linear`` through the vendor GEMM path.

Variants:
- dense: pre-materialized exact no-E weight + F.linear;
- tiled_no_e: C28 compact tiled kernel, no dense weight workspace;
- decode_only: compact -> one dense workspace, no GEMM;
- decode_workspace: decode the same workspace every call, then F.linear.

The decoded workspace is diagnostic only.  It is explicitly counted as runtime
resident scratch and is not a Gate-C compact-resident candidate.
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

from fold_lm.v05.triton_decode_workspace_runtime import DecodedWorkspaceNoELinearBank
from fold_lm.v05.triton_tiled_runtime import TiledNoECompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
    ROLES,
    build_synthetic_initialization,
    role_shape,
)

VARIANTS = ("dense", "tiled_no_e", "decode_only", "decode_workspace")
DEFAULT_WIDTH = 256
DEFAULT_ROWS = (1, 32, 216)


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
        tiled_vs_dense = []
        workspace_vs_dense = []
        tiled_to_workspace = []
        decode_fraction = []
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("every row/role round must contain all variants")
            dense = float(group["dense"]["device_per_forward_ms"])
            tiled = float(group["tiled_no_e"]["device_per_forward_ms"])
            decode = float(group["decode_only"]["device_per_forward_ms"])
            workspace = float(group["decode_workspace"]["device_per_forward_ms"])
            for variant, value in (
                ("dense", dense),
                ("tiled_no_e", tiled),
                ("decode_only", decode),
                ("decode_workspace", workspace),
            ):
                values[variant].append(value)
            tiled_vs_dense.append(tiled / dense)
            workspace_vs_dense.append(workspace / dense)
            tiled_to_workspace.append(tiled / workspace)
            decode_fraction.append(decode / workspace)
        points[f"r{rows_count}_{role}"] = {
            "rows": rows_count,
            "role": role,
            "rounds": len(rounds),
            "dense_device_median_ms": _median(values["dense"]),
            "tiled_no_e_device_median_ms": _median(values["tiled_no_e"]),
            "decode_only_device_median_ms": _median(values["decode_only"]),
            "decode_workspace_device_median_ms": _median(values["decode_workspace"]),
            "tiled_vs_dense_paired_median": _median(tiled_vs_dense),
            "decode_workspace_vs_dense_paired_median": _median(workspace_vs_dense),
            "tiled_to_decode_workspace_speedup_paired_median": _median(tiled_to_workspace),
            "decode_fraction_of_workspace_paired_median": _median(decode_fraction),
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
        raise RuntimeError("C31 decoded-workspace diagnostic requires CUDA")
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
    generator = torch.Generator(device="cpu").manual_seed(20260912)
    records: list[dict] = []
    structures = {}
    total = len(row_counts) * len(ROLES) * 2 * rounds * len(VARIANTS)
    completed = 0
    max_weight_gap = 0.0
    max_output_gap = 0.0

    for role in ROLES:
        input_width, output_width = role_shape(width, role)
        full_init = build_synthetic_initialization(input_width, output_width)
        no_e_init = without_correction(full_init)
        tiled_bank = TiledNoECompressedLinearBank(no_e_init).to(device)
        workspace_bank = DecodedWorkspaceNoELinearBank(no_e_init).to(device)
        structures[role] = {
            "width": width,
            "input_width": input_width,
            "output_width": output_width,
            "module_count": len(no_e_init.encoded_weights),
            "workspace_bytes": workspace_bank.workspace_bytes,
            "workspace_is_dense_runtime_scratch": True,
        }

        for module_index, encoded in enumerate(no_e_init.encoded_weights):
            dense_weight = torch.tensor(
                np.array(encoded.materialize(), copy=True),
                dtype=torch.float32,
                device=device,
            )
            decoded = workspace_bank.decode(module_index=module_index)
            torch.cuda.synchronize()
            max_weight_gap = max(max_weight_gap, float((decoded - dense_weight).abs().max().item()))
            torch.testing.assert_close(decoded, dense_weight, rtol=1e-5, atol=1e-6)

            for rows_count in row_counts:
                value = torch.randn(
                    rows_count,
                    input_width,
                    generator=generator,
                    dtype=torch.float32,
                ).to(device)
                dense_out = F.linear(value, dense_weight, None)
                tiled_out = tiled_bank(value, module_index=module_index)
                workspace_out = workspace_bank(value, module_index=module_index)
                torch.cuda.synchronize()
                torch.testing.assert_close(tiled_out, dense_out, rtol=1e-4, atol=1e-5)
                torch.testing.assert_close(workspace_out, dense_out, rtol=1e-4, atol=1e-5)
                max_output_gap = max(
                    max_output_gap,
                    float((workspace_out - dense_out).abs().max().item()),
                )

                callables = {
                    "dense": lambda v=value, w=dense_weight: F.linear(v, w, None),
                    "tiled_no_e": lambda v=value, b=tiled_bank, mi=module_index: b(v, module_index=mi),
                    "decode_only": lambda b=workspace_bank, mi=module_index: b.decode(module_index=mi),
                    "decode_workspace": lambda v=value, b=workspace_bank, mi=module_index: b(v, module_index=mi),
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
                            f"[gate-c-decode-workspace] {completed}/{total} "
                            f"width={width} rows={rows_count} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={per_forward_ms:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-decode-workspace-v1",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "width": width,
        "row_counts": list(row_counts),
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_sample": iterations,
        "structures": structures,
        "max_abs_decoded_weight_gap": max_weight_gap,
        "max_abs_decode_workspace_output_gap": max_output_gap,
        "summary": summarize_records(records),
        "elapsed_seconds": time.perf_counter() - started,
        "diagnostic_only": True,
        "gate_c_candidate": False,
        "reason_not_candidate": "uses one dense decoded runtime workspace",
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
