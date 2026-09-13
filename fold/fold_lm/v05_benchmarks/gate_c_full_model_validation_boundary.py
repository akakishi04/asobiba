"""V5-C / C35: equal validation-policy comparison on a saved composition model.

C34 is synthetic and excludes correction E. C35 returns to an unchanged learned
fixture, including E, and measures dense/Triton under two labelled policies:
original per-operation checks versus diagnostic boundary checks. No kernel,
weights, routes, precision or production default is modified. Boundary validation
is NOT equivalent to rejecting every invalid intermediate at its point of use.
Event intervals include host submission gaps; they are not kernel-only timings.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

import torch

VARIANTS = ("dense_checked", "triton_checked", "dense_boundary", "triton_boundary")
METRICS = ("device_per_forward_ms", "wall_per_forward_ms")
COMPARISONS = {
    "triton_vs_dense_checked": ("triton_checked", "dense_checked"),
    "triton_vs_dense_boundary": ("triton_boundary", "dense_boundary"),
    "dense_checked_to_boundary_speedup": ("dense_checked", "dense_boundary"),
    "triton_checked_to_boundary_speedup": ("triton_checked", "triton_boundary"),
}


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def validate_scope(warmup, rounds, iterations):
    _integer(warmup, "warmup")
    _integer(rounds, "rounds", 1)
    _integer(iterations, "iterations", 1)


def order_for_round(index):
    _integer(index, "round index")
    offset = index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


def validate_task_metadata(config, initial, operations, operands):
    """No value reductions: input range checks belong to explicit preflight."""
    for value in (initial, operations, operands):
        if not isinstance(value, torch.Tensor):
            raise TypeError("composition inputs must be tensors")
        if value.dtype != torch.int64:
            raise TypeError("composition inputs must use int64")
    if initial.ndim != 1 or initial.shape[0] <= 0:
        raise ValueError("initial values must have shape [batch]")
    expected = (initial.shape[0], config.operation_steps)
    if tuple(operations.shape) != expected or tuple(operands.shape) != expected:
        raise ValueError("operation/operand shape mismatch")
    if initial.device != operations.device or initial.device != operands.device:
        raise ValueError("composition input devices must match")


def validate_state_metadata(config, working, context, route_index):
    if type(route_index) is not int or not 0 <= route_index < config.modules:
        raise ValueError("route_index out of range")
    if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
        raise TypeError("working/context must be tensors")
    if working.ndim != 3 or tuple(working.shape[1:]) != (config.slots, config.width):
        raise ValueError("working state shape mismatch")
    if context.shape != working.shape:
        raise ValueError("context shape mismatch")
    if not working.is_floating_point() or not context.is_floating_point():
        raise TypeError("working/context must be floating tensors")
    if working.dtype != context.dtype or working.device != context.device:
        raise ValueError("working/context dtype and device must match")


def make_models(dense_model, initializations):
    """Create private diagnostic subclasses, leaving all original classes intact."""
    from fold_lm.v05.composition_task import CompositionModel
    from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
    from fold_lm.v05.triton_runtime import (
        TritonCompressedFixedRoutingCore, TritonCompressedLinearBank,
    )
    from fold_lm.v05_benchmarks.gate_c_triton_validation_overhead import _StructuralValidationMixin

    if type(dense_model) is not CompositionModel or type(dense_model.core) is not HighPrecisionFixedRoutingCore:
        raise TypeError("C35 is restricted to the composition fixture and original dense core")
    device = next(dense_model.parameters()).device

    class BoundaryTask(CompositionModel):
        def _validate(self, initial_values, operations, operands):
            validate_task_metadata(self.config, initial_values, operations, operands)

    class BoundaryDenseCore(HighPrecisionFixedRoutingCore):
        def forward(self, working, context, *, route_index):
            validate_state_metadata(self.config, working, context, route_index)
            z = working + context
            shared_delta = self.shared(z)
            routed_delta = self.module_set[route_index](z)
            gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
            return working + gate * (shared_delta + routed_delta)

    class BoundaryBank(_StructuralValidationMixin, TritonCompressedLinearBank):
        pass  # Existing fused row-wise kernel INCLUDING correction E, unchanged.

    class BoundaryTritonCore(TritonCompressedFixedRoutingCore):
        def forward(self, working, context, *, route_index):
            validate_state_metadata(self.config, working, context, route_index)
            z = working + context
            shared_delta = self.shared(z)
            normalized = self.norms[route_index](z)
            hidden = self.up_bank(normalized, module_index=route_index) + self.up_biases[route_index]
            hidden = torch.nn.functional.gelu(hidden)
            routed_delta = self.down_bank(hidden, module_index=route_index) + self.down_biases[route_index]
            gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
            return working + gate * (shared_delta + routed_delta)

    checked_triton = copy.deepcopy(dense_model)
    checked_triton.core = TritonCompressedFixedRoutingCore(dense_model.core, initializations).to(device)
    boundary_dense = BoundaryTask(dense_model.config).to(device)
    boundary_dense.core = BoundaryDenseCore(dense_model.core.config).to(device)
    boundary_dense.load_state_dict(dense_model.state_dict(), strict=True)
    boundary_triton = BoundaryTask(dense_model.config).to(device)
    boundary_triton.core = BoundaryTritonCore(dense_model.core, initializations).to(device)
    boundary_triton.core.up_bank = BoundaryBank(initializations.up).to(device)
    boundary_triton.core.down_bank = BoundaryBank(initializations.down).to(device)
    boundary_triton.load_state_dict(checked_triton.state_dict(), strict=True)
    return {name: model.eval() for name, model in zip(
        VARIANTS, (dense_model, checked_triton, boundary_dense, boundary_triton))}


def trajectory_score(output, targets, scale):
    if (output.ndim != 2 or output.shape[0] <= 0 or targets.dtype != torch.int64
            or output.shape != targets.shape or not math.isfinite(float(scale)) or float(scale) <= 0
            or not bool(torch.isfinite(output).all())):
        raise ValueError("invalid or non-finite trajectory output")
    prediction = torch.round(output * float(scale)).to(torch.int64)
    return float((prediction == targets).all(dim=1).float().mean().item())


def summarize_records(records, scores, *, rounds):
    validate_scope(0, rounds, 1)
    if set(scores) != set(VARIANTS):
        raise ValueError("scores must contain exactly all variants")
    for value in scores.values():
        if isinstance(value, bool) or not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
            raise ValueError("invalid score")
    table = {}
    for record in records:
        r = _integer(record["round"], "round")
        name = record["variant"]
        if r >= rounds or name not in VARIANTS or (r, name) in table:
            raise ValueError("duplicate or out-of-scope record")
        for metric in METRICS:
            value = record[metric]
            if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError("timings must be positive and finite")
        table[r, name] = record
    if set(table) != {(r, name) for r in range(rounds) for name in VARIANTS}:
        raise ValueError("missing full-model round/variant records")
    def stats(values):
        return {"median": statistics.median(values), "min": min(values), "max": max(values)}
    result = {"rounds": rounds, "record_count": len(records), "variants": {}, "paired_ratios": {}}
    for name in VARIANTS:
        result["variants"][name] = {"score": float(scores[name])}
        for label, metric in zip(("device", "wall"), METRICS):
            result["variants"][name][label + "_ms"] = stats(
                [float(table[r, name][metric]) for r in range(rounds)])
    for key, (a, b) in COMPARISONS.items():
        for label, metric in zip(("device", "wall"), METRICS):
            result["paired_ratios"][key + "_" + label] = stats(
                [float(table[r, a][metric]) / float(table[r, b][metric]) for r in range(rounds)])
    return result


def _file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@torch.inference_mode()
def run_benchmark(fixture_path, *, device="cuda", warmup=10, rounds=8, iterations=50):
    validate_scope(warmup, rounds, iterations)
    if os.environ.get("CUDA_LAUNCH_BLOCKING") not in (None, "", "0"):
        raise RuntimeError("disable CUDA_LAUNCH_BLOCKING before benchmarking")
    requested = torch.device(device)
    if requested.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C35 requires CUDA")
    from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture
    from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import _load_initializations

    started = time.perf_counter()
    print("[C35] loading fixture (no training)", file=sys.stderr, flush=True)
    fixture = load_runtime_fixture(fixture_path, device=requested)
    if fixture["task"] != "composition":
        raise ValueError("C35 currently accepts composition fixtures only")
    initializations = _load_initializations(str(fixture_path))
    e_counts = {role: [int(w.correction_nnz) for w in getattr(initializations, role).encoded_weights]
                for role in ("up", "down")}
    if not any(sum(values) for values in e_counts.values()):
        raise ValueError("C35 requires a fixture with correction E present")
    dense = fixture["models"]["dense"]
    compact = fixture["models"]["compact"].eval()
    models = make_models(dense, initializations)
    examples = fixture["validation"]
    inputs = tuple(value.to(requested) for value in
                   (examples.initial_values, examples.operations, examples.operands))
    targets = examples.targets.to(requested)
    # This is the original strict validation, not the benchmark-only override.
    dense._validate(*inputs)
    for model in models.values():
        for tensor in model.state_dict().values():
            if tensor.is_floating_point() and not bool(torch.isfinite(tensor).all()):
                raise ValueError("non-finite model preflight state")

    old_precision = torch.get_float32_matmul_precision()
    torch.set_float32_matmul_precision("highest")
    records, outputs, scores, gaps = [], {}, {}, {}
    try:
        with torch.cuda.device(requested):
            compact_output = compact(*inputs)
            for name, model in models.items():
                output = model(*inputs)
                if not bool(torch.isfinite(output).all()):
                    raise ValueError("non-finite preflight output")
                outputs[name] = output.clone()
                scores[name] = trajectory_score(output, targets, dense.config.state_scale)
                expected_score = fixture["scores"]["dense" if name.startswith("dense") else "compact"]
                if abs(scores[name] - expected_score) > 1e-7:
                    raise RuntimeError(f"{name} did not preserve stored fixture score")
            for name, reference in (
                ("dense_boundary", outputs["dense_checked"]),
                ("triton_boundary", outputs["triton_checked"]),
                ("triton_checked", compact_output),
            ):
                torch.testing.assert_close(outputs[name], reference, rtol=1e-4, atol=1e-5)
                gaps[name] = float((outputs[name] - reference).abs().max().item())
            for model in models.values():
                for _ in range(warmup):
                    model(*inputs)
            torch.cuda.synchronize()
            events = (torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True))
            events[0].record(); events[1].record(); events[1].synchronize()
            for r in range(rounds):
                for name in order_for_round(r):
                    torch.cuda.synchronize()
                    wall_start = time.perf_counter()
                    events[0].record()
                    for _ in range(iterations):
                        output = models[name](*inputs)
                    events[1].record(); events[1].synchronize()
                    wall_ms = (time.perf_counter() - wall_start) * 1000.0 / iterations
                    device_ms = float(events[0].elapsed_time(events[1])) / iterations
                    # Numerical checks/target access are outside the timing region.
                    torch.testing.assert_close(output, outputs[name], rtol=1e-4, atol=1e-5)
                    if trajectory_score(output, targets, dense.config.state_scale) != scores[name]:
                        raise RuntimeError("task score changed during measurement")
                    records.append({"round": r, "variant": name, "order": list(order_for_round(r)),
                                    "device_per_forward_ms": device_ms, "wall_per_forward_ms": wall_ms})
                    elapsed = time.perf_counter() - started
                    eta = elapsed / len(records) * (rounds * len(VARIANTS) - len(records))
                    print(f"[C35] {len(records)}/{rounds * len(VARIANTS)} {name} "
                          f"device={device_ms:.3f}ms wall={wall_ms:.3f}ms "
                          f"elapsed={elapsed:.1f}s eta={eta:.1f}s", file=sys.stderr, flush=True)
    finally:
        torch.set_float32_matmul_precision(old_precision)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                         stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {
        "schema": "fold-v05-gate-c-full-model-validation-boundary-v1", "stage": "V5-C",
        "experiment_id": "C35", "commit_sha": commit, "fixture_path": str(fixture_path),
        "fixture_sha256": _file_hash(fixture_path), "task": fixture["task"], "seed": fixture["seed"],
        "device_name": torch.cuda.get_device_name(requested), "torch_version": str(torch.__version__),
        "cuda_version": torch.version.cuda, "width": dense.config.width,
        "validation_batch": examples.size, "operation_steps": dense.config.operation_steps,
        "core_calls_per_forward": 2 * dense.config.operation_steps,
        "correction_nnz_per_module_by_role": e_counts,
        "compact_bank_bytes_by_policy": {
            name: sum(getattr(models[name].core, role + "_bank").resident_tensor_bytes
                      for role in ("up", "down"))
            for name in ("triton_checked", "triton_boundary")},
        "float32_matmul_precision": "highest", "kernel_input_precision": "existing float32 rowwise kernel",
        "warmup": warmup, "rounds": rounds, "iterations_per_sample": iterations,
        "max_abs_output_gap_by_comparison": gaps, "scores": scores,
        "summary": summarize_records(records, scores, rounds=rounds), "records": records,
        "elapsed_seconds": time.perf_counter() - started, "retrained": False,
        "diagnostic_only": True, "gate_c_candidate": False, "production_runtime_modified": False,
        "known_deviations": [
            "boundary path skips per-operation value scans; not the production safety contract",
            "strict input preflight and post-batch final trajectory checks are outside timing",
            "boundary path does not promise to detect every non-finite intermediate",
            "both routes still execute per operation, exactly as in the existing composition wrapper",
            "existing rowwise E-capable kernel; C34 no-E tiled kernels are NOT integrated",
            "prepared device input; no training, transfer, isolated kernel or peak-memory claim",
            "event intervals include host-submission gaps and external GPU contention",
            "single saved composition fixture, not general language ability or Gate C PASS"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--output", help="Optional complete JSON result; overwritten on success")
    args = parser.parse_args(argv)
    _integer(args.threads, "threads", 1)
    torch.set_num_threads(args.threads)
    result = run_benchmark(args.fixture, device=args.device, warmup=args.warmup,
                           rounds=args.rounds, iterations=args.iterations)
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        output = Path(args.output)
        if output.resolve() == Path(args.fixture).resolve():
            raise ValueError("output must not overwrite the fixture")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
