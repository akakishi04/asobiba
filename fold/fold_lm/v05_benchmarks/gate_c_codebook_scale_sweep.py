"""C57: runtime scale sweep for the best current compact execution family.

C56 showed that at the real width-32 Up shape most remaining bank-level cost
comes from compact codebook gather/decode, while the same predecoded Triton
matmul is only modestly slower than dense F.linear. C57 asks whether that ratio
improves, stays flat, or worsens as the Linear width grows.

This is a runtime-only synthetic scale diagnostic. It preserves the current
high-fidelity compact structure (2x2 blocks, Q=3, 8 entries, two modules), uses
no sparse correction E, and compares:

- dense F.linear on the exact materialized compact weight;
- predecoded Triton with scalable N16/M64/K32 tiling;
- direct compact Triton using the same tiling plus codebook decode/gather.

No production runtime is modified and no quality claim is made from this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import DirectCompressedLinearBank
from fold_lm.v05.triton_runtime import TritonCompressedLinearBank, triton_runtime_available, triton, tl
from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization


EXPERIMENT_ID = "C57-codebook-runtime-scale-sweep"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
WIDTHS = (32, 64, 128, 256)
ROWS = 1728
ROUNDS = 20
ITERATIONS = 200
WARMUP = 50
VARIANTS = ("dense", "predecoded_triton", "compact_triton")
BLOCK_N = 16
BLOCK_M = 64
BLOCK_K = 32


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _measure(fn) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERATIONS):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


if triton is not None:

    @triton.jit
    def _predecoded_scale_kernel(
        x_ptr,
        w_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
    ):
        pid_n = tl.program_id(0)
        pid_m = tl.program_id(1)
        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
        mask_n = offs_n < N
        mask_m = offs_m < M
        acc = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)

        for k0 in tl.static_range(0, K, BLOCK_K):
            offs_k = k0 + tl.arange(0, BLOCK_K)
            mask_k = offs_k < K
            x = tl.load(
                x_ptr + offs_n[:, None] * K + offs_k[None, :],
                mask=mask_n[:, None] & mask_k[None, :],
                other=0.0,
            )
            w = tl.load(
                w_ptr + offs_m[:, None] * K + offs_k[None, :],
                mask=mask_m[:, None] & mask_k[None, :],
                other=0.0,
            )
            acc += tl.dot(x, tl.trans(w), input_precision="ieee")

        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


    @triton.jit
    def _compact_scale_kernel(
        x_ptr,
        base_ptr,
        codebooks_ptr,
        codes_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
        ENTRIES: tl.constexpr,
        MODULE_INDEX: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
    ):
        pid_n = tl.program_id(0)
        pid_m = tl.program_id(1)
        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
        mask_n = offs_n < N
        mask_m = offs_m < M
        acc = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)

        for k0 in tl.static_range(0, K, BLOCK_K):
            offs_k = k0 + tl.arange(0, BLOCK_K)
            mask_k = offs_k < K
            matrix_mask = mask_m[:, None] & mask_k[None, :]
            x = tl.load(
                x_ptr + offs_n[:, None] * K + offs_k[None, :],
                mask=mask_n[:, None] & mask_k[None, :],
                other=0.0,
            )
            weight = tl.load(
                base_ptr + offs_m[:, None] * K + offs_k[None, :],
                mask=matrix_mask,
                other=0.0,
            )

            row_block = offs_m[:, None] // BR
            col_block = offs_k[None, :] // BC
            inner_row = offs_m[:, None] % BR
            inner_col = offs_k[None, :] % BC

            for q in tl.static_range(0, Q):
                code_offset = (
                    (((MODULE_INDEX * GRID_R + row_block) * GRID_C + col_block) * Q)
                    + q
                )
                code = tl.load(
                    codes_ptr + code_offset,
                    mask=matrix_mask,
                    other=0,
                ).to(tl.int32)
                codebook_offset = (
                    (((q * ENTRIES + code) * BR + inner_row) * BC) + inner_col
                )
                weight += tl.load(
                    codebooks_ptr + codebook_offset,
                    mask=matrix_mask,
                    other=0.0,
                )

            acc += tl.dot(x, tl.trans(weight), input_precision="ieee")

        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


def _predecoded_forward(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    n, k = value.shape
    m = int(weight.shape[0])
    out = torch.empty((n, m), device=value.device, dtype=value.dtype)
    grid = (triton.cdiv(n, BLOCK_N), triton.cdiv(m, BLOCK_M))
    _predecoded_scale_kernel[grid](
        value,
        weight,
        out,
        N=n,
        M=m,
        K=k,
        BLOCK_N=BLOCK_N,
        BLOCK_M=BLOCK_M,
        BLOCK_K=BLOCK_K,
        num_warps=4,
    )
    return out


def _compact_forward(value: torch.Tensor, bank: TritonCompressedLinearBank, module_index: int) -> torch.Tensor:
    n, k = value.shape
    m = int(bank.output_width)
    out = torch.empty((n, m), device=value.device, dtype=value.dtype)
    grid = (triton.cdiv(n, BLOCK_N), triton.cdiv(m, BLOCK_M))
    _compact_scale_kernel[grid](
        value,
        bank.base,
        bank.codebooks,
        bank.codes,
        out,
        N=n,
        M=m,
        K=k,
        GRID_R=bank.grid_rows,
        GRID_C=bank.grid_cols,
        BR=bank.block_rows,
        BC=bank.block_cols,
        Q=bank.codebook_count,
        ENTRIES=bank.entries_per_codebook,
        MODULE_INDEX=module_index,
        BLOCK_N=BLOCK_N,
        BLOCK_M=BLOCK_M,
        BLOCK_K=BLOCK_K,
        num_warps=4,
    )
    return out


def _summarize(records: list[dict]) -> dict:
    points: dict[str, dict] = {}
    for width in WIDTHS:
        rows = [r for r in records if int(r["width"]) == width]
        table = {
            (int(r["module_index"]), int(r["round"]), str(r["variant"])): float(r["device_ms"])
            for r in rows
        }
        values = {
            variant: [
                table[module_index, round_index, variant]
                for module_index in (0, 1)
                for round_index in range(ROUNDS)
            ]
            for variant in VARIANTS
        }
        paired = {}
        for label, a_name, b_name in (
            ("predecoded_over_dense", "predecoded_triton", "dense"),
            ("compact_over_predecoded", "compact_triton", "predecoded_triton"),
            ("compact_over_dense", "compact_triton", "dense"),
        ):
            ratios = []
            for module_index in (0, 1):
                for round_index in range(ROUNDS):
                    ratios.append(
                        table[module_index, round_index, a_name]
                        / table[module_index, round_index, b_name]
                    )
            paired[label] = {
                **_stats(ratios),
                "numerator_faster_samples": sum(v < 1.0 for v in ratios),
                "numerator_slower_samples": sum(v > 1.0 for v in ratios),
            }
        points[str(width)] = {
            "device_ms": {name: _stats(vals) for name, vals in values.items()},
            "paired_ratios": paired,
        }
    return {"points": points}


@torch.inference_mode()
def run(*, protected: Path, fixture: Path, c56_summary: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available() or not triton_runtime_available():
        raise RuntimeError("C57 requires CUDA + Triton")

    c56 = json.loads(c56_summary.read_text(encoding="utf-8"))
    if c56.get("experiment_id") != "C56-real-up-predecoded-matmul-isolation" or c56.get("status") != "PASS":
        raise RuntimeError("C57 requires accepted C56 summary")

    before = _sha256(protected)
    fixture_hash = _sha256(fixture)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(20260913)
    records: list[dict] = []
    structures: dict[str, dict] = {}
    max_gaps: dict[str, dict] = {}
    total = len(WIDTHS) * 2 * ROUNDS * len(VARIANTS)
    completed = 0

    for width in WIDTHS:
        k = width
        m = 2 * width
        init = build_synthetic_initialization(
            k,
            m,
            module_count=2,
            block_rows=2,
            block_cols=2,
            codebook_count=3,
            entries_per_codebook=8,
            correction_density=0.0,
            max_abs_correction=0.0,
            seed=20260913,
        )
        bank = TritonCompressedLinearBank(init).to(device)
        materializer = DirectCompressedLinearBank(init)
        compact_resident_bytes = sum(
            int(buffer.numel() * buffer.element_size())
            for _name, buffer in bank.named_buffers()
        )
        dense_module_bytes = 2 * m * k * 4
        structures[str(width)] = {
            "input_width": k,
            "output_width": m,
            "rows": ROWS,
            "block_rows": 2,
            "block_cols": 2,
            "codebook_count": 3,
            "entries_per_codebook": 8,
            "module_count": 2,
            "dense_module_bytes": dense_module_bytes,
            "compact_runtime_resident_bytes": compact_resident_bytes,
            "compact_runtime_resident_ratio": compact_resident_bytes / dense_module_bytes,
            "estimated_serialized_payload_bytes": int(init.accounting.estimated_encoded_payload_bytes),
            "estimated_serialized_payload_ratio": float(init.accounting.estimated_payload_ratio),
        }

        value = torch.randn(ROWS, k, generator=generator, dtype=torch.float32).to(device)
        max_gaps[str(width)] = {}

        for module_index in (0, 1):
            dense_weight = materializer.materialized_weight(module_index).to(device)
            dense_call = lambda v=value, w=dense_weight: F.linear(v, w, None)
            predecoded_call = lambda v=value, w=dense_weight: _predecoded_forward(v, w)
            compact_call = lambda v=value, b=bank, mi=module_index: _compact_forward(v, b, mi)

            dense_out = dense_call()
            predecoded_out = predecoded_call()
            compact_out = compact_call()
            torch.cuda.synchronize()
            torch.testing.assert_close(predecoded_out, dense_out, rtol=1e-4, atol=1e-5)
            torch.testing.assert_close(compact_out, dense_out, rtol=1e-4, atol=1e-5)
            max_gaps[str(width)][str(module_index)] = {
                "predecoded": float((predecoded_out - dense_out).abs().max().item()),
                "compact": float((compact_out - dense_out).abs().max().item()),
            }

            calls = {
                "dense": dense_call,
                "predecoded_triton": predecoded_call,
                "compact_triton": compact_call,
            }
            for variant in VARIANTS:
                for _ in range(WARMUP):
                    calls[variant]()
            torch.cuda.synchronize()

            for round_index in range(ROUNDS):
                offset = round_index % len(VARIANTS)
                order = VARIANTS[offset:] + VARIANTS[:offset]
                for variant in order:
                    timing = _measure(calls[variant])
                    records.append({
                        "width": width,
                        "module_index": module_index,
                        "round": round_index,
                        "variant": variant,
                        "device_ms": timing,
                    })
                    completed += 1
                print(
                    f"[C57] width={width} module={module_index} round={round_index + 1}/{ROUNDS} "
                    f"checked ({completed}/{total})",
                    flush=True,
                )

    after = _sha256(protected)
    if after != before:
        raise RuntimeError("protected C37 result changed during C57")

    summary = _summarize(records)
    compact_ratios = [
        float(summary["points"][str(width)]["paired_ratios"]["compact_over_dense"]["median"])
        for width in WIDTHS
    ]
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "synthetic width scaling diagnostic for current best codebook execution family",
        "widths": list(WIDTHS),
        "geometry": {
            "rows": ROWS,
            "block_n": BLOCK_N,
            "block_m": BLOCK_M,
            "block_k": BLOCK_K,
            "num_warps": 4,
            "up_like_shape": "K=width, M=2*width",
        },
        "structures": structures,
        "summary": summary,
        "compact_over_dense_median_curve": {
            str(width): ratio for width, ratio in zip(WIDTHS, compact_ratios)
        },
        "max_abs_output_gaps": max_gaps,
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "fixture_sha256": fixture_hash,
        "C56_summary_sha256": _sha256(c56_summary),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "synthetic scale fixtures are runtime-only and do not establish task quality",
            "no-E isolates codebook execution and is not a final quality candidate",
            "tile geometry is fixed across widths and may not be optimal at every scale",
            "C57 is a pivot decision diagnostic, not a Gate-C pass test",
        ],
        "records": records,
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--c56-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected=args.protected_result,
        fixture=args.fixture,
        c56_summary=args.c56_summary,
        output_dir=args.output_dir,
    )
    display = {key: value for key, value in result.items() if key != "records"}
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C57 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
