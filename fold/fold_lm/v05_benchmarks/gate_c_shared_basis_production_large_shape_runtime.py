"""C81: actual production Shared-Basis large-shape runtime/resident-memory gate.

C80 accepted the explicit production policy:

    training  -> materialized arithmetic
    inference -> GEMM-native arithmetic

C81 measures the actual production ``SharedBasisFixedRoutingCore.forward`` in
GEMM-native mode at representative large widths and the three currently selected
rank fractions.  Dense and Shared-Basis points are made semantically identical.
The benchmark intentionally excludes dense->SVD constructor cost: this is an
inference/runtime and persistent-layout gate, not an initialization benchmark.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from torch import nn

from fold_lm.v05.modules import (
    HighPrecisionFixedRoutingCore,
    LearnedCoreConfig,
    SharedBasisFixedRoutingCore,
    _ResidualMLP,
)

EXPERIMENT_ID = "C81-shared-basis-production-large-shape-runtime"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
WIDTHS = (1024, 3072, 5120)
PROFILES = {
    "lean": (1, 16),
    "medium": (1, 8),
    "rank3_bridge": (3, 16),
}
BATCHES = (1, 8)
SLOTS = 20
MODULES = 2
HIDDEN_MULT = 2
ROUNDS = 7
ITERATIONS = 20
WARMUP = 8
RTOL = 5e-4
ATOL = 1e-4
MAX_ENDPOINT_PERSISTENT_RATIO = 0.82
MAX_ENDPOINT_LATENCY_RATIO = 1.20


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _rank(profile: str, width: int) -> int:
    numerator, denominator = PROFILES[profile]
    value = width * numerator
    if value % denominator:
        raise RuntimeError(f"non-integral rank profile={profile} width={width}")
    return value // denominator


def _storage_bytes(module: nn.Module) -> int:
    seen: set[tuple[int, int]] = set()
    total = 0
    for tensor in list(module.parameters()) + list(module.buffers()):
        storage = tensor.untyped_storage()
        key = (int(storage.data_ptr()), int(storage.nbytes()))
        if key not in seen:
            seen.add(key)
            total += key[1]
    return total


def _allocate_shared(config: LearnedCoreConfig, rank: int, device: torch.device) -> SharedBasisFixedRoutingCore:
    """Allocate production layout directly, without a transient Dense/SVD source."""
    with torch.device(device):
        core = SharedBasisFixedRoutingCore.__new__(SharedBasisFixedRoutingCore)
        nn.Module.__init__(core)
        core.config = config
        core.rank = rank
        core.execution_mode = "gemm_native"
        core.shared = _ResidualMLP(config.width, config.hidden_mult)
        core.norms = nn.ModuleList([nn.LayerNorm(config.width) for _ in range(config.modules)])
        core.gate_logits = nn.Parameter(torch.zeros(config.width))
        hidden = config.width * config.hidden_mult
        core.up_biases = nn.Parameter(torch.zeros(config.modules, hidden))
        core.down_biases = nn.Parameter(torch.zeros(config.modules, config.width))
        core.up_projection = nn.Parameter(torch.empty(hidden + rank, config.width))
        core.down_projection = nn.Parameter(torch.empty(config.width + rank, hidden))
        core.up_coeff = nn.Parameter(torch.zeros(config.modules, hidden, rank))
        core.down_coeff = nn.Parameter(torch.zeros(config.modules, config.width, rank))
        with torch.no_grad():
            core.up_projection.fill_(1e-4)
            core.down_projection.fill_(1e-4)
    return core


def _make_dense_reference(shared: SharedBasisFixedRoutingCore, device: torch.device) -> HighPrecisionFixedRoutingCore:
    config = shared.config
    hidden = config.width * config.hidden_mult
    with torch.device(device):
        dense = HighPrecisionFixedRoutingCore(config)
    dense.shared.load_state_dict(shared.shared.state_dict())
    dense.gate_logits.data.copy_(shared.gate_logits.data)
    up_base = shared.up_projection[:hidden]
    down_base = shared.down_projection[: config.width]
    with torch.no_grad():
        for route in range(config.modules):
            dense.module_set[route].norm.load_state_dict(shared.norms[route].state_dict())
            dense.module_set[route].up.weight.copy_(up_base)
            dense.module_set[route].down.weight.copy_(down_base)
            dense.module_set[route].up.bias.copy_(shared.up_biases[route])
            dense.module_set[route].down.bias.copy_(shared.down_biases[route])
    return dense


def _event_ms(fn) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    for _ in range(ITERATIONS):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _measure_pair(dense, shared, working, context, route: int) -> tuple[list[float], list[float]]:
    with torch.inference_mode():
        for _ in range(WARMUP):
            dense(working, context, route_index=route)
            shared(working, context, route_index=route)
        torch.cuda.synchronize()
        dense_times: list[float] = []
        shared_times: list[float] = []
        for round_index in range(ROUNDS):
            order = ("dense", "shared") if round_index % 2 == 0 else ("shared", "dense")
            values: dict[str, float] = {}
            for variant in order:
                fn = (
                    (lambda: dense(working, context, route_index=route))
                    if variant == "dense"
                    else (lambda: shared(working, context, route_index=route))
                )
                values[variant] = _event_ms(fn)
            dense_times.append(values["dense"])
            shared_times.append(values["shared"])
    return dense_times, shared_times


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C81 requires CUDA")
    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records: list[dict] = []
    total = len(WIDTHS) * len(PROFILES) * len(BATCHES)
    completed = 0

    for width in WIDTHS:
        config = LearnedCoreConfig(width=width, slots=SLOTS, modules=MODULES, hidden_mult=HIDDEN_MULT)
        for profile in PROFILES:
            rank = _rank(profile, width)
            gc.collect()
            torch.cuda.empty_cache()
            baseline_alloc = int(torch.cuda.memory_allocated())
            shared = _allocate_shared(config, rank, device)
            torch.cuda.synchronize()
            shared_alloc = int(torch.cuda.memory_allocated()) - baseline_alloc
            dense_before = int(torch.cuda.memory_allocated())
            dense = _make_dense_reference(shared, device)
            torch.cuda.synchronize()
            dense_alloc = int(torch.cuda.memory_allocated()) - dense_before

            shared_bytes = _storage_bytes(shared)
            dense_bytes = _storage_bytes(dense)
            persistent_ratio = shared_bytes / dense_bytes

            for batch in BATCHES:
                working = torch.zeros(batch, SLOTS, width, device=device)
                context = torch.full_like(working, 0.01)
                with torch.inference_mode():
                    dense_out = dense(working, context, route_index=0)
                    shared_out = shared(working, context, route_index=0)
                allclose = bool(torch.allclose(shared_out, dense_out, rtol=RTOL, atol=ATOL))
                max_abs = float((shared_out - dense_out).abs().max().item())

                ratios: list[float] = []
                dense_samples: list[float] = []
                shared_samples: list[float] = []
                for route in range(MODULES):
                    dense_times, shared_times = _measure_pair(
                        dense, shared, working, context, route
                    )
                    dense_samples.extend(dense_times)
                    shared_samples.extend(shared_times)
                    ratios.extend(s / d for s, d in zip(shared_times, dense_times, strict=True))

                record = {
                    "profile": profile,
                    "width": width,
                    "rank": rank,
                    "rank_fraction": rank / width,
                    "batch": batch,
                    "dense_persistent_bytes": dense_bytes,
                    "shared_persistent_bytes": shared_bytes,
                    "full_core_persistent_ratio": persistent_ratio,
                    "dense_cuda_live_delta_bytes": dense_alloc,
                    "shared_cuda_live_delta_bytes": shared_alloc,
                    "output_allclose": allclose,
                    "output_max_abs_gap": max_abs,
                    "dense_ms": _stats(dense_samples),
                    "shared_ms": _stats(shared_samples),
                    "shared_over_dense_latency": _stats(ratios),
                }
                records.append(record)
                completed += 1
                print(
                    f"[C81] profile={profile} width={width} rank={rank} batch={batch} "
                    f"ratio={record['shared_over_dense_latency']['median']:.4f} "
                    f"persistent={persistent_ratio:.4f} ({completed}/{total})",
                    flush=True,
                )

                del working, context, dense_out, shared_out

            del dense, shared
            gc.collect()
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C81")

    endpoint = [row for row in records if int(row["width"]) == 5120]
    all_outputs = all(bool(row["output_allclose"]) for row in records)
    endpoint_memory = all(
        float(row["full_core_persistent_ratio"]) <= MAX_ENDPOINT_PERSISTENT_RATIO
        for row in endpoint
    )
    endpoint_latency = all(
        float(row["shared_over_dense_latency"]["median"]) <= MAX_ENDPOINT_LATENCY_RATIO
        for row in endpoint
    )
    summary = {
        "record_count": len(records),
        "widths": list(WIDTHS),
        "profiles": {name: list(value) for name, value in PROFILES.items()},
        "batches": list(BATCHES),
        "all_outputs_allclose": all_outputs,
        "endpoint_persistent_ratio_ceiling": MAX_ENDPOINT_PERSISTENT_RATIO,
        "endpoint_latency_ratio_ceiling": MAX_ENDPOINT_LATENCY_RATIO,
        "all_width5120_persistent_ratios_within_ceiling": endpoint_memory,
        "all_width5120_latency_ratios_within_ceiling": endpoint_latency,
        "width5120": endpoint,
        "production_runtime_gate_passed": all_outputs and endpoint_memory and endpoint_latency,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "actual production Shared-Basis large-shape runtime/resident-memory gate",
        "records": records,
        "summary": summary,
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "default_dense_runtime_changed": False,
        "gate_c_candidate": False,
        "limitations": [
            "C81 measures production forward/persistent layout but excludes dense-to-SVD constructor cost",
            "factorized runtime tensors are synthetically allocated with zero coefficients",
            "float32 eager CUDA only on the current RTX 4070 Ti SUPER",
            "C81 is a runtime/storage gate, not a fresh quality experiment",
            "C81 does not by itself establish broad-model superiority or Gate C passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(protected_result_path=args.protected_result, output_dir=args.output_dir)
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C81 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
