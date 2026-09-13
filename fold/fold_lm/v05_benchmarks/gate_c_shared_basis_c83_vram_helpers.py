"""Helpers for C83 fresh-process operational VRAM/headroom measurement."""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    _allocate_shared,
)

WIDTH = 5120
SLOTS = 20
MODULES = 2
HIDDEN_MULT = 2
PROFILES = {
    "lean": (1, 16),
    "medium": (1, 8),
    "rank3_bridge": (3, 16),
}
BATCHES = (1, 8)
WARMUP = 4
MEASURE_ITERS = 8
GIB = 1024 ** 3


def _rank(profile: str) -> int:
    num, den = PROFILES[profile]
    value = WIDTH * num
    if value % den:
        raise RuntimeError("C83 non-integral rank")
    return value // den


def _cuda_stats() -> dict[str, int]:
    free, total = torch.cuda.mem_get_info()
    return {
        "allocated_bytes": int(torch.cuda.memory_allocated()),
        "reserved_bytes": int(torch.cuda.memory_reserved()),
        "free_bytes": int(free),
        "total_bytes": int(total),
    }


def _build_model(variant: str, profile: str, device: torch.device):
    config = LearnedCoreConfig(
        width=WIDTH,
        slots=SLOTS,
        modules=MODULES,
        hidden_mult=HIDDEN_MULT,
    )
    if variant == "dense":
        with torch.device(device):
            return HighPrecisionFixedRoutingCore(config)
    if variant == "shared":
        return _allocate_shared(config, _rank(profile), device)
    raise ValueError(f"unknown C83 variant: {variant}")


def run_child(*, variant: str, profile: str, batch: int, output_path: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C83 requires CUDA")
    if variant not in ("dense", "shared"):
        raise ValueError("variant must be dense/shared")
    if profile not in PROFILES:
        raise ValueError("unknown profile")
    if batch not in BATCHES:
        raise ValueError("unsupported batch")

    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    torch.cuda.init()
    torch.cuda.synchronize()
    gc.collect()
    torch.cuda.empty_cache()
    baseline = _cuda_stats()

    model = _build_model(variant, profile, device).eval()
    torch.cuda.synchronize()
    resident = _cuda_stats()

    working = torch.zeros(batch, SLOTS, WIDTH, device=device)
    context = torch.full_like(working, 0.01)
    with torch.inference_mode():
        for step in range(WARMUP):
            model(working, context, route_index=step % MODULES)
    torch.cuda.synchronize()
    ready = _cuda_stats()

    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        for step in range(MEASURE_ITERS):
            output = model(working, context, route_index=step % MODULES)
    torch.cuda.synchronize()
    after = _cuda_stats()
    peak_allocated = int(torch.cuda.max_memory_allocated())
    peak_reserved = int(torch.cuda.max_memory_reserved())
    output_finite = bool(torch.isfinite(output).all().item())

    record = {
        "variant": variant,
        "profile": profile,
        "rank": None if variant == "dense" else _rank(profile),
        "batch": batch,
        "baseline": baseline,
        "resident": resident,
        "ready": ready,
        "after": after,
        "resident_allocated_delta_bytes": resident["allocated_bytes"] - baseline["allocated_bytes"],
        "resident_reserved_delta_bytes": resident["reserved_bytes"] - baseline["reserved_bytes"],
        "ready_device_vram_consumed_bytes": baseline["free_bytes"] - ready["free_bytes"],
        "ready_device_free_bytes": ready["free_bytes"],
        "peak_allocated_bytes": peak_allocated,
        "peak_reserved_bytes": peak_reserved,
        "peak_allocated_delta_from_baseline_bytes": peak_allocated - baseline["allocated_bytes"],
        "peak_reserved_delta_from_baseline_bytes": peak_reserved - baseline["reserved_bytes"],
        "output_finite": output_finite,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("dense", "shared"), required=True)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--batch", type=int, choices=BATCHES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_child(
        variant=args.variant,
        profile=args.profile,
        batch=args.batch,
        output_path=args.output,
    )
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
