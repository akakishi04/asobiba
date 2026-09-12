"""C19: isolate dense vs compact routed Linear runtime from a C16 fixture."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture

ROLES = ("up", "down")
KINDS = ("dense", "compact", "base_only")


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def measure(callable_, *, warmup: int, repeats: int, device: torch.device) -> dict:
    if not callable(callable_):
        raise TypeError("callable_ must be callable")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(repeats) is not int or repeats <= 0:
        raise ValueError("repeats must be positive")
    with torch.inference_mode():
        for _ in range(warmup):
            callable_()
        _sync(device)
        samples = []
        for _ in range(repeats):
            _sync(device)
            started = time.perf_counter()
            callable_()
            _sync(device)
            samples.append(time.perf_counter() - started)
    ordered = sorted(samples)
    p90 = ordered[max(0, min(len(ordered) - 1, math.ceil(0.9 * len(ordered)) - 1))]
    return {
        "mean_seconds": sum(samples) / len(samples),
        "median_seconds": statistics.median(samples),
        "p90_seconds": p90,
        "repeats": repeats,
    }


def bank_structure(bank) -> dict:
    correction_nnz = sum(
        int(getattr(bank, f"correction_values_{i}").numel())
        for i in range(bank.module_count)
    )
    return {
        "module_count": int(bank.module_count),
        "input_width": int(bank.input_width),
        "output_width": int(bank.output_width),
        "grid_rows": int(bank.grid_rows),
        "grid_cols": int(bank.grid_cols),
        "block_rows": int(bank.block_rows),
        "block_cols": int(bank.block_cols),
        "codebook_count": int(bank.codebook_count),
        "entries_per_codebook": int(bank.entries_per_codebook),
        "codes_per_module": int(bank.grid_rows * bank.grid_cols * bank.codebook_count),
        "correction_nnz_total": correction_nnz,
        "resident_tensor_bytes": int(bank.resident_tensor_bytes),
    }


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    roles = {}
    for role in ROLES:
        rows = [row for row in records if row["role"] == role]
        if not rows:
            continue
        means = {
            kind: sum(float(row["timings"][kind]["mean_seconds"]) for row in rows) / len(rows)
            for kind in KINDS
        }
        roles[role] = {
            "modules": len(rows),
            "dense_mean_us": means["dense"] * 1e6,
            "compact_mean_us": means["compact"] * 1e6,
            "base_only_mean_us": means["base_only"] * 1e6,
            "compact_ratio_vs_dense": means["compact"] / means["dense"],
            "compact_ratio_vs_base_only": means["compact"] / means["base_only"],
        }
    return {"roles": roles}


def run_profile(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    warmup: int = 20,
    repeats: int = 200,
) -> dict:
    device = torch.device(device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    fixture = load_runtime_fixture(fixture_path, device=device)
    dense_core = fixture["models"]["dense"].core
    compact_core = fixture["models"]["compact"].core
    batch = int(fixture["validation"].size)
    slots = int(dense_core.config.slots)
    generator = torch.Generator(device="cpu").manual_seed(20260912)
    records = []
    for module_index in range(int(dense_core.config.modules)):
        for role in ROLES:
            dense_linear = getattr(dense_core.module_set[module_index], role)
            bank = compact_core.up_bank if role == "up" else compact_core.down_bank
            value = torch.randn(
                batch, slots, int(bank.input_width), generator=generator,
                dtype=dense_linear.weight.dtype,
            ).to(device)
            base = bank.base.to(device=device, dtype=value.dtype)
            timings = {
                "dense": measure(lambda: F.linear(value, dense_linear.weight, None), warmup=warmup, repeats=repeats, device=device),
                "compact": measure(lambda: bank(value, module_index=module_index), warmup=warmup, repeats=repeats, device=device),
                "base_only": measure(lambda: F.linear(value, base, None), warmup=warmup, repeats=repeats, device=device),
            }
            records.append({"module_index": module_index, "role": role, "input_shape": list(value.shape), "timings": timings})
    return {
        "schema": "fold-v05-gate-c-compact-linear-profile-v1",
        "task": fixture["task"],
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": "cpu" if device.type == "cpu" else torch.cuda.get_device_name(device),
        "validation_batch": batch,
        "slots": slots,
        "structures": {"up": bank_structure(compact_core.up_bank), "down": bank_structure(compact_core.down_bank)},
        "records": records,
        "summary": summarize(records),
        "retrained": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    print(json.dumps(run_profile(args.fixture, device=args.device, warmup=args.warmup, repeats=args.repeats), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
