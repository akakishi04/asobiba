"""C73: full-core width/rank scaling after selected-shape runtime diagnostics.

C71 showed that the selected small Gate-B shapes save persistent bytes but incur
~1.30-1.42x eager latency for GEMM-native shared-basis execution. C72 showed
that CUDA Graph replay does not remove that penalty overall, so launch overhead
alone is not the explanation.

C73 isolates model scale. It keeps the same two-route, hidden_mult=2 full-core
structure and compares semantically identical inference cores across widths
32..5120. Three rank fractions reproduce the routed-weight capacity bands that
matter in the accepted quality experiments:

- lean:   rank = width/16  -> routed ratio 0.5703125 asymptotically/exactly here;
- medium: rank = width/8   -> routed ratio 0.640625;
- high:   rank = width/4   -> routed ratio 0.78125.

The extended sweep includes 1536/2048/3072/4096/5120 so the transition from
small launch/shape-dominated cores to substantially larger GEMM workloads is
measured directly. 5120 is used rather than 5096 because every width must be
divisible by 16/8/4 for the three rank profiles.

Each point measures eager CUDA core latency at slots=20 and batch sizes 1/8,
plus persistent full-core bytes and allocator-observed forward peak delta.
No training or task-quality claim is made: dense-materialized and shared-basis
cores are derived from the exact same factor values.
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
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_runtime_recurrence_equivalence import (
    GemmNativeSharedBasisCore,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_selected_shape_runtime_memory import (
    MaterializedSharedBasisCore,
    _measure_peak_bytes,
    _module_persistent_bytes,
    _routed_weight_bytes_dense,
    _routed_weight_bytes_shared,
)


EXPERIMENT_ID = "C73-shared-basis-full-core-width-rank-scaling"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
WIDTHS = (32, 64, 128, 256, 512, 1024, 1536, 2048, 3072, 4096, 5120)
RANK_PROFILES = {
    "lean": 16,
    "medium": 8,
    "high": 4,
}
BATCH_SIZES = (1, 8)
SLOTS = 20
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


def _first_width_at_or_below(points: dict[str, dict], *, batch: int, threshold: float):
    for width in WIDTHS:
        value = float(points[str(width)]["batches"][str(batch)]["shared_over_dense_latency"]["median"])
        if value <= threshold:
            return width
    return None


def _summarize(records: list[dict], structures: dict[str, dict]) -> dict:
    profiles: dict[str, dict] = {}
    all_point_medians: list[float] = []
    all_peak_ratios: list[float] = []

    for profile in RANK_PROFILES:
        profile_points: dict[str, dict] = {}
        for width in WIDTHS:
            structure = structures[profile][str(width)]
            batches: dict[str, dict] = {}
            for batch in BATCH_SIZES:
                subset = [
                    row for row in records
                    if row["profile"] == profile
                    and int(row["width"]) == width
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
                latency = _stats(ratios)
                peak_rows = [row for row in subset if row["kind"] == "peak_memory"]
                peaks = {str(row["variant"]): int(row["peak_delta_bytes"]) for row in peak_rows}
                peak_ratio = peaks["shared_basis_gemm"] / max(peaks["dense_materialized"], 1)
                all_point_medians.append(float(latency["median"]))
                all_peak_ratios.append(float(peak_ratio))
                batches[str(batch)] = {
                    "shared_over_dense_latency": latency,
                    "forward_peak_delta_bytes": peaks,
                    "shared_over_dense_peak_delta": peak_ratio,
                }
            profile_points[str(width)] = {**structure, "batches": batches}

        threshold_summary = {}
        for batch in BATCH_SIZES:
            threshold_summary[str(batch)] = {
                "first_width_median_le_1_25": _first_width_at_or_below(
                    profile_points, batch=batch, threshold=1.25
                ),
                "first_width_median_le_1_15": _first_width_at_or_below(
                    profile_points, batch=batch, threshold=1.15
                ),
                "first_width_median_le_1_10": _first_width_at_or_below(
                    profile_points, batch=batch, threshold=1.10
                ),
            }
        profiles[profile] = {
            "rank_divisor": RANK_PROFILES[profile],
            "points": profile_points,
            "thresholds": threshold_summary,
        }

    return {
        "profiles": profiles,
        "latency_median_ratio_across_all_points": _stats(all_point_medians),
        "peak_delta_ratio_across_all_points": _stats(all_peak_ratios),
    }


@torch.inference_mode()
def run(*, protected_result_path: Path, c72_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C73 requires CUDA")

    c72 = json.loads(c72_summary_path.read_text(encoding="utf-8"))
    if c72.get("experiment_id") != "C72-shared-basis-selected-shape-cuda-graph":
        raise RuntimeError("C73 requires accepted C72 summary")
    if c72.get("status") != "PASS":
        raise RuntimeError("C72 summary is not PASS")
    if not bool(c72.get("summary", {}).get("all_graph_outputs_allclose", False)):
        raise RuntimeError("C73 requires C72 graph equivalence")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(SOURCE_SEED)
    records: list[dict] = []
    structures: dict[str, dict] = {profile: {} for profile in RANK_PROFILES}
    total_points = len(RANK_PROFILES) * len(WIDTHS) * len(BATCH_SIZES)
    completed = 0

    for profile_index, (profile, divisor) in enumerate(RANK_PROFILES.items()):
        for width_index, width in enumerate(WIDTHS):
            rank = width // divisor
            if rank <= 0 or width % divisor != 0:
                raise RuntimeError(f"invalid C73 rank profile {profile} width={width}")

            torch.manual_seed(SOURCE_SEED + 1000 * profile_index + width_index)
            source_dense = HighPrecisionFixedRoutingCore(
                LearnedCoreConfig(
                    width=width,
                    slots=SLOTS,
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
                "hidden": width * HIDDEN_MULT,
                "slots": SLOTS,
                "modules": MODULES,
                "rank": rank,
                "rank_fraction": rank / width,
                "dense_routed_weight_bytes": dense_routed,
                "shared_routed_weight_bytes": shared_routed,
                "routed_weight_ratio": shared_routed / dense_routed,
                "dense_full_core_persistent_bytes": dense_core,
                "shared_full_core_persistent_bytes": shared_core,
                "full_core_persistent_ratio": shared_core / dense_core,
            }

            print(
                f"[C73] profile={profile} width={width} rank={rank} "
                f"routed_ratio={shared_routed / dense_routed:.6f} "
                f"core_ratio={shared_core / dense_core:.6f}",
                flush=True,
            )

            for batch in BATCH_SIZES:
                working = (
                    torch.randn(
                        batch,
                        SLOTS,
                        width,
                        generator=generator,
                        dtype=torch.float32,
                    ) * INPUT_SCALE
                ).to(device)
                context = (
                    torch.randn(
                        batch,
                        SLOTS,
                        width,
                        generator=generator,
                        dtype=torch.float32,
                    ) * INPUT_SCALE
                ).to(device)

                calls = {}
                for route in range(MODULES):
                    dense_call = lambda r=route, w=working, c=context: dense(w, c, route_index=r)
                    shared_call = lambda r=route, w=working, c=context: shared(w, c, route_index=r)
                    dense_out = dense_call()
                    shared_out = shared_call()
                    torch.testing.assert_close(shared_out, dense_out, rtol=RTOL, atol=ATOL)
                    calls[("dense_materialized", route)] = dense_call
                    calls[("shared_basis_gemm", route)] = shared_call

                for variant in ("dense_materialized", "shared_basis_gemm"):
                    peak = _measure_peak_bytes(calls[(variant, 0)])
                    records.append({
                        "kind": "peak_memory",
                        "profile": profile,
                        "width": width,
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
                                "batch_size": batch,
                                "route_index": route,
                                "round": round_index,
                                "variant": variant,
                                "device_ms": timing,
                            })

                completed += 1
                print(
                    f"[C73] profile={profile} width={width} batch={batch} "
                    f"done ({completed}/{total_points})",
                    flush=True,
                )

            del source_dense, source, dense, shared
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C73")

    summary = _summarize(records, structures)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "full-core width/rank scaling for GEMM-native shared-basis execution",
        "widths": list(WIDTHS),
        "rank_profiles": RANK_PROFILES,
        "batch_sizes": list(BATCH_SIZES),
        "slots": SLOTS,
        "modules": MODULES,
        "hidden_mult": HIDDEN_MULT,
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "summary": summary,
        "C72_summary_sha256": _sha256(c72_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C73 uses synthetic factor values and tests runtime/storage scaling only",
            "slots are fixed to 20 and batches to 1/8 rather than covering all deployment shapes",
            "only float32 eager CUDA is measured",
            "rank fractions are representative accepted capacity bands, not newly quality-validated at large widths",
            "the extended sweep reaches width5120 but still does not establish production LLM scale",
            "C73 does not by itself establish Gate C passage",
        ],
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    display = {key: value for key, value in report.items() if key != "records"}
    return display


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c72-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c72_summary_path=args.c72_summary,
        output_dir=args.output_dir,
    )
    result["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C73 RESULT ===")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
