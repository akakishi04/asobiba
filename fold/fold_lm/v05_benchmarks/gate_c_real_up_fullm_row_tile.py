"""C54: real-Up full-M row-tile diagnostic for compact codebook execution.

C53 localized the dominant bank-level Up cost to the codebook-delta/decode path,
while the row-wise shared-base computation was close to dense.  C50 tested the
existing 16x16 tiled mapping and found it slightly slower than the tuned row-wise
kernel for the real Up shape.  That does not answer whether the *shape mapping*
was the problem: C50 decoded four separate 16-channel output tiles for each row
tile even though the real Up output width is only 64.

C54 keeps the compact representation unchanged and asks one bounded question:

    does one program owning all 64 output channels, with one decoded 64x32 weight
    tile reused across 16 or 32 activation rows, materially beat the tuned
    row-wise BM64/W4 execution?

The experiment is deliberately no-E so correction cost does not obscure the
codebook microarchitecture question.  It does not modify production runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import DirectCompressedLinearBank
from fold_lm.v05.triton_runtime import (
    TritonCompressedLinearBank,
    _compressed_linear_kernel,
    triton_runtime_available,
    triton,
    tl,
)
from fold_lm.v05_benchmarks.gate_c_triton_validation_overhead import (
    _StructuralValidationMixin,
)
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import (
    without_correction,
)
from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import (
    _load_initializations,
)


EXPERIMENT_ID = "C54-real-up-fullm-row-tile"
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
DEFAULT_ROWS = 216
DEFAULT_SLOTS = 8
DEFAULT_WIDTH = 32
ROUNDS = 40
ITERATIONS = 500
WARMUP = 100
VARIANTS = (
    "dense_no_e",
    "rowwise_bm64",
    "fullm_n16",
    "fullm_n32",
)


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


def _measure(callable_) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERATIONS):
        callable_()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _summarize(records: list[dict]) -> dict:
    table: dict[tuple[int, int, str], float] = {}
    for record in records:
        key = (
            int(record["module_index"]),
            int(record["round"]),
            str(record["variant"]),
        )
        value = float(record["device_ms_per_forward"])
        if record["variant"] not in VARIANTS or key in table:
            raise ValueError("invalid or duplicate C54 timing record")
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("C54 timings must be positive and finite")
        table[key] = value

    expected = {
        (module_index, round_index, variant)
        for module_index in (0, 1)
        for round_index in range(ROUNDS)
        for variant in VARIANTS
    }
    if set(table) != expected:
        raise ValueError("incomplete C54 timing table")

    result = {
        "device_ms_per_forward": {
            variant: _stats(
                [
                    table[module_index, round_index, variant]
                    for module_index in (0, 1)
                    for round_index in range(ROUNDS)
                ]
            )
            for variant in VARIANTS
        },
        "paired_comparisons": {},
    }

    comparisons = (
        ("rowwise_over_dense", "rowwise_bm64", "dense_no_e"),
        ("fullm_n16_over_rowwise", "fullm_n16", "rowwise_bm64"),
        ("fullm_n32_over_rowwise", "fullm_n32", "rowwise_bm64"),
        ("fullm_n16_over_dense", "fullm_n16", "dense_no_e"),
        ("fullm_n32_over_dense", "fullm_n32", "dense_no_e"),
        ("fullm_n32_over_n16", "fullm_n32", "fullm_n16"),
    )

    for label, numerator, denominator in comparisons:
        ratios: list[float] = []
        deltas_us: list[float] = []
        for module_index in (0, 1):
            for round_index in range(ROUNDS):
                a = table[module_index, round_index, numerator]
                b = table[module_index, round_index, denominator]
                ratios.append(a / b)
                deltas_us.append((a - b) * 1000.0)
        result["paired_comparisons"][label] = {
            "ratio": {
                **_stats(ratios),
                "numerator_faster_samples": sum(value < 1.0 for value in ratios),
                "numerator_slower_samples": sum(value > 1.0 for value in ratios),
                "tied_samples": sum(value == 1.0 for value in ratios),
            },
            "delta_us": _stats(deltas_us),
        }

    compressed = ("rowwise_bm64", "fullm_n16", "fullm_n32")
    result["best_compact_by_device_median"] = min(
        compressed,
        key=lambda name: result["device_ms_per_forward"][name]["median"],
    )
    return result


if triton is not None:

    @triton.jit
    def _fullm_row_tile_no_e_kernel(
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
        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        offs_m = tl.arange(0, BLOCK_M)
        offs_k = tl.arange(0, BLOCK_K)

        mask_n = offs_n < N
        mask_m = offs_m < M
        mask_k = offs_k < K
        matrix_mask = mask_m[:, None] & mask_k[None, :]

        x = tl.load(
            x_ptr + offs_n[:, None] * K + offs_k[None, :],
            mask=mask_n[:, None] & mask_k[None, :],
            other=0.0,
        )

        # Decode the complete 64x32 Up weight tile once per BLOCK_N rows.
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

        acc = tl.dot(x, tl.trans(weight), input_precision="ieee")
        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


class _StructuralRowwiseBank(_StructuralValidationMixin, TritonCompressedLinearBank):
    """C53 winning row-wise no-E geometry used as C54 control."""

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if value.device.type != "cuda" or value.dtype != torch.float32:
            raise RuntimeError("C54 row-wise control requires CUDA float32")
        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )
        indices, corrections = self._correction(module_index)
        if int(corrections.numel()) != 0:
            raise ValueError("C54 is a no-E diagnostic")
        block_k = triton.next_power_of_2(self.input_width)
        grid = (
            int(flat.shape[0]) * triton.cdiv(self.output_width, 64),
        )
        _compressed_linear_kernel[grid](
            flat,
            self.base,
            self.codebooks,
            self.codes,
            indices,
            corrections,
            output,
            M=self.output_width,
            K=self.input_width,
            GRID_R=self.grid_rows,
            GRID_C=self.grid_cols,
            BR=self.block_rows,
            BC=self.block_cols,
            Q=self.codebook_count,
            ENTRIES=self.entries_per_codebook,
            MODULE_INDEX=module_index,
            CORR_NNZ=0,
            BLOCK_M=64,
            BLOCK_K=block_k,
            BLOCK_C=1,
            num_warps=4,
        )
        return output.reshape(*value.shape[:-1], self.output_width)


class _FullMRowTileBank(_StructuralValidationMixin, TritonCompressedLinearBank):
    def __init__(self, initialization, *, block_n: int) -> None:
        super().__init__(initialization)
        if block_n not in (16, 32):
            raise ValueError("C54 block_n must be 16 or 32")
        self.block_n = block_n
        for module_index in range(self.module_count):
            _indices, values = self._correction(module_index)
            if int(values.numel()) != 0:
                raise ValueError("C54 full-M path requires no correction E")

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime unavailable")
        if value.device.type != "cuda" or value.dtype != torch.float32:
            raise RuntimeError("C54 full-M path requires CUDA float32")
        if self.output_width != 64 or self.input_width != 32:
            raise ValueError("C54 full-M kernel is intentionally scoped to real Up 32->64")

        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )
        grid = (triton.cdiv(int(flat.shape[0]), self.block_n),)
        _fullm_row_tile_no_e_kernel[grid](
            flat,
            self.base,
            self.codebooks,
            self.codes,
            output,
            N=int(flat.shape[0]),
            M=self.output_width,
            K=self.input_width,
            GRID_R=self.grid_rows,
            GRID_C=self.grid_cols,
            BR=self.block_rows,
            BC=self.block_cols,
            Q=self.codebook_count,
            ENTRIES=self.entries_per_codebook,
            MODULE_INDEX=module_index,
            BLOCK_N=self.block_n,
            BLOCK_M=64,
            BLOCK_K=32,
            num_warps=4,
        )
        return output.reshape(*value.shape[:-1], self.output_width)


@torch.inference_mode()
def run_benchmark(
    *,
    fixture_path: Path,
    protected_result_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C54 requires CUDA")
    if not triton_runtime_available():
        raise RuntimeError("C54 requires Triton")

    protected_before = _sha256(protected_result_path)
    initializations = _load_initializations(str(fixture_path))
    no_e_up = without_correction(initializations.up)

    template = no_e_up.template
    structure = {
        "input_width": int(template.input_width),
        "output_width": int(template.output_width),
        "block_rows": int(template.block_rows),
        "block_cols": int(template.block_cols),
        "grid_rows": int(template.grid_rows),
        "grid_cols": int(template.grid_cols),
        "codebook_count": int(template.codebook_count),
        "entries_per_codebook": int(template.entries_per_codebook),
        "module_count": len(no_e_up.encoded_weights),
    }
    expected_structure = {
        "input_width": 32,
        "output_width": 64,
        "block_rows": 2,
        "block_cols": 2,
        "grid_rows": 32,
        "grid_cols": 16,
        "codebook_count": 3,
        "entries_per_codebook": 8,
        "module_count": 2,
    }
    if structure != expected_structure:
        raise RuntimeError(f"unexpected C54 Up structure: {structure}")

    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    rowwise = _StructuralRowwiseBank(no_e_up).to(device)
    fullm_n16 = _FullMRowTileBank(no_e_up, block_n=16).to(device)
    fullm_n32 = _FullMRowTileBank(no_e_up, block_n=32).to(device)
    materializer = DirectCompressedLinearBank(no_e_up)

    generator = torch.Generator(device="cpu").manual_seed(20260913)
    value = torch.randn(
        DEFAULT_ROWS,
        DEFAULT_SLOTS,
        DEFAULT_WIDTH,
        generator=generator,
        dtype=torch.float32,
    ).to(device)

    records: list[dict] = []
    max_gaps: dict[str, dict[str, float]] = {}
    total = 2 * ROUNDS * len(VARIANTS)
    completed = 0

    for module_index in (0, 1):
        dense_weight = materializer.materialized_weight(module_index).to(device)
        dense_call = lambda: F.linear(value, dense_weight, None)
        rowwise_call = lambda: rowwise(value, module_index=module_index)
        n16_call = lambda: fullm_n16(value, module_index=module_index)
        n32_call = lambda: fullm_n32(value, module_index=module_index)

        dense_out = dense_call()
        rowwise_out = rowwise_call()
        n16_out = n16_call()
        n32_out = n32_call()
        torch.cuda.synchronize()

        for name, output in (
            ("rowwise_bm64", rowwise_out),
            ("fullm_n16", n16_out),
            ("fullm_n32", n32_out),
        ):
            torch.testing.assert_close(output, dense_out, rtol=1e-4, atol=1e-5)
            max_gaps.setdefault(name, {})[str(module_index)] = float(
                (output - dense_out).abs().max().item()
            )

        calls = {
            "dense_no_e": dense_call,
            "rowwise_bm64": rowwise_call,
            "fullm_n16": n16_call,
            "fullm_n32": n32_call,
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
                records.append(
                    {
                        "module_index": module_index,
                        "round": round_index,
                        "variant": variant,
                        "device_ms_per_forward": timing,
                    }
                )
                completed += 1
            print(
                f"[C54] module={module_index} round={round_index + 1}/{ROUNDS} "
                f"checked ({completed}/{total})",
                flush=True,
            )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C54")

    summary = _summarize(records)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "real Up no-E full-M row-tile microarchitecture diagnostic",
        "shape": {
            "activation": [DEFAULT_ROWS, DEFAULT_SLOTS, DEFAULT_WIDTH],
            "flattened_rows": DEFAULT_ROWS * DEFAULT_SLOTS,
            "input_width": 32,
            "output_width": 64,
        },
        "compact_structure": structure,
        "geometry": {
            "rowwise": {"block_m": 64, "block_k": 32, "num_warps": 4},
            "fullm_n16": {"block_n": 16, "block_m": 64, "block_k": 32, "num_warps": 4},
            "fullm_n32": {"block_n": 32, "block_m": 64, "block_k": 32, "num_warps": 4},
        },
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "summary": summary,
        "max_abs_output_gaps": max_gaps,
        "fixture_sha256": _sha256(fixture_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "no-E is diagnostic and not a quality candidate",
            "bank-level Up benchmark, not full-model latency",
            "full-M variants change execution mapping only; compact representation is unchanged",
            "synthetic deterministic activation with real fixture shape",
            "C54 alone cannot establish Gate C pass",
        ],
        "records": records,
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run_benchmark(
        fixture_path=args.fixture,
        protected_result_path=args.protected_result,
        output_dir=args.output_dir,
    )
    display = {key: value for key, value in result.items() if key != "records"}
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C54 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
