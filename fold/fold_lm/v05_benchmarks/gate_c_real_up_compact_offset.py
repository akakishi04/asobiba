"""C55: real-Up compact offset/address arithmetic diagnostic.

C54 established that owning all 64 Up output channels and reusing the decoded
weight across 16 activation rows materially beats the tuned row-wise mapping.
C55 keeps that full-M/N16 execution mapping fixed and changes only the resident
uint8 code metadata:

- codes: original per-block code, with q/entry/block-base arithmetic in-kernel;
- entry_index: store q * ENTRIES + code directly, same uint8 byte count;
- block_offset: store the codebook block base element offset directly, same
  uint8 byte count.

Both transformed variants replace, rather than duplicate, the original resident
codes buffer.  This isolates whether codebook address arithmetic is a material
part of the remaining decode cost without creating dense module weights or
adding resident metadata bytes.
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
from fold_lm.v05.triton_runtime import (
    TritonCompressedLinearBank,
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
from fold_lm.v05_benchmarks.gate_c_real_up_fullm_row_tile import (
    _FullMRowTileBank,
)

EXPERIMENT_ID = "C55-real-up-compact-offset"
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
    "fullm_codes",
    "fullm_entry_index",
    "fullm_block_offset",
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
            raise ValueError("invalid or duplicate C55 timing record")
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("C55 timings must be positive and finite")
        table[key] = value

    expected = {
        (module_index, round_index, variant)
        for module_index in (0, 1)
        for round_index in range(ROUNDS)
        for variant in VARIANTS
    }
    if set(table) != expected:
        raise ValueError("incomplete C55 timing table")

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
        ("codes_over_dense", "fullm_codes", "dense_no_e"),
        ("entry_over_codes", "fullm_entry_index", "fullm_codes"),
        ("block_offset_over_codes", "fullm_block_offset", "fullm_codes"),
        ("block_offset_over_entry", "fullm_block_offset", "fullm_entry_index"),
        ("entry_over_dense", "fullm_entry_index", "dense_no_e"),
        ("block_offset_over_dense", "fullm_block_offset", "dense_no_e"),
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
                "numerator_faster_samples": sum(x < 1.0 for x in ratios),
                "numerator_slower_samples": sum(x > 1.0 for x in ratios),
                "tied_samples": sum(x == 1.0 for x in ratios),
            },
            "delta_us": _stats(deltas_us),
        }

    compact = ("fullm_codes", "fullm_entry_index", "fullm_block_offset")
    result["best_compact_by_device_median"] = min(
        compact,
        key=lambda name: result["device_ms_per_forward"][name]["median"],
    )
    return result


if triton is not None:

    @triton.jit
    def _fullm_entry_index_kernel(
        x_ptr,
        base_ptr,
        codebooks_ptr,
        entry_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
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
            metadata_offset = (
                (((MODULE_INDEX * GRID_R + row_block) * GRID_C + col_block) * Q)
                + q
            )
            entry_index = tl.load(
                entry_ptr + metadata_offset,
                mask=matrix_mask,
                other=0,
            ).to(tl.int32)
            codebook_offset = (
                ((entry_index * BR + inner_row) * BC) + inner_col
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

    @triton.jit
    def _fullm_block_offset_kernel(
        x_ptr,
        base_ptr,
        codebooks_ptr,
        block_offset_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
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
        weight = tl.load(
            base_ptr + offs_m[:, None] * K + offs_k[None, :],
            mask=matrix_mask,
            other=0.0,
        )

        row_block = offs_m[:, None] // BR
        col_block = offs_k[None, :] // BC
        inner_offset = (offs_m[:, None] % BR) * BC + (offs_k[None, :] % BC)

        for q in tl.static_range(0, Q):
            metadata_offset = (
                (((MODULE_INDEX * GRID_R + row_block) * GRID_C + col_block) * Q)
                + q
            )
            block_base = tl.load(
                block_offset_ptr + metadata_offset,
                mask=matrix_mask,
                other=0,
            ).to(tl.int32)
            weight += tl.load(
                codebooks_ptr + block_base + inner_offset,
                mask=matrix_mask,
                other=0.0,
            )

        acc = tl.dot(x, tl.trans(weight), input_precision="ieee")
        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


class _OffsetMetadataBank(_StructuralValidationMixin, TritonCompressedLinearBank):
    def __init__(self, initialization, *, mode: str) -> None:
        super().__init__(initialization)
        if mode not in ("entry_index", "block_offset"):
            raise ValueError("C55 mode must be entry_index or block_offset")
        self.mode = mode
        self._module_count = int(self.codes.shape[0])

        codes = self.codes.detach().to(dtype=torch.int16)
        q = torch.arange(
            self.codebook_count,
            dtype=torch.int16,
            device=codes.device,
        ).reshape(1, 1, 1, self.codebook_count)
        entry_index = q * self.entries_per_codebook + codes

        if int(entry_index.max().item()) > 255:
            raise ValueError("C55 entry index does not fit uint8")

        if mode == "entry_index":
            metadata = entry_index.to(dtype=torch.uint8)
            metadata_name = "entry_indices"
        else:
            metadata = entry_index * (self.block_rows * self.block_cols)
            if int(metadata.max().item()) > 255:
                raise ValueError("C55 block offset does not fit uint8")
            metadata = metadata.to(dtype=torch.uint8)
            metadata_name = "codebook_block_offsets"

        delattr(self, "codes")
        self.register_buffer(metadata_name, metadata)

        for module_index in range(self.module_count):
            _indices, values = self._correction(module_index)
            if int(values.numel()) != 0:
                raise ValueError("C55 transformed metadata path requires no E")

    @property
    def module_count(self) -> int:
        return self._module_count

    @property
    def metadata_bytes(self) -> int:
        buffer = (
            self.entry_indices
            if self.mode == "entry_index"
            else self.codebook_block_offsets
        )
        return int(buffer.numel() * buffer.element_size())

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton unavailable")
        if value.device.type != "cuda" or value.dtype != torch.float32:
            raise RuntimeError("C55 requires CUDA float32")
        if self.output_width != 64 or self.input_width != 32:
            raise ValueError("C55 is scoped to real Up 32->64")

        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )
        grid = (triton.cdiv(int(flat.shape[0]), 16),)

        if self.mode == "entry_index":
            _fullm_entry_index_kernel[grid](
                flat,
                self.base,
                self.codebooks,
                self.entry_indices,
                output,
                N=int(flat.shape[0]),
                M=self.output_width,
                K=self.input_width,
                GRID_R=self.grid_rows,
                GRID_C=self.grid_cols,
                BR=self.block_rows,
                BC=self.block_cols,
                Q=self.codebook_count,
                MODULE_INDEX=module_index,
                BLOCK_N=16,
                BLOCK_M=64,
                BLOCK_K=32,
                num_warps=4,
            )
        else:
            _fullm_block_offset_kernel[grid](
                flat,
                self.base,
                self.codebooks,
                self.codebook_block_offsets,
                output,
                N=int(flat.shape[0]),
                M=self.output_width,
                K=self.input_width,
                GRID_R=self.grid_rows,
                GRID_C=self.grid_cols,
                BR=self.block_rows,
                BC=self.block_cols,
                Q=self.codebook_count,
                MODULE_INDEX=module_index,
                BLOCK_N=16,
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
    c54_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available() or not triton_runtime_available():
        raise RuntimeError("C55 requires CUDA + Triton")

    c54 = json.loads(c54_summary_path.read_text(encoding="utf-8"))
    if (
        c54.get("experiment_id") != "C54-real-up-fullm-row-tile"
        or c54.get("status") != "PASS"
    ):
        raise RuntimeError("C55 requires accepted C54 summary")

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
    expected = {
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
    if structure != expected:
        raise RuntimeError(f"unexpected C55 Up structure: {structure}")

    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    device = torch.device("cuda")

    codes_bank = _FullMRowTileBank(no_e_up, block_n=16).to(device)
    entry_bank = _OffsetMetadataBank(no_e_up, mode="entry_index").to(device)
    offset_bank = _OffsetMetadataBank(no_e_up, mode="block_offset").to(device)
    materializer = DirectCompressedLinearBank(no_e_up)

    codes_bytes = int(codes_bank.codes.numel() * codes_bank.codes.element_size())
    if entry_bank.metadata_bytes != codes_bytes or offset_bank.metadata_bytes != codes_bytes:
        raise RuntimeError("C55 transformed metadata changed resident code byte count")

    generator = torch.Generator(device="cpu").manual_seed(20260913)
    value = torch.randn(
        DEFAULT_ROWS,
        DEFAULT_SLOTS,
        DEFAULT_WIDTH,
        generator=generator,
        dtype=torch.float32,
    ).to(device)

    records: list[dict] = []
    gaps: dict[str, dict[str, float]] = {}
    total = 2 * ROUNDS * len(VARIANTS)
    completed = 0

    for module_index in (0, 1):
        dense_weight = materializer.materialized_weight(module_index).to(device)
        dense_call = lambda: F.linear(value, dense_weight, None)
        codes_call = lambda: codes_bank(value, module_index=module_index)
        entry_call = lambda: entry_bank(value, module_index=module_index)
        offset_call = lambda: offset_bank(value, module_index=module_index)

        dense_out = dense_call()
        codes_out = codes_call()
        entry_out = entry_call()
        offset_out = offset_call()
        torch.cuda.synchronize()

        for name, output in (
            ("fullm_codes", codes_out),
            ("fullm_entry_index", entry_out),
            ("fullm_block_offset", offset_out),
        ):
            torch.testing.assert_close(output, dense_out, rtol=1e-4, atol=1e-5)
            gaps.setdefault(name, {})[str(module_index)] = float(
                (output - dense_out).abs().max().item()
            )

        calls = {
            "dense_no_e": dense_call,
            "fullm_codes": codes_call,
            "fullm_entry_index": entry_call,
            "fullm_block_offset": offset_call,
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
                f"[C55] module={module_index} round={round_index + 1}/{ROUNDS} "
                f"checked ({completed}/{total})",
                flush=True,
            )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C55")

    summary = _summarize(records)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "real Up full-M/N16 compact address metadata diagnostic",
        "shape": {
            "activation": [DEFAULT_ROWS, DEFAULT_SLOTS, DEFAULT_WIDTH],
            "flattened_rows": DEFAULT_ROWS * DEFAULT_SLOTS,
            "input_width": 32,
            "output_width": 64,
        },
        "compact_structure": structure,
        "geometry": {
            "block_n": 16,
            "block_m": 64,
            "block_k": 32,
            "num_warps": 4,
        },
        "resident_metadata": {
            "original_codes_bytes": codes_bytes,
            "entry_index_bytes": entry_bank.metadata_bytes,
            "block_offset_bytes": offset_bank.metadata_bytes,
            "transformed_variants_replace_original_codes": True,
        },
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "summary": summary,
        "max_abs_output_gaps": gaps,
        "fixture_sha256": _sha256(fixture_path),
        "C54_summary_sha256": _sha256(c54_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "no-E is diagnostic and not a quality candidate",
            "bank-level Up benchmark, not full-model latency",
            "full-M/N16 mapping is fixed from C54",
            "metadata transformations replace uint8 codes with equal-byte uint8 metadata",
            "C55 alone cannot establish Gate C pass",
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
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c54-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run_benchmark(
        fixture_path=args.fixture,
        protected_result_path=args.protected_result,
        c54_summary_path=args.c54_summary,
        output_dir=args.output_dir,
    )
    display = {key: value for key, value in result.items() if key != "records"}
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C55 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
