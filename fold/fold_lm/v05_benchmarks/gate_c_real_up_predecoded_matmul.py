"""C56: isolate codebook gather/decode from the full-M/N16 matmul.

C54 showed full-M/N16 row reuse helps. C55 showed equal-byte precomputed address
metadata helps little. C56 compares the compact full-M/N16 path with the same
Triton row-tile matmul fed an already-materialized no-E weight. The materialized
weight is diagnostic only and is not a Gate-C candidate.
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
from fold_lm.v05.triton_runtime import triton_runtime_available, triton, tl
from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import _load_initializations
from fold_lm.v05_benchmarks.gate_c_real_up_fullm_row_tile import _FullMRowTileBank

EXPERIMENT_ID = "C56-real-up-predecoded-matmul-isolation"
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
ROUNDS = 40
ITERATIONS = 500
WARMUP = 100
VARIANTS = ("dense", "predecoded_triton", "compact_fullm_n16")


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def stats(xs):
    return {
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "min": min(xs),
        "max": max(xs),
    }


def measure(fn) -> float:
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
    def predecoded_kernel(
        x_ptr,
        w_ptr,
        out_ptr,
        N: tl.constexpr,
        BLOCK_N: tl.constexpr,
    ):
        offs_n = tl.program_id(0) * BLOCK_N + tl.arange(0, BLOCK_N)
        offs_m = tl.arange(0, 64)
        offs_k = tl.arange(0, 32)
        mask_n = offs_n < N
        x = tl.load(
            x_ptr + offs_n[:, None] * 32 + offs_k[None, :],
            mask=mask_n[:, None],
            other=0.0,
        )
        w = tl.load(w_ptr + offs_m[:, None] * 32 + offs_k[None, :])
        acc = tl.dot(x, tl.trans(w), input_precision="ieee")
        tl.store(
            out_ptr + offs_n[:, None] * 64 + offs_m[None, :],
            acc,
            mask=mask_n[:, None],
        )


def predecoded_forward(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    flat = value.reshape(-1, 32).contiguous()
    out = torch.empty((flat.shape[0], 64), device=value.device, dtype=value.dtype)
    predecoded_kernel[(triton.cdiv(int(flat.shape[0]), 16),)](
        flat,
        weight,
        out,
        N=int(flat.shape[0]),
        BLOCK_N=16,
        num_warps=4,
    )
    return out.reshape(*value.shape[:-1], 64)


def summarize(records):
    table = {}
    for row in records:
        key = (row["module_index"], row["round"], row["variant"])
        value = float(row["device_ms_per_forward"])
        if key in table or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid C56 timing record")
        table[key] = value

    result = {
        "device_ms_per_forward": {
            v: stats([
                table[m, r, v]
                for m in (0, 1)
                for r in range(ROUNDS)
            ])
            for v in VARIANTS
        },
        "paired_comparisons": {},
    }

    for label, a_name, b_name in (
        ("predecoded_over_dense", "predecoded_triton", "dense"),
        ("compact_over_predecoded", "compact_fullm_n16", "predecoded_triton"),
        ("compact_over_dense", "compact_fullm_n16", "dense"),
    ):
        ratios = []
        deltas = []
        for m in (0, 1):
            for r in range(ROUNDS):
                a = table[m, r, a_name]
                b = table[m, r, b_name]
                ratios.append(a / b)
                deltas.append((a - b) * 1000.0)
        result["paired_comparisons"][label] = {
            "ratio": {
                **stats(ratios),
                "numerator_faster_samples": sum(x < 1.0 for x in ratios),
                "numerator_slower_samples": sum(x > 1.0 for x in ratios),
                "tied_samples": sum(x == 1.0 for x in ratios),
            },
            "delta_us": stats(deltas),
        }
    return result


@torch.inference_mode()
def run(*, fixture: Path, protected: Path, c55_summary: Path, output_dir: Path):
    if not torch.cuda.is_available() or not triton_runtime_available():
        raise RuntimeError("C56 requires CUDA + Triton")

    c55 = json.loads(c55_summary.read_text(encoding="utf-8"))
    if c55.get("experiment_id") != "C55-real-up-compact-offset" or c55.get("status") != "PASS":
        raise RuntimeError("C56 requires accepted C55 summary")

    before = sha256(protected)
    init = _load_initializations(str(fixture))
    no_e = without_correction(init.up)
    t = no_e.template
    if (
        int(t.input_width), int(t.output_width), int(t.block_rows), int(t.block_cols),
        int(t.codebook_count), int(t.entries_per_codebook), len(no_e.encoded_weights)
    ) != (32, 64, 2, 2, 3, 8, 2):
        raise RuntimeError("unexpected C56 Up structure")

    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    compact = _FullMRowTileBank(no_e, block_n=16).to(device)
    materializer = DirectCompressedLinearBank(no_e)
    gen = torch.Generator(device="cpu").manual_seed(20260913)
    value = torch.randn(216, 8, 32, generator=gen, dtype=torch.float32).to(device)

    records = []
    gaps = {}
    total = 2 * ROUNDS * len(VARIANTS)
    done = 0

    for module_index in (0, 1):
        weight = materializer.materialized_weight(module_index).to(device)
        calls = {
            "dense": lambda: F.linear(value, weight, None),
            "predecoded_triton": lambda: predecoded_forward(value, weight),
            "compact_fullm_n16": lambda: compact(value, module_index=module_index),
        }
        dense_out = calls["dense"]()
        for name in ("predecoded_triton", "compact_fullm_n16"):
            out = calls[name]()
            torch.cuda.synchronize()
            torch.testing.assert_close(out, dense_out, rtol=1e-4, atol=1e-5)
            gaps.setdefault(name, {})[str(module_index)] = float((out - dense_out).abs().max().item())

        for name in VARIANTS:
            for _ in range(WARMUP):
                calls[name]()
        torch.cuda.synchronize()

        for round_index in range(ROUNDS):
            offset = round_index % len(VARIANTS)
            order = VARIANTS[offset:] + VARIANTS[:offset]
            for name in order:
                records.append({
                    "module_index": module_index,
                    "round": round_index,
                    "variant": name,
                    "device_ms_per_forward": measure(calls[name]),
                })
                done += 1
            print(f"[C56] module={module_index} round={round_index + 1}/{ROUNDS} checked ({done}/{total})", flush=True)

    after = sha256(protected)
    if after != before:
        raise RuntimeError("protected C37 result changed during C56")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "real Up full-M/N16 predecoded-weight matmul isolation diagnostic",
        "shape": {"activation": [216, 8, 32], "flattened_rows": 1728, "input_width": 32, "output_width": 64},
        "geometry": {"block_n": 16, "block_m": 64, "block_k": 32, "num_warps": 4},
        "diagnostic_dense_weight_bytes_per_module": 8192,
        "summary": summarize(records),
        "max_abs_output_gaps": gaps,
        "fixture_sha256": sha256(fixture),
        "C55_summary_sha256": sha256(c55_summary),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "predecoded dense weight is diagnostic only",
            "no-E is diagnostic and not a quality candidate",
            "bank-level Up benchmark only",
            "C56 does not establish Gate C pass",
        ],
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    p.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    p.add_argument("--c55-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(argv)
    started = time.perf_counter()
    result = run(fixture=a.fixture, protected=a.protected_result, c55_summary=a.c55_summary, output_dir=a.output_dir)
    display = {k: v for k, v in result.items() if k != "records"}
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C56 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
