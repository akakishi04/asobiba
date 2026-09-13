"""C71: selected-rank real-shape runtime and memory diagnostic.

C70 established that the GEMM-native shared-basis execution formula is
numerically/semantically equivalent to effective-weight materialization for the
three current Gate-B task shapes, including 64 repeated state updates. C71 now
asks the next isolated Gate-C question: what are the actual latency and
persistent/temporary-memory tradeoffs of that formula at the selected ranks and
real core shapes?

For each task shape, C71 builds one shared-basis core and derives two
semantically identical inference cores from exactly the same factor values:

1. ``dense_materialized`` stores independent effective Up/Down matrices for all
   routed modules and uses ordinary F.linear;
2. ``shared_basis_gemm`` stores shared [base; basis] projections plus
   module-specific coefficients and uses the C70 GEMM-native formula.

No task training or quality comparison is performed here because the two cores
represent the same effective routed weights by construction.  C71 measures core
inference only, at batch sizes 1/8/32 and both routes, so front-end/readout costs
do not hide the routed-core tradeoff.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _build_task,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_runtime_recurrence_equivalence import (
    GemmNativeSharedBasisCore,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C71-shared-basis-selected-shape-runtime-memory"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
TASKS = ("condition", "composition", "language")
BATCH_SIZES = (1, 8, 32)
VARIANTS = ("dense_materialized", "shared_basis_gemm")
ROUNDS = 20
ITERATIONS = 200
WARMUP = 50
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


def _tensor_bytes(tensor: torch.Tensor) -> int:
    return int(tensor.numel() * tensor.element_size())


def _module_persistent_bytes(module: nn.Module) -> int:
    seen: set[int] = set()
    total = 0
    for tensor in list(module.parameters()) + list(module.buffers()):
        pointer = int(tensor.data_ptr()) if tensor.numel() else id(tensor)
        if pointer in seen:
            continue
        seen.add(pointer)
        total += _tensor_bytes(tensor)
    return total


class MaterializedSharedBasisCore(nn.Module):
    """Dense effective-weight inference core equivalent to one factorized core."""

    def __init__(self, source: JointTrainSharedBasisCore) -> None:
        super().__init__()
        if not isinstance(source, JointTrainSharedBasisCore):
            raise TypeError("source must be JointTrainSharedBasisCore")
        self.config: LearnedCoreConfig = source.config
        self.rank = int(source.rank)
        self.shared = copy.deepcopy(source.shared)
        self.norms = copy.deepcopy(source.norms)
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.up_weights = nn.Parameter(
            torch.stack(
                [
                    source.up_base.detach()
                    + source.up_coeff[index].detach() @ source.up_basis.detach()
                    for index in range(source.config.modules)
                ],
                dim=0,
            ).clone()
        )
        self.down_weights = nn.Parameter(
            torch.stack(
                [
                    source.down_base.detach()
                    + source.down_coeff[index].detach() @ source.down_basis.detach()
                    for index in range(source.config.modules)
                ],
                dim=0,
            ).clone()
        )
        self.up_biases = nn.Parameter(source.up_biases.detach().clone())
        self.down_biases = nn.Parameter(source.down_biases.detach().clone())

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be positive")
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=self.up_weights.device if device is None else device,
            dtype=self.up_weights.dtype if dtype is None else dtype,
        )

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index out of range")
        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        hidden = F.linear(
            normalized,
            self.up_weights[route_index],
            self.up_biases[route_index],
        )
        hidden = F.gelu(hidden)
        routed_delta = F.linear(
            hidden,
            self.down_weights[route_index],
            self.down_biases[route_index],
        )
        gate = torch.sigmoid(self.gate_logits).to(dtype=z.dtype, device=z.device)
        return working + gate * (shared_delta + routed_delta)


def _routed_weight_bytes_dense(core: MaterializedSharedBasisCore) -> int:
    return _tensor_bytes(core.up_weights) + _tensor_bytes(core.down_weights)


def _routed_weight_bytes_shared(core: GemmNativeSharedBasisCore) -> int:
    return (
        _tensor_bytes(core.up_projection)
        + _tensor_bytes(core.down_projection)
        + _tensor_bytes(core.up_coeff)
        + _tensor_bytes(core.down_coeff)
    )


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


def _measure_peak_bytes(fn) -> dict[str, int]:
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    baseline = int(torch.cuda.memory_allocated())
    output = fn()
    torch.cuda.synchronize()
    peak = int(torch.cuda.max_memory_allocated())
    output_bytes = _tensor_bytes(output)
    del output
    torch.cuda.synchronize()
    return {
        "baseline_allocated_bytes": baseline,
        "peak_allocated_bytes": peak,
        "peak_delta_bytes": max(0, peak - baseline),
        "output_bytes": output_bytes,
    }


def _summarize(records: list[dict], structures: dict[str, dict]) -> dict:
    tasks: dict[str, dict] = {}
    all_latency_medians: list[float] = []
    all_peak_ratios: list[float] = []
    for task in TASKS:
        by_batch: dict[str, dict] = {}
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
                if row["kind"] == "latency"
            }
            ratios = [
                table[route, round_index, "shared_basis_gemm"]
                / table[route, round_index, "dense_materialized"]
                for route in range(2)
                for round_index in range(ROUNDS)
            ]
            peak_rows = [row for row in subset if row["kind"] == "peak_memory"]
            peaks = {
                str(row["variant"]): int(row["peak_delta_bytes"])
                for row in peak_rows
            }
            dense_peak = peaks["dense_materialized"]
            shared_peak = peaks["shared_basis_gemm"]
            peak_ratio = shared_peak / max(dense_peak, 1)
            latency_stats = _stats(ratios)
            all_latency_medians.append(float(latency_stats["median"]))
            all_peak_ratios.append(float(peak_ratio))
            by_batch[str(batch)] = {
                "shared_over_dense_latency": latency_stats,
                "forward_peak_delta_bytes": peaks,
                "shared_over_dense_peak_delta": peak_ratio,
            }
        structure = structures[task]
        tasks[task] = {
            **structure,
            "batches": by_batch,
        }
    return {
        "tasks": tasks,
        "latency_median_ratio_across_task_batch_points": _stats(all_latency_medians),
        "peak_delta_ratio_across_task_batch_points": _stats(all_peak_ratios),
        "worst_task_batch_latency_median_ratio": max(all_latency_medians),
        "best_task_batch_latency_median_ratio": min(all_latency_medians),
    }


@torch.inference_mode()
def run(*, protected_result_path: Path, c70_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C71 requires CUDA")

    c70 = json.loads(c70_summary_path.read_text(encoding="utf-8"))
    if c70.get("experiment_id") != "C70-shared-basis-runtime-recurrence-equivalence":
        raise RuntimeError("C71 requires accepted C70 summary")
    if c70.get("status") != "PASS":
        raise RuntimeError("C70 summary is not PASS")
    summary70 = c70.get("summary", {})
    required = (
        "all_validation_scores_equal",
        "all_validation_semantic_equal",
        "all_validation_outputs_allclose",
        "all_recurrence_allclose",
        "all_runtime_formula_equivalent",
    )
    if not all(bool(summary70.get(name, False)) for name in required):
        raise RuntimeError("C71 requires all accepted C70 equivalence gates")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(SOURCE_SEED)
    records: list[dict] = []
    structures: dict[str, dict] = {}

    for task_index, task in enumerate(TASKS):
        spec = TASK_SPECS[task]
        rank = int(spec["rank"])
        torch.manual_seed(SOURCE_SEED + task_index)
        _config, initial_model, _train, _validation, _evaluator = _build_task(
            task, SOURCE_SEED + task_index, device
        )
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C71 initial core must be HighPrecisionFixedRoutingCore")

        source = JointTrainSharedBasisCore(initial_model.core, rank).to(device)
        dense = MaterializedSharedBasisCore(source).to(device).eval()
        shared = GemmNativeSharedBasisCore(source).to(device).eval()

        width = int(source.config.width)
        hidden = width * int(source.config.hidden_mult)
        theoretical = _storage(width=width, hidden=hidden, rank=rank)
        dense_routed = _routed_weight_bytes_dense(dense)
        shared_routed = _routed_weight_bytes_shared(shared)
        if dense_routed != int(theoretical["dense_weight_bytes"]):
            raise RuntimeError(f"C71 task={task} dense routed byte mismatch")
        if shared_routed != int(theoretical["representation_weight_bytes"]):
            raise RuntimeError(f"C71 task={task} shared routed byte mismatch")

        dense_core_bytes = _module_persistent_bytes(dense)
        shared_core_bytes = _module_persistent_bytes(shared)
        structures[task] = {
            "rank": rank,
            "width": width,
            "hidden": hidden,
            "slots": int(source.config.slots),
            "modules": int(source.config.modules),
            "dense_routed_weight_bytes": dense_routed,
            "shared_routed_weight_bytes": shared_routed,
            "routed_weight_ratio": shared_routed / dense_routed,
            "dense_full_core_persistent_bytes": dense_core_bytes,
            "shared_full_core_persistent_bytes": shared_core_bytes,
            "full_core_persistent_ratio": shared_core_bytes / dense_core_bytes,
        }

        print(
            f"[C71] task={task} rank={rank} slots={source.config.slots} width={width} "
            f"routed_ratio={shared_routed / dense_routed:.6f} "
            f"full_core_ratio={shared_core_bytes / dense_core_bytes:.6f}",
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

            calls: dict[tuple[str, int], object] = {}
            for route in range(source.config.modules):
                dense_call = lambda r=route, w=working, c=context: dense(w, c, route_index=r)
                shared_call = lambda r=route, w=working, c=context: shared(w, c, route_index=r)
                dense_out = dense_call()
                shared_out = shared_call()
                torch.testing.assert_close(shared_out, dense_out, rtol=RTOL, atol=ATOL)
                calls[("dense_materialized", route)] = dense_call
                calls[("shared_basis_gemm", route)] = shared_call

            # Peak activation/workspace memory uses route 0; both routes have the
            # same tensor shapes and persistent storage.
            for variant in VARIANTS:
                peak = _measure_peak_bytes(calls[(variant, 0)])
                records.append(
                    {
                        "kind": "peak_memory",
                        "task": task,
                        "batch_size": batch,
                        "route_index": 0,
                        "round": -1,
                        "variant": variant,
                        **peak,
                    }
                )

            for variant in VARIANTS:
                for route in range(source.config.modules):
                    for _ in range(WARMUP):
                        calls[(variant, route)]()
            torch.cuda.synchronize()

            for round_index in range(ROUNDS):
                order = VARIANTS if round_index % 2 == 0 else tuple(reversed(VARIANTS))
                for route in range(source.config.modules):
                    for variant in order:
                        timing = _measure_latency(calls[(variant, route)])
                        records.append(
                            {
                                "kind": "latency",
                                "task": task,
                                "batch_size": batch,
                                "route_index": route,
                                "round": round_index,
                                "variant": variant,
                                "device_ms": timing,
                            }
                        )
            print(
                f"[C71] task={task} batch={batch} measured routes=2 rounds={ROUNDS}",
                flush=True,
            )

        del initial_model, source, dense, shared
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C71")

    summary = _summarize(records, structures)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "selected-rank real-shape core latency and memory diagnostic",
        "tasks": list(TASKS),
        "batch_sizes": list(BATCH_SIZES),
        "variants": list(VARIANTS),
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "source_seed": SOURCE_SEED,
        "summary": summary,
        "C70_summary_sha256": _sha256(c70_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C71 benchmarks the routed core only; task front ends/readouts are intentionally excluded",
            "eager CUDA execution is measured; CUDA Graph residency/latency is deferred",
            "peak delta is allocator-observed forward memory, not total process VRAM",
            "the task shapes and selected ranks are current small Gate-B/Gate-C points, not production LLM scale",
            "C71 does not by itself establish Gate C passage",
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
    parser.add_argument("--c70-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c70_summary_path=args.c70_summary,
        output_dir=args.output_dir,
    )
    result["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C71 RESULT ===")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
