"""C20: compare dense, compact PyTorch, and fused Triton routed Linear runtime."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.compression_serialization import deserialize_module_initializations
from fold_lm.v05.triton_runtime import TritonCompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture

ROLES = ("up", "down")
KINDS = ("dense", "compact", "triton", "base_only")


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
        samples: list[float] = []
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


def _load_compressed_initializations(fixture_path: str):
    payload = torch.load(fixture_path, map_location="cpu", weights_only=True)
    blob_tensor = payload.get("compressed_blob")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8:
        raise ValueError("fixture compressed blob is invalid")
    return deserialize_module_initializations(blob_tensor.contiguous().numpy().tobytes())


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
            "triton_mean_us": means["triton"] * 1e6,
            "base_only_mean_us": means["base_only"] * 1e6,
            "compact_ratio_vs_dense": means["compact"] / means["dense"],
            "triton_ratio_vs_dense": means["triton"] / means["dense"],
            "compact_to_triton_speedup": means["compact"] / means["triton"],
            "triton_ratio_vs_base_only": means["triton"] / means["base_only"],
            "max_abs_triton_compact_output_gap": max(
                float(row["max_abs_triton_compact_output_gap"]) for row in rows
            ),
            "max_triton_first_call_seconds": max(
                float(row["triton_first_call_seconds"]) for row in rows
            ),
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
    if device.type != "cuda":
        raise RuntimeError("C20 fused Triton profile requires CUDA")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")

    started = time.perf_counter()
    fixture = load_runtime_fixture(fixture_path, device=device)
    initializations = _load_compressed_initializations(fixture_path)
    dense_core = fixture["models"]["dense"].core
    compact_core = fixture["models"]["compact"].core
    triton_up = TritonCompressedLinearBank(initializations.up).to(device)
    triton_down = TritonCompressedLinearBank(initializations.down).to(device)
    batch = int(fixture["validation"].size)
    slots = int(dense_core.config.slots)
    generator = torch.Generator(device="cpu").manual_seed(20260912)
    records = []
    total = int(dense_core.config.modules) * len(ROLES)
    completed = 0

    for module_index in range(int(dense_core.config.modules)):
        for role in ROLES:
            dense_linear = getattr(dense_core.module_set[module_index], role)
            compact_bank = compact_core.up_bank if role == "up" else compact_core.down_bank
            triton_bank = triton_up if role == "up" else triton_down
            value = torch.randn(
                batch,
                slots,
                int(compact_bank.input_width),
                generator=generator,
                dtype=dense_linear.weight.dtype,
            ).to(device)
            base = compact_bank.base.to(device=device, dtype=value.dtype)

            _sync(device)
            first_started = time.perf_counter()
            triton_output = triton_bank(value, module_index=module_index)
            _sync(device)
            triton_first_call_seconds = time.perf_counter() - first_started
            compact_output = compact_bank(value, module_index=module_index)
            gap = float((triton_output - compact_output).abs().max().item())
            torch.testing.assert_close(
                triton_output,
                compact_output,
                rtol=1e-4,
                atol=1e-5,
            )

            timings = {
                "dense": measure(
                    lambda: F.linear(value, dense_linear.weight, None),
                    warmup=warmup,
                    repeats=repeats,
                    device=device,
                ),
                "compact": measure(
                    lambda: compact_bank(value, module_index=module_index),
                    warmup=warmup,
                    repeats=repeats,
                    device=device,
                ),
                "triton": measure(
                    lambda: triton_bank(value, module_index=module_index),
                    warmup=warmup,
                    repeats=repeats,
                    device=device,
                ),
                "base_only": measure(
                    lambda: F.linear(value, base, None),
                    warmup=warmup,
                    repeats=repeats,
                    device=device,
                ),
            }
            records.append(
                {
                    "module_index": module_index,
                    "role": role,
                    "input_shape": list(value.shape),
                    "timings": timings,
                    "triton_first_call_seconds": triton_first_call_seconds,
                    "max_abs_triton_compact_output_gap": gap,
                }
            )
            completed += 1
            elapsed = time.perf_counter() - started
            print(
                f"[gate-c-triton-linear] {completed}/{total} "
                f"role={role} module={module_index} "
                f"elapsed={elapsed:.2f}s "
                f"dense={timings['dense']['mean_seconds'] * 1e6:.1f}us "
                f"compact={timings['compact']['mean_seconds'] * 1e6:.1f}us "
                f"triton={timings['triton']['mean_seconds'] * 1e6:.1f}us",
                file=sys.stderr,
                flush=True,
            )

    return {
        "schema": "fold-v05-gate-c-triton-linear-profile-v1",
        "task": fixture["task"],
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "validation_batch": batch,
        "slots": slots,
        "records": records,
        "summary": summarize(records),
        "elapsed_seconds": time.perf_counter() - started,
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
    result = run_profile(
        args.fixture,
        device=args.device,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
