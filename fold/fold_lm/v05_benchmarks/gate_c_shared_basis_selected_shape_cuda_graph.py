"""C72: selected-shape CUDA Graph latency diagnostic for shared-basis execution.

C71 measured selected-rank real task-shape core inference in eager CUDA and
found persistent-core storage savings but roughly 1.30-1.42x median latency for
the GEMM-native shared-basis formula. C58 had already suggested that small
shared-basis shapes are launch/shape dominated. C72 changes exactly one runtime
axis: execution is captured and replayed with CUDA Graphs.

For the same condition/composition/language core shapes, selected ranks, and
batch sizes 1/8/32 used by C71, C72 derives two semantically identical inference
cores from the same factor values:

1. dense_materialized: independent effective Up/Down matrices;
2. shared_basis_gemm: shared [base; basis] projection plus coefficient addmm.

Each route/variant is captured separately with static inputs and replay latency
is measured with CUDA events. The accepted C71 eager median ratio for the same
(task,batch) point is carried into the report so we can directly diagnose how
much of the eager penalty was launch overhead.

C72 does not modify production runtime and does not claim production-scale
latency; it is a graph-replay diagnostic at the currently selected small shapes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _build_task,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_runtime_recurrence_equivalence import (
    GemmNativeSharedBasisCore,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_selected_shape_runtime_memory import (
    MaterializedSharedBasisCore,
)


EXPERIMENT_ID = "C72-shared-basis-selected-shape-cuda-graph"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
TASKS = ("condition", "composition", "language")
BATCH_SIZES = (1, 8, 32)
VARIANTS = ("dense_materialized", "shared_basis_gemm")
ROUNDS = 20
ITERATIONS = 500
CAPTURE_WARMUP = 20
REPLAY_WARMUP = 50
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


def _measure_graph(graph: torch.cuda.CUDAGraph) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERATIONS):
        graph.replay()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _capture_graph(core, working: torch.Tensor, context: torch.Tensor, route_index: int):
    # Warm up on a side stream so lazy CUDA library initialization is complete
    # before graph capture starts.
    warmup_stream = torch.cuda.Stream()
    warmup_stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(warmup_stream):
        for _ in range(CAPTURE_WARMUP):
            core(working, context, route_index=route_index)
    torch.cuda.current_stream().wait_stream(warmup_stream)
    torch.cuda.synchronize()

    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):
        output = core(working, context, route_index=route_index)
    graph.replay()
    torch.cuda.synchronize()
    return graph, output


def _summarize(records: list[dict], c71: dict) -> dict:
    task_summary: dict[str, dict] = {}
    graph_point_medians: list[float] = []
    eager_point_medians: list[float] = []
    ratio_of_ratios: list[float] = []

    c71_tasks = c71.get("summary", {}).get("tasks", {})
    for task in TASKS:
        batches: dict[str, dict] = {}
        for batch in BATCH_SIZES:
            subset = [
                row
                for row in records
                if row["task"] == task and int(row["batch_size"]) == batch
            ]
            table = {
                (int(row["route_index"]), int(row["round"]), str(row["variant"])):
                float(row["device_ms"])
                for row in subset
            }
            ratios = [
                table[route, round_index, "shared_basis_gemm"]
                / table[route, round_index, "dense_materialized"]
                for route in range(2)
                for round_index in range(ROUNDS)
            ]
            graph_stats = _stats(ratios)
            eager_median = float(
                c71_tasks[task]["batches"][str(batch)]["shared_over_dense_latency"]["median"]
            )
            graph_median = float(graph_stats["median"])
            relative_to_eager = graph_median / eager_median
            graph_point_medians.append(graph_median)
            eager_point_medians.append(eager_median)
            ratio_of_ratios.append(relative_to_eager)
            batches[str(batch)] = {
                "shared_over_dense_graph_latency": graph_stats,
                "c71_eager_shared_over_dense_median": eager_median,
                "graph_median_over_eager_median": relative_to_eager,
                "absolute_ratio_reduction_vs_eager": eager_median - graph_median,
            }
        task_summary[task] = {
            "rank": int(TASK_SPECS[task]["rank"]),
            "batches": batches,
        }

    return {
        "tasks": task_summary,
        "graph_latency_median_ratio_across_task_batch_points": _stats(graph_point_medians),
        "c71_eager_latency_median_ratio_across_same_points": _stats(eager_point_medians),
        "graph_over_eager_ratio_of_ratios": _stats(ratio_of_ratios),
        "points_graph_ratio_below_eager_ratio": sum(
            graph < eager for graph, eager in zip(graph_point_medians, eager_point_medians)
        ),
        "point_count": len(graph_point_medians),
        "best_graph_point_median_ratio": min(graph_point_medians),
        "worst_graph_point_median_ratio": max(graph_point_medians),
    }


@torch.inference_mode()
def run(*, protected_result_path: Path, c71_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C72 requires CUDA")

    c71 = json.loads(c71_summary_path.read_text(encoding="utf-8"))
    if c71.get("experiment_id") != "C71-shared-basis-selected-shape-runtime-memory":
        raise RuntimeError("C72 requires accepted C71 summary")
    if c71.get("status") != "PASS":
        raise RuntimeError("C71 summary is not PASS")
    if tuple(c71.get("tasks", ())) != TASKS:
        raise RuntimeError("C72 requires the accepted C71 task set")
    if tuple(int(v) for v in c71.get("batch_sizes", ())) != BATCH_SIZES:
        raise RuntimeError("C72 requires the accepted C71 batch set")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(SOURCE_SEED)
    records: list[dict] = []
    equivalence: dict[str, dict] = {}

    for task_index, task in enumerate(TASKS):
        rank = int(TASK_SPECS[task]["rank"])
        torch.manual_seed(SOURCE_SEED + task_index)
        _config, initial_model, _train, _validation, _evaluator = _build_task(
            task, SOURCE_SEED + task_index, device
        )
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C72 initial core must be HighPrecisionFixedRoutingCore")

        source = JointTrainSharedBasisCore(initial_model.core, rank).to(device).eval()
        dense = MaterializedSharedBasisCore(source).to(device).eval()
        shared = GemmNativeSharedBasisCore(source).to(device).eval()
        equivalence[task] = {}

        print(
            f"[C72] task={task} rank={rank} slots={source.config.slots} width={source.config.width}",
            flush=True,
        )

        for batch in BATCH_SIZES:
            working = (
                torch.randn(
                    batch,
                    source.config.slots,
                    source.config.width,
                    generator=generator,
                    dtype=torch.float32,
                )
                * INPUT_SCALE
            ).to(device)
            context = (
                torch.randn(
                    batch,
                    source.config.slots,
                    source.config.width,
                    generator=generator,
                    dtype=torch.float32,
                )
                * INPUT_SCALE
            ).to(device)

            graphs: dict[tuple[str, int], torch.cuda.CUDAGraph] = {}
            outputs: dict[tuple[str, int], torch.Tensor] = {}
            for route in range(source.config.modules):
                eager_dense = dense(working, context, route_index=route)
                eager_shared = shared(working, context, route_index=route)
                torch.testing.assert_close(eager_shared, eager_dense, rtol=RTOL, atol=ATOL)

                dense_graph, dense_output = _capture_graph(dense, working, context, route)
                shared_graph, shared_output = _capture_graph(shared, working, context, route)
                dense_graph.replay()
                shared_graph.replay()
                torch.cuda.synchronize()
                torch.testing.assert_close(shared_output, dense_output, rtol=RTOL, atol=ATOL)
                torch.testing.assert_close(dense_output, eager_dense, rtol=RTOL, atol=ATOL)
                torch.testing.assert_close(shared_output, eager_shared, rtol=RTOL, atol=ATOL)
                graphs[("dense_materialized", route)] = dense_graph
                graphs[("shared_basis_gemm", route)] = shared_graph
                outputs[("dense_materialized", route)] = dense_output
                outputs[("shared_basis_gemm", route)] = shared_output

            max_gap = max(
                float(
                    (
                        outputs[("shared_basis_gemm", route)].float()
                        - outputs[("dense_materialized", route)].float()
                    ).abs().max().item()
                )
                for route in range(source.config.modules)
            )
            equivalence[task][str(batch)] = {
                "max_abs_graph_output_gap": max_gap,
                "allclose": True,
            }

            for graph in graphs.values():
                for _ in range(REPLAY_WARMUP):
                    graph.replay()
            torch.cuda.synchronize()

            for round_index in range(ROUNDS):
                order = VARIANTS if round_index % 2 == 0 else tuple(reversed(VARIANTS))
                for route in range(source.config.modules):
                    for variant in order:
                        timing = _measure_graph(graphs[(variant, route)])
                        records.append(
                            {
                                "task": task,
                                "batch_size": batch,
                                "route_index": route,
                                "round": round_index,
                                "variant": variant,
                                "device_ms": timing,
                            }
                        )
            print(
                f"[C72] task={task} batch={batch} graph measured routes=2 rounds={ROUNDS} "
                f"max_gap={max_gap:.3e}",
                flush=True,
            )

            del graphs, outputs
            torch.cuda.empty_cache()

        del initial_model, source, dense, shared
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C72")

    summary = _summarize(records, c71)
    summary["all_graph_outputs_allclose"] = all(
        bool(row["allclose"])
        for task_rows in equivalence.values()
        for row in task_rows.values()
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "selected-shape CUDA Graph replay latency diagnostic",
        "tasks": list(TASKS),
        "batch_sizes": list(BATCH_SIZES),
        "variants": list(VARIANTS),
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "capture_warmup": CAPTURE_WARMUP,
        "replay_warmup": REPLAY_WARMUP,
        "source_seed": SOURCE_SEED,
        "summary": summary,
        "graph_output_equivalence": equivalence,
        "C71_summary_sha256": _sha256(c71_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C72 measures fixed-shape CUDA Graph replay, not dynamic-shape eager execution",
            "graph memory residency is not isolated in C72",
            "the task shapes and selected ranks remain small Gate-B/Gate-C points",
            "C72 does not establish production-scale latency or Gate C passage",
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
    parser.add_argument("--c71-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c71_summary_path=args.c71_summary,
        output_dir=args.output_dir,
    )
    result["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C72 RESULT ===")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
