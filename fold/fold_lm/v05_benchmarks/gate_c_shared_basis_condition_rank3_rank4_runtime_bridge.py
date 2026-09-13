"""C75: runtime/storage bridge between Condition rank3 and accepted rank4.

C73 showed that GEMM-native Shared Basis runtime tax is strongly rank-fraction
dependent: width/16 and width/8 become close to Dense at large widths, whereas
width/4 retains roughly a 20%+ endpoint tax. C74 then tested the previously
unmeasured Condition rank3 point. Rank3 saves routed bytes versus rank4 but its
12-seed exhaustive quality evidence is mildly worse versus Dense and therefore
is not automatically adopted.

C75 asks one isolated question before spending more quality experiments:
how much runtime and persistent-storage benefit does rank3 actually buy relative
to rank4?

Two rank profiles are measured with semantically identical Dense-vs-Shared
pairs inside each profile:

- rank3_bridge: rank = 3 * width / 16  (Condition width16 -> rank3)
- rank4_high:   rank = width / 4       (Condition width16 -> rank4)

The sweep includes the exact Condition width16 scale plus larger widths through
5120. Large widths use slots=20 and batches 1/8 to align with C73; width16 also
includes the real Condition-like slots=1 point. No task quality is measured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import JointTrainSharedBasisCore
from fold_lm.v05_benchmarks.gate_c_shared_basis_runtime_recurrence_equivalence import GemmNativeSharedBasisCore
from fold_lm.v05_benchmarks.gate_c_shared_basis_selected_shape_runtime_memory import (
    MaterializedSharedBasisCore,
    _measure_peak_bytes,
    _module_persistent_bytes,
    _routed_weight_bytes_dense,
    _routed_weight_bytes_shared,
)

EXPERIMENT_ID = "C75-shared-basis-condition-rank3-rank4-runtime-bridge"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
WIDTHS = (16, 32, 64, 128, 256, 512, 1024, 2048, 3072, 4096, 5120)
PROFILES = {
    "rank3_bridge": (3, 16),
    "rank4_high": (1, 4),
}
BATCH_SIZES = (1, 8)
SLOTS_LARGE = 20
MODULES = 2
HIDDEN_MULT = 2
ROUNDS = 10
ITERATIONS = 50
WARMUP = 20
SOURCE_SEED = 20260914
INPUT_SCALE = 0.05
RTOL = 5e-4
ATOL = 1e-4


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


def _measure_latency(fn) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERATIONS):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _rank(profile: str, width: int) -> int:
    numerator, denominator = PROFILES[profile]
    value = width * numerator
    if value % denominator != 0:
        raise RuntimeError(f"C75 non-integral rank profile={profile} width={width}")
    rank = value // denominator
    if rank <= 0:
        raise RuntimeError("C75 rank must be positive")
    return rank


def _summarize(records: list[dict], structures: dict[str, dict]) -> dict:
    profiles = {}
    for profile in PROFILES:
        points = {}
        for width in WIDTHS:
            structure = structures[profile][str(width)]
            slots_to_measure = (1, SLOTS_LARGE) if width == 16 else (SLOTS_LARGE,)
            slot_points = {}
            for slots in slots_to_measure:
                batch_points = {}
                for batch in BATCH_SIZES:
                    subset = [
                        row for row in records
                        if row["profile"] == profile
                        and int(row["width"]) == width
                        and int(row["slots"]) == slots
                        and int(row["batch_size"]) == batch
                    ]
                    table = {
                        (int(row["route_index"]), int(row["round"]), str(row["variant"])):
                            float(row["device_ms"])
                        for row in subset
                        if row["kind"] == "latency"
                    }
                    ratios = [
                        table[route, round_index, "shared_basis_gemm"]
                        / table[route, round_index, "dense_materialized"]
                        for route in range(MODULES)
                        for round_index in range(ROUNDS)
                    ]
                    peak_rows = [row for row in subset if row["kind"] == "peak_memory"]
                    peaks = {str(row["variant"]): int(row["peak_delta_bytes"]) for row in peak_rows}
                    batch_points[str(batch)] = {
                        "shared_over_dense_latency": _stats(ratios),
                        "forward_peak_delta_bytes": peaks,
                        "shared_over_dense_peak_delta": (
                            peaks["shared_basis_gemm"] / max(peaks["dense_materialized"], 1)
                        ),
                    }
                slot_points[str(slots)] = {"batches": batch_points}
            points[str(width)] = {**structure, "slot_points": slot_points}
        profiles[profile] = {"points": points}

    comparisons = {}
    for width in WIDTHS:
        if width == 16:
            slots_values = (1, SLOTS_LARGE)
        else:
            slots_values = (SLOTS_LARGE,)
        width_comparison = {}
        for slots in slots_values:
            batch_comparison = {}
            for batch in BATCH_SIZES:
                r3 = float(
                    profiles["rank3_bridge"]["points"][str(width)]["slot_points"][str(slots)]
                    ["batches"][str(batch)]["shared_over_dense_latency"]["median"]
                )
                r4 = float(
                    profiles["rank4_high"]["points"][str(width)]["slot_points"][str(slots)]
                    ["batches"][str(batch)]["shared_over_dense_latency"]["median"]
                )
                batch_comparison[str(batch)] = {
                    "rank3_shared_over_dense_median": r3,
                    "rank4_shared_over_dense_median": r4,
                    "rank3_minus_rank4_latency_ratio": r3 - r4,
                    "rank3_over_rank4_latency_tax_ratio": r3 / r4,
                }
            width_comparison[str(slots)] = {"batches": batch_comparison}
        comparisons[str(width)] = width_comparison

    r3_struct = structures["rank3_bridge"]["5120"]
    r4_struct = structures["rank4_high"]["5120"]
    return {
        "profiles": profiles,
        "comparisons": comparisons,
        "width5120_full_core_persistent_ratio_rank3": r3_struct["full_core_persistent_ratio"],
        "width5120_full_core_persistent_ratio_rank4": r4_struct["full_core_persistent_ratio"],
        "width5120_rank3_over_rank4_persistent_bytes": (
            r3_struct["shared_full_core_persistent_bytes"]
            / r4_struct["shared_full_core_persistent_bytes"]
        ),
        "condition_width16_rank3_routed_ratio": structures["rank3_bridge"]["16"]["routed_weight_ratio"],
        "condition_width16_rank4_routed_ratio": structures["rank4_high"]["16"]["routed_weight_ratio"],
    }


@torch.inference_mode()
def run(*, protected_result_path: Path, c74_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C75 requires CUDA")

    c74 = json.loads(c74_summary_path.read_text(encoding="utf-8"))
    if c74.get("experiment_id") != "C74-shared-basis-condition-rank3-12seed-exhaustive":
        raise RuntimeError("C75 requires accepted C74 summary")
    if c74.get("status") != "PASS":
        raise RuntimeError("C74 summary is not PASS")
    if int(c74.get("rank", -1)) != 3 or int(c74.get("accepted_rank", -1)) != 4:
        raise RuntimeError("C75 requires C74 rank3-vs-rank4 setup")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(SOURCE_SEED)
    records: list[dict] = []
    structures: dict[str, dict] = {profile: {} for profile in PROFILES}
    total = sum((2 if width == 16 else 1) * len(BATCH_SIZES) for width in WIDTHS) * len(PROFILES)
    completed = 0

    for profile_index, profile in enumerate(PROFILES):
        for width_index, width in enumerate(WIDTHS):
            rank = _rank(profile, width)
            slots_for_structure = SLOTS_LARGE
            torch.manual_seed(SOURCE_SEED + 1000 * profile_index + width_index)
            source_dense = HighPrecisionFixedRoutingCore(
                LearnedCoreConfig(
                    width=width,
                    slots=slots_for_structure,
                    modules=MODULES,
                    hidden_mult=HIDDEN_MULT,
                )
            ).to(device)
            source = JointTrainSharedBasisCore(source_dense, rank).to(device)
            dense = MaterializedSharedBasisCore(source).to(device).eval()
            shared = GemmNativeSharedBasisCore(source).to(device).eval()

            dense_routed = _routed_weight_bytes_dense(dense)
            shared_routed = _routed_weight_bytes_shared(shared)
            dense_core = _module_persistent_bytes(dense)
            shared_core = _module_persistent_bytes(shared)
            structures[profile][str(width)] = {
                "width": width,
                "rank": rank,
                "rank_fraction": rank / width,
                "dense_routed_weight_bytes": dense_routed,
                "shared_routed_weight_bytes": shared_routed,
                "routed_weight_ratio": shared_routed / dense_routed,
                "dense_full_core_persistent_bytes": dense_core,
                "shared_full_core_persistent_bytes": shared_core,
                "full_core_persistent_ratio": shared_core / dense_core,
            }

            slots_values = (1, SLOTS_LARGE) if width == 16 else (SLOTS_LARGE,)
            for slots in slots_values:
                if slots != slots_for_structure:
                    # Rebuild only the shape-dependent container; weight dimensions and
                    # persistent accounting remain identical.
                    source_dense_s = HighPrecisionFixedRoutingCore(
                        LearnedCoreConfig(
                            width=width,
                            slots=slots,
                            modules=MODULES,
                            hidden_mult=HIDDEN_MULT,
                        )
                    ).to(device)
                    source_s = JointTrainSharedBasisCore(source_dense_s, rank).to(device)
                    dense_s = MaterializedSharedBasisCore(source_s).to(device).eval()
                    shared_s = GemmNativeSharedBasisCore(source_s).to(device).eval()
                else:
                    source_dense_s, source_s, dense_s, shared_s = source_dense, source, dense, shared

                for batch in BATCH_SIZES:
                    working = (
                        torch.randn(batch, slots, width, generator=generator, dtype=torch.float32)
                        * INPUT_SCALE
                    ).to(device)
                    context = (
                        torch.randn(batch, slots, width, generator=generator, dtype=torch.float32)
                        * INPUT_SCALE
                    ).to(device)
                    calls = {}
                    for route in range(MODULES):
                        dense_call = lambda r=route, w=working, c=context, m=dense_s: m(w, c, route_index=r)
                        shared_call = lambda r=route, w=working, c=context, m=shared_s: m(w, c, route_index=r)
                        torch.testing.assert_close(shared_call(), dense_call(), rtol=RTOL, atol=ATOL)
                        calls[("dense_materialized", route)] = dense_call
                        calls[("shared_basis_gemm", route)] = shared_call

                    for variant in ("dense_materialized", "shared_basis_gemm"):
                        peak = _measure_peak_bytes(calls[(variant, 0)])
                        records.append({
                            "kind": "peak_memory",
                            "profile": profile,
                            "width": width,
                            "slots": slots,
                            "batch_size": batch,
                            "route_index": 0,
                            "round": -1,
                            "variant": variant,
                            **peak,
                        })

                    for variant in ("dense_materialized", "shared_basis_gemm"):
                        for route in range(MODULES):
                            for _ in range(WARMUP):
                                calls[(variant, route)]()
                    torch.cuda.synchronize()

                    for round_index in range(ROUNDS):
                        order = (
                            ("dense_materialized", "shared_basis_gemm")
                            if round_index % 2 == 0
                            else ("shared_basis_gemm", "dense_materialized")
                        )
                        for route in range(MODULES):
                            for variant in order:
                                timing = _measure_latency(calls[(variant, route)])
                                records.append({
                                    "kind": "latency",
                                    "profile": profile,
                                    "width": width,
                                    "slots": slots,
                                    "batch_size": batch,
                                    "route_index": route,
                                    "round": round_index,
                                    "variant": variant,
                                    "device_ms": timing,
                                })

                    completed += 1
                    print(
                        f"[C75] profile={profile} width={width} rank={rank} slots={slots} "
                        f"batch={batch} done ({completed}/{total})",
                        flush=True,
                    )

                if slots != slots_for_structure:
                    del source_dense_s, source_s, dense_s, shared_s
                    torch.cuda.empty_cache()

            del source_dense, source, dense, shared
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C75")

    summary = _summarize(records, structures)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "runtime/storage bridge between Condition rank3 and rank4 capacity fractions",
        "widths": list(WIDTHS),
        "profiles": {name: {"numerator": value[0], "denominator": value[1]} for name, value in PROFILES.items()},
        "batch_sizes": list(BATCH_SIZES),
        "slots_large": SLOTS_LARGE,
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "summary": summary,
        "C74_summary_sha256": _sha256(c74_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C75 is runtime/storage only and does not add quality evidence for rank3",
            "large-width 3/16 ranks are scaling probes rather than quality-validated capacities",
            "float32 eager CUDA only",
            "C75 does not establish a formal quality equivalence margin or Gate C passage",
        ],
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return {key: value for key, value in report.items() if key != "records"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c74-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c74_summary_path=args.c74_summary,
        output_dir=args.output_dir,
    )
    result["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C75 RESULT ===")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
