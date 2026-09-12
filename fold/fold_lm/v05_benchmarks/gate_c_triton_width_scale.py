"""C25: synthetic width-scaling diagnostic for the fused V5-C Triton Linear.

C24 showed that sparse correction E is not the dominant cost at the current tiny
shape; the remaining overhead is mostly the shared-base/codebook execution path.
C25 therefore asks a different question: how does the Dense-vs-compressed runtime
ratio change as the Linear width grows while the compression structure stays
similar?

This is a runtime diagnostic, not a quality benchmark.  It constructs deterministic
synthetic compressed Linear banks with the current high-fidelity structure:

- hidden width = 2 * model width;
- 2x2 blocks;
- 3 additive codebooks, 8 entries each;
- two modules sharing base/codebooks;
- sparse correction density 3.125% with |E| <= 0.15.

For each width and both up/down roles, the exact materialized compressed weight is
used as the Dense reference, so Dense and Triton compute the same transform.  CUDA
Events, batched forwards, rotating measurement order and paired round ratios reduce
Windows/WDDM timing noise.
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

from fold_lm.v05.compression_init import (
    CompressionInitialization,
    InitializationAccounting,
    ReconstructionMetrics,
)
from fold_lm.v05.compression_v5c import BlockCodebookTemplate, EncodedBlockWeight
from fold_lm.v05.triton_runtime import TritonCompressedLinearBank


ROLES = ("up", "down")
VARIANTS = ("dense", "triton")
DEFAULT_WIDTHS = (32, 64, 128, 256)
DEFAULT_CORRECTION_DENSITY = 0.03125


def order_for_round(round_index: int) -> tuple[str, ...]:
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    return VARIANTS if round_index % 2 == 0 else tuple(reversed(VARIANTS))


def role_shape(width: int, role: str) -> tuple[int, int]:
    if type(width) is not int or width <= 0:
        raise ValueError("width must be a positive integer")
    if role == "up":
        return width, width * 2
    if role == "down":
        return width * 2, width
    raise ValueError("unknown role")


def _bits_per_code(entries: int) -> int:
    if type(entries) is not int or entries <= 0:
        raise ValueError("entries must be positive")
    return 0 if entries == 1 else int(math.ceil(math.log2(entries)))


def build_synthetic_initialization(
    input_width: int,
    output_width: int,
    *,
    module_count: int = 2,
    block_rows: int = 2,
    block_cols: int = 2,
    codebook_count: int = 3,
    entries_per_codebook: int = 8,
    correction_density: float = DEFAULT_CORRECTION_DENSITY,
    max_abs_correction: float = 0.15,
    seed: int = 20260912,
) -> CompressionInitialization:
    for name, value in (("input_width", input_width), ("output_width", output_width), ("module_count", module_count)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if output_width % block_rows != 0 or input_width % block_cols != 0:
        raise ValueError("shape must be divisible by block dimensions")
    if not 0.0 <= float(correction_density) <= 1.0:
        raise ValueError("correction_density must be in [0, 1]")

    rng = np.random.default_rng(seed + input_width * 17 + output_width * 31)
    scale = 1.0 / math.sqrt(input_width)
    base = rng.normal(0.0, scale, size=(output_width, input_width)).astype(np.float64)
    codebooks = rng.normal(
        0.0,
        scale * 0.08,
        size=(codebook_count, entries_per_codebook, block_rows, block_cols),
    ).astype(np.float64)
    template = BlockCodebookTemplate(
        base=base,
        codebooks=codebooks,
        block_rows=block_rows,
        block_cols=block_cols,
    )

    matrix_entries = output_width * input_width
    correction_nnz = int(round(matrix_entries * float(correction_density)))
    correction_nnz = min(matrix_entries, max(0, correction_nnz))
    encoded = []
    metrics = []
    for module_index in range(module_count):
        codes = rng.integers(
            0,
            entries_per_codebook,
            size=(template.grid_rows, template.grid_cols, codebook_count),
            dtype=np.int64,
        )
        if correction_nnz:
            flat = np.sort(rng.choice(matrix_entries, size=correction_nnz, replace=False))
            rows, cols = np.unravel_index(flat, (output_width, input_width))
            indices = np.stack([rows, cols], axis=1).astype(np.int64, copy=False)
            values = rng.uniform(
                -max_abs_correction,
                max_abs_correction,
                size=correction_nnz,
            ).astype(np.float64)
        else:
            indices = np.empty((0, 2), dtype=np.int64)
            values = np.empty((0,), dtype=np.float64)
        encoded.append(
            EncodedBlockWeight(
                template=template,
                codes=codes,
                correction_indices=indices,
                correction_values=values,
                max_correction_entries=correction_nnz,
                max_abs_correction=max_abs_correction,
            )
        )
        metrics.append(
            ReconstructionMetrics(
                rmse=0.0,
                max_abs_error=0.0,
                correction_nnz=correction_nnz,
                correction_density=correction_nnz / matrix_entries,
            )
        )

    dense_bytes = module_count * matrix_entries * 4
    shared_bytes = (base.size + codebooks.size) * 4
    code_bits = (
        module_count
        * template.grid_rows
        * template.grid_cols
        * codebook_count
        * _bits_per_code(entries_per_codebook)
    )
    code_bytes = (code_bits + 7) // 8
    correction_bytes = module_count * correction_nnz * 12
    accounting = InitializationAccounting(
        dense_float32_bytes=int(dense_bytes),
        shared_continuous_float32_bytes=int(shared_bytes),
        discrete_code_bits=int(code_bits),
        discrete_code_bytes=int(code_bytes),
        correction_payload_bytes=int(correction_bytes),
        estimated_encoded_payload_bytes=int(shared_bytes + code_bytes + correction_bytes),
    )
    return CompressionInitialization(
        template=template,
        encoded_weights=tuple(encoded),
        metrics=tuple(metrics),
        accounting=accounting,
    )


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
        paired = []
        dense_values = []
        triton_values = []
        for round_index in rounds:
            group = {r["variant"]: r for r in rows if int(r["round"]) == round_index}
            if set(group) != set(VARIANTS):
                raise ValueError("every width/role round must contain dense and triton")
            dense = float(group["dense"]["device_per_forward_ms"])
            triton = float(group["triton"]["device_per_forward_ms"])
            dense_values.append(dense)
            triton_values.append(triton)
            paired.append(triton / dense)
        key = f"w{width}_{role}"
        points[key] = {
            "width": width,
            "role": role,
            "rounds": len(rounds),
            "dense_device_median_ms": _median(dense_values),
            "triton_device_median_ms": _median(triton_values),
            "triton_vs_dense_paired_median": _median(paired),
            "triton_vs_dense_paired_min": min(paired),
            "triton_vs_dense_paired_max": max(paired),
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
        raise RuntimeError("C25 width scaling diagnostic requires CUDA")
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
            init = build_synthetic_initialization(input_width, output_width)
            bank = TritonCompressedLinearBank(init).to(device)
            structures[f"w{width}_{role}"] = {
                "input_width": input_width,
                "output_width": output_width,
                "module_count": len(init.encoded_weights),
                "correction_density": init.metrics[0].correction_density,
                "estimated_payload_ratio": init.accounting.estimated_payload_ratio,
            }

            for module_index, encoded in enumerate(init.encoded_weights):
                dense_weight = torch.tensor(
                    np.array(encoded.materialize(), copy=True),
                    dtype=torch.float32,
                    device=device,
                )
                value = torch.randn(
                    rows,
                    input_width,
                    generator=generator,
                    dtype=torch.float32,
                ).to(device)
                triton_out = bank(value, module_index=module_index)
                dense_out = F.linear(value, dense_weight, None)
                torch.cuda.synchronize()
                torch.testing.assert_close(triton_out, dense_out, rtol=1e-4, atol=1e-5)

                callables = {
                    "dense": lambda v=value, w=dense_weight: F.linear(v, w, None),
                    "triton": lambda v=value, b=bank, mi=module_index: b(v, module_index=mi),
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
                            f"[gate-c-triton-width-scale] {completed}/{total} "
                            f"width={width} role={role} module={module_index} "
                            f"round={round_index + 1}/{rounds} variant={variant} "
                            f"device={per_forward_ms:.4f}ms",
                            file=sys.stderr,
                            flush=True,
                        )

    return {
        "schema": "fold-v05-gate-c-triton-width-scale-v1",
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
