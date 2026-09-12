"""V5-C / C34: bounded IEEE tile comparison with codebooks restored.

C33 measured shared-base-only transforms, not the compressed model. C34 compares
16x16x32 and 32x32x32 on the SAME no-E compressed weights and inputs, using the
existing C28 kernel unchanged. Dense executes the materialized no-E reference.

Finite-input preflight and output parity checks are outside timed batches.
Metadata validation remains inside each diagnostic bank forward. Production
validation, precision, weights and kernels are not changed. CUDA-event intervals
include possible host-submission gaps/interference; they are NOT isolated kernel
durations. Wall time and all raw records are retained. This is not a Gate C pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time

import torch

DEFAULT_WIDTH = 256
DEFAULT_ROWS = (1, 216)
ROLES = ("up", "down")
TILES = {"ieee_16x16x32": (16, 16, 32), "ieee_32x32x32": (32, 32, 32)}
VARIANTS = ("dense", *TILES)
METRICS = ("device_per_forward_ms", "wall_per_forward_ms")


def _integer(value, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def validate_scope(width, row_counts, warmup, rounds, iterations) -> None:
    _integer(width, "width", 1)
    if width % 2:
        raise ValueError("width must be divisible by the existing 2x2 block shape")
    if not row_counts:
        raise ValueError("row_counts must be nonempty")
    for count in row_counts:
        _integer(count, "row count", 1)
    if len(set(row_counts)) != len(row_counts):
        raise ValueError("row_counts must be unique")
    _integer(warmup, "warmup")
    _integer(rounds, "rounds", 1)
    _integer(iterations, "iterations", 1)


def order_for_round(round_index: int) -> tuple[str, ...]:
    _integer(round_index, "round_index")
    offset = round_index % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


def make_diagnostic_bank(initialization, tile_name: str):
    """Reuse the existing IEEE kernel; no global monkey patch or new kernel."""
    if tile_name not in TILES:
        raise ValueError("unknown bounded tile configuration")
    from fold_lm.v05 import triton_tiled_runtime as runtime
    from fold_lm.v05_benchmarks.gate_c_triton_validation_overhead import (
        _StructuralValidationMixin,
    )

    class DiagnosticBank(_StructuralValidationMixin, runtime.TiledNoECompressedLinearBank):
        def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
            self._validate(value, module_index)
            if value.device.type != "cuda":
                raise RuntimeError("C34 requires a CUDA activation")
            if value.dtype != torch.float32:
                raise TypeError("C34 requires float32")
            if any(b.device != value.device for b in (self.base, self.codes, self.codebooks)):
                raise ValueError("bank buffers must match the activation device")
            indices, values = self._correction(module_index)
            if indices.numel() or values.numel():
                raise ValueError("C34 requires no-E weights")
            if value.numel() == 0:
                raise ValueError("empty activations are outside C34 scope")
            flat = value.reshape(-1, self.input_width).contiguous()
            output = torch.empty((flat.shape[0], self.output_width),
                                 device=value.device, dtype=torch.float32)
            bn, bm, bk = self.diagnostic_tile
            grid = (runtime.triton.cdiv(int(flat.shape[0]), bn),
                    runtime.triton.cdiv(self.output_width, bm))
            runtime._compressed_linear_tiled_no_e_kernel[grid](
                flat, self.base, self.codebooks, self.codes, output,
                N=int(flat.shape[0]), M=self.output_width, K=self.input_width,
                GRID_R=self.grid_rows, GRID_C=self.grid_cols,
                BR=self.block_rows, BC=self.block_cols,
                Q=self.codebook_count, ENTRIES=self.entries_per_codebook,
                MODULE_INDEX=module_index, BLOCK_N=bn, BLOCK_M=bm, BLOCK_K=bk,
                num_warps=4,
            )
            return output.reshape(*value.shape[:-1], self.output_width)

    bank = DiagnosticBank(initialization)
    bank.diagnostic_tile = TILES[tile_name]
    return bank


def summarize_records(records: list[dict], *, row_counts: tuple[int, ...],
                      rounds: int, module_count: int) -> dict:
    """Reject missing/duplicate cells instead of silently dropping a module."""
    validate_scope(2, row_counts, 0, rounds, 1)
    _integer(module_count, "module_count", 1)
    if not records:
        raise ValueError("records must be nonempty")
    table = {}
    for record in records:
        count = _integer(record["rows"], "rows", 1)
        module = _integer(record["module_index"], "module_index")
        round_index = _integer(record["round"], "round")
        role, variant = record["role"], record["variant"]
        if (count not in row_counts or role not in ROLES or variant not in VARIANTS
                or module >= module_count or round_index >= rounds):
            raise ValueError("record outside requested scope")
        key = (count, role, module, round_index, variant)
        if key in table:
            raise ValueError("duplicate measurement cell")
        for metric in METRICS:
            number = record[metric]
            if isinstance(number, bool) or not math.isfinite(float(number)) or float(number) <= 0:
                raise ValueError("timings must be finite and positive")
        table[key] = record
    expected = {(n, role, m, r, variant) for n in row_counts for role in ROLES
                for m in range(module_count) for r in range(rounds) for variant in VARIANTS}
    if set(table) != expected:
        raise ValueError("missing requested rows/role/module/round/variant measurements")
    points = {}
    for n in row_counts:
        for role in ROLES:
            pairs = [(m, r) for m in range(module_count) for r in range(rounds)]
            def values(variant, metric):
                return [float(table[n, role, m, r, variant][metric]) for m, r in pairs]
            def ratio(a, b, metric):
                numbers = [x / y for x, y in zip(values(a, metric), values(b, metric))]
                return {"median": statistics.median(numbers), "min": min(numbers),
                        "max": max(numbers)}
            point = {"rows": n, "role": role, "module_count": module_count,
                     "rounds": rounds, "paired_samples": len(pairs), "variants": {},
                     "paired_ratios": {}}
            for variant in VARIANTS:
                point["variants"][variant] = {}
                for label, metric in zip(("device", "wall"), METRICS):
                    numbers = values(variant, metric)
                    point["variants"][variant].update({
                        f"{label}_median_ms": statistics.median(numbers),
                        f"{label}_min_ms": min(numbers), f"{label}_max_ms": max(numbers)})
            for label, metric in zip(("device", "wall"), METRICS):
                for name in TILES:
                    point["paired_ratios"][f"{name}_vs_dense_{label}"] = ratio(name, "dense", metric)
                point["paired_ratios"][f"tile16_to_tile32_speedup_{label}"] = ratio(
                    "ieee_16x16x32", "ieee_32x32x32", metric)
            points[f"r{n}_{role}"] = point
    return {"points": points, "record_count": len(records)}


@torch.inference_mode()
def _measure_batch(fn, iterations: int, events) -> tuple[dict, torch.Tensor]:
    start, end = events
    torch.cuda.synchronize()
    wall_started = time.perf_counter()
    start.record()
    for _ in range(iterations):
        output = fn()
    end.record()
    end.synchronize()
    wall = time.perf_counter() - wall_started
    return {"device_per_forward_ms": float(start.elapsed_time(end)) / iterations,
            "wall_per_forward_ms": 1000.0 * wall / iterations}, output


def _commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


@torch.inference_mode()
def run_benchmark(*, width=DEFAULT_WIDTH, row_counts=DEFAULT_ROWS, device="cuda",
                  warmup=20, rounds=9, iterations=100) -> dict:
    validate_scope(width, row_counts, warmup, rounds, iterations)
    if os.environ.get("CUDA_LAUNCH_BLOCKING") not in (None, "", "0"):
        raise RuntimeError("disable CUDA_LAUNCH_BLOCKING before timing")
    requested = torch.device(device)
    if requested.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("C34 requires CUDA")
    from torch.nn import functional as F
    from fold_lm.v05_benchmarks.gate_c_triton_width_scale import (
        build_synthetic_initialization, role_shape,
    )
    from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction

    started = time.perf_counter()
    seed, module_count = 20260913, 2
    generator = torch.Generator(device="cpu").manual_seed(seed)
    records, gaps, structures, input_hashes = [], {}, {}, {}
    total = len(row_counts) * len(ROLES) * module_count * rounds * len(VARIANTS)
    old_precision = torch.get_float32_matmul_precision()
    torch.set_float32_matmul_precision("highest")
    try:
        with torch.cuda.device(requested):
            for role in ROLES:
                input_width, output_width = role_shape(width, role)
                init = without_correction(build_synthetic_initialization(
                    input_width, output_width, module_count=module_count, seed=seed))
                banks = {name: make_diagnostic_bank(init, name).to(requested).eval() for name in TILES}
                structures[role] = {
                    "input_width": input_width, "output_width": output_width,
                    "module_count": module_count, "correction_nnz": 0,
                    "compact_resident_bytes_per_variant": {
                        name: bank.resident_tensor_bytes for name, bank in banks.items()},
                    "dense_reference_bytes_per_module": input_width * output_width * 4,
                }
                for module, encoded in enumerate(init.encoded_weights):
                    dense_weight = torch.tensor(encoded.materialize().copy(),
                                                dtype=torch.float32, device=requested)
                    for n in row_counts:
                        cpu_value = torch.randn(n, input_width, generator=generator)
                        case = f"r{n}_{role}_m{module}"
                        input_hashes[case] = hashlib.sha256(cpu_value.numpy().tobytes()).hexdigest()
                        value = cpu_value.to(requested)
                        if not bool(torch.isfinite(value).all()):
                            raise ValueError("non-finite preflight input")
                        reference = F.linear(value, dense_weight, None)
                        callables = {"dense": lambda v=value, w=dense_weight: F.linear(v, w, None)}
                        callables.update({name: (lambda b=bank, v=value, mi=module: b(v, module_index=mi))
                                          for name, bank in banks.items()})
                        # Compile and validate each path before measurement; no timing claim here.
                        for name, fn in callables.items():
                            output = fn()
                            torch.testing.assert_close(output, reference, rtol=1e-4, atol=1e-5)
                            gaps[f"{case}:{name}"] = float((output - reference).abs().max().item())
                            for _ in range(warmup):
                                fn()
                        events = (torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True))
                        events[0].record()
                        events[1].record()
                        events[1].synchronize()  # Initialize lazy events outside wall-clock timing.
                        for r in range(rounds):
                            order = order_for_round(r)
                            for name in order:
                                timing, output = _measure_batch(callables[name], iterations, events)
                                # Check after the sample, never inside the timed forward loop.
                                torch.testing.assert_close(output, reference, rtol=1e-4, atol=1e-5)
                                gaps[f"{case}:{name}"] = max(gaps[f"{case}:{name}"],
                                                            float((output-reference).abs().max().item()))
                                records.append({"width": width, "rows": n, "role": role,
                                                "module_index": module, "round": r, "variant": name,
                                                "order": list(order), **timing})
                                elapsed = time.perf_counter() - started
                                eta = elapsed / len(records) * (total-len(records))
                                print(f"[gate-c-compressed-tile-clean] {len(records)}/{total} "
                                      f"{case} round={r+1}/{rounds} variant={name} "
                                      f"device={timing['device_per_forward_ms']:.4f}ms "
                                      f"wall={timing['wall_per_forward_ms']:.4f}ms "
                                      f"elapsed={elapsed:.1f}s eta={eta:.1f}s", file=sys.stderr, flush=True)
    finally:
        torch.set_float32_matmul_precision(old_precision)
    return {
        "schema": "fold-v05-gate-c-compressed-tile-clean-v1", "stage": "V5-C", "experiment_id": "C34",
        "commit_sha": _commit(), "device": str(requested), "device_name": torch.cuda.get_device_name(requested),
        "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda, "seed": seed,
        "width": width, "row_counts": list(row_counts), "warmup": warmup, "rounds": rounds,
        "iterations_per_sample": iterations, "float32_matmul_precision": "highest",
        "kernel_input_precision": "ieee", "tiles": TILES, "structures": structures,
        "max_abs_output_gap_by_case": gaps, "input_hashes": input_hashes,
        "summary": summarize_records(records, row_counts=row_counts, rounds=rounds, module_count=module_count),
        "records": records, "elapsed_seconds": time.perf_counter()-started,
        "diagnostic_only": True, "gate_c_candidate": False, "production_runtime_modified": False,
        "validation_policy": "finite preflight/output checks outside timing; metadata checks inside",
        "known_deviations": ["synthetic no-E Linear, not task quality or full-model inference",
                             "event intervals include possible submission gaps and external contention",
                             "resident bytes describe each bank only; total peak RAM/VRAM not measured",
                             "no new serialized-size or training result"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--rows", type=int, nargs="+", default=list(DEFAULT_ROWS))
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(width=args.width, row_counts=tuple(args.rows), device=args.device,
                           warmup=args.warmup, rounds=args.rounds, iterations=args.iterations)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
