"""C24: isolate sparse correction E cost inside the fused Triton Linear kernel.

C23 established a more robust full-model runtime baseline using CUDA Events and
paired same-round ratios.  The remaining question is whether the Triton kernel
spends most of its excess time scanning sparse correction E, or decoding the
shared codebook representation itself.

This benchmark is diagnostic only.  It compares, for the same routed Linear
shape/input:

- dense: the original high-precision Linear;
- triton_full: the real fused compressed kernel;
- triton_no_e: the same compressed representation with correction E removed.

The no-E path intentionally changes numerical output and is never treated as a
quality candidate.  It exists only to measure how much runtime the correction
branch contributes.  CUDA Events, repeated forwards, round-order rotation and
paired medians are used to reduce WDDM/clock noise.
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

from fold_lm.v05.compression_init import CompressionInitialization
from fold_lm.v05.compression_v5c import EncodedBlockWeight
from fold_lm.v05.compression_serialization import deserialize_module_initializations
from fold_lm.v05.triton_runtime import TritonCompressedLinearBank
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture

ROLES = ("up", "down")
VARIANTS = ("dense", "triton_full", "triton_no_e")


def order_for_round(round_index: int) -> tuple[str, ...]:
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    offset = round_index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


def _load_initializations(fixture_path: str):
    payload = torch.load(fixture_path, map_location="cpu", weights_only=True)
    blob_tensor = payload.get("compressed_blob")
    if not isinstance(blob_tensor, torch.Tensor) or blob_tensor.dtype != torch.uint8:
        raise ValueError("fixture compressed blob is invalid")
    return deserialize_module_initializations(blob_tensor.contiguous().numpy().tobytes())


def without_correction(initialization: CompressionInitialization) -> CompressionInitialization:
    if not isinstance(initialization, CompressionInitialization):
        raise TypeError("initialization must be CompressionInitialization")
    encoded = tuple(
        EncodedBlockWeight(
            template=initialization.template,
            codes=np.array(weight.codes, copy=True),
            correction_indices=None,
            correction_values=None,
            max_correction_entries=0,
            max_abs_correction=0.0,
        )
        for weight in initialization.encoded_weights
    )
    # Metrics/accounting belong to the real candidate and are deliberately kept
    # only as inert metadata.  C24 never reports no-E as a storage/quality candidate.
    return CompressionInitialization(
        template=initialization.template,
        encoded_weights=encoded,
        metrics=initialization.metrics,
        accounting=initialization.accounting,
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
    roles = {}
    for role in ROLES:
        rows = [row for row in records if row.get("role") == role]
        if not rows:
            continue
        keys = {(int(row["round"]), int(row["module_index"])) for row in rows}
        by_key = {key: {} for key in keys}
        for row in rows:
            variant = row.get("variant")
            if variant not in VARIANTS:
                raise ValueError("unknown variant")
            key = (int(row["round"]), int(row["module_index"]))
            if variant in by_key[key]:
                raise ValueError("duplicate variant for module/round")
            by_key[key][variant] = row
        if any(set(group) != set(VARIANTS) for group in by_key.values()):
            raise ValueError("each module/round must contain all variants")

        medians = {
            variant: _median([
                float(row["device_per_forward_ms"])
                for row in rows
                if row["variant"] == variant
            ])
            for variant in VARIANTS
        }
        full_vs_dense = []
        no_e_vs_dense = []
        full_to_no_e = []
        for group in by_key.values():
            dense = float(group["dense"]["device_per_forward_ms"])
            full = float(group["triton_full"]["device_per_forward_ms"])
            no_e = float(group["triton_no_e"]["device_per_forward_ms"])
            full_vs_dense.append(full / dense)
            no_e_vs_dense.append(no_e / dense)
            full_to_no_e.append(full / no_e)

        roles[role] = {
            "samples_per_variant": len([row for row in rows if row["variant"] == "dense"]),
            "dense_device_median_ms": medians["dense"],
            "triton_full_device_median_ms": medians["triton_full"],
            "triton_no_e_device_median_ms": medians["triton_no_e"],
            "triton_full_vs_dense_paired_median": _median(full_vs_dense),
            "triton_no_e_vs_dense_paired_median": _median(no_e_vs_dense),
            "full_to_no_e_slowdown_paired_median": _median(full_to_no_e),
        }
    if not roles:
        raise ValueError("records contain no recognized roles")
    return {"roles": roles}


def run_benchmark(
    fixture_path: str,
    *,
    device: str | torch.device = "cuda",
    warmup: int = 20,
    rounds: int = 9,
    iterations: int = 200,
) -> dict:
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C24 correction ablation requires CUDA")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    if type(rounds) is not int or rounds <= 0:
        raise ValueError("rounds must be positive")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be positive")

    started = time.perf_counter()
    fixture = load_runtime_fixture(fixture_path, device=device)
    dense_core = fixture["models"]["dense"].core
    initializations = _load_initializations(fixture_path)
    full = {"up": initializations.up, "down": initializations.down}
    no_e = {role: without_correction(init) for role, init in full.items()}
    full_banks = {role: TritonCompressedLinearBank(init).to(device) for role, init in full.items()}
    no_e_banks = {role: TritonCompressedLinearBank(init).to(device) for role, init in no_e.items()}

    generator = torch.Generator(device="cpu").manual_seed(20260912)
    records: list[dict] = []
    output_gap_by_role: dict[str, float] = {}
    correction_nnz_by_role = {
        role: sum(weight.correction_nnz for weight in init.encoded_weights)
        for role, init in full.items()
    }
    total = int(dense_core.config.modules) * len(ROLES) * rounds * len(VARIANTS)
    completed = 0

    for role in ROLES:
        max_gap = 0.0
        for module_index in range(int(dense_core.config.modules)):
            dense_linear = getattr(dense_core.module_set[module_index], role)
            bank = full_banks[role]
            value = torch.randn(
                int(fixture["validation"].size),
                int(dense_core.config.slots),
                int(bank.input_width),
                generator=generator,
                dtype=dense_linear.weight.dtype,
            ).to(device)

            # Trigger both Triton specializations and record the numerical effect
            # of removing E.  This delta is diagnostic, not a correctness target.
            full_output = full_banks[role](value, module_index=module_index)
            no_e_output = no_e_banks[role](value, module_index=module_index)
            torch.cuda.synchronize()
            max_gap = max(max_gap, float((full_output - no_e_output).abs().max().item()))

            callables = {
                "dense": lambda v=value, linear=dense_linear: F.linear(v, linear.weight, None),
                "triton_full": lambda v=value, b=full_banks[role], mi=module_index: b(v, module_index=mi),
                "triton_no_e": lambda v=value, b=no_e_banks[role], mi=module_index: b(v, module_index=mi),
            }
            with torch.inference_mode():
                for variant in VARIANTS:
                    for _ in range(warmup):
                        callables[variant]()
            torch.cuda.synchronize()

            for round_index in range(rounds):
                order = order_for_round(round_index)
                for variant in order:
                    per_forward_ms = _measure_batch(callables[variant], iterations=iterations)
                    records.append({
                        "role": role,
                        "module_index": module_index,
                        "round": round_index,
                        "variant": variant,
                        "device_per_forward_ms": per_forward_ms,
                    })
                    completed += 1
                    print(
                        f"[gate-c-triton-e-ablation] {completed}/{total} "
                        f"role={role} module={module_index} round={round_index + 1}/{rounds} "
                        f"variant={variant} device={per_forward_ms * 1000.0:.1f}us",
                        file=sys.stderr,
                        flush=True,
                    )
        output_gap_by_role[role] = max_gap

    return {
        "schema": "fold-v05-gate-c-triton-correction-ablation-v1",
        "fixture_path": fixture_path,
        "task": fixture["task"],
        "seed": fixture["seed"],
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "warmup": warmup,
        "rounds": rounds,
        "iterations_per_sample": iterations,
        "correction_nnz_total_by_role": correction_nnz_by_role,
        "max_abs_full_vs_no_e_output_gap_by_role": output_gap_by_role,
        "summary": summarize_records(records),
        "elapsed_seconds": time.perf_counter() - started,
        "retrained": False,
        "diagnostic_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        args.fixture,
        device=args.device,
        warmup=args.warmup,
        rounds=args.rounds,
        iterations=args.iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
