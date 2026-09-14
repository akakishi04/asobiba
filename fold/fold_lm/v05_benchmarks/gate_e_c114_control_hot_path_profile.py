"""C114: profile the production Control Representation Adapter hot path.

This is a performance characterization, not a Gate-E passage claim.  Each
(path,width) condition runs in a fresh CUDA process so allocator state from one
condition cannot contaminate another.  Primary online profile is batch=1,
slots=1, comparing width 8 and the registered large width 5120.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import torch

from fold_lm.v05.controller import (
    ControlLaneActionRouter,
    ControlLaneRouterConfig,
    canonicalize_boolean_channels,
)

EXPERIMENT_ID = "C114-v5e-production-control-hot-path-profile"
C113_EXPERIMENT_ID = "C113-v5e-stale-eligibility-preflight"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
WIDTHS = (8, 5120)
PATHS = ("router_only", "adapter_only", "production")
BATCH = 1
SLOTS = 1
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 8
ACTION_COUNT = 6
WARMUP = 200
ITERATIONS = 2000
SAMPLES = 5


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _inputs(width: int, device):
    raw_w = torch.zeros(BATCH, SLOTS, width, device=device)
    raw_c = torch.zeros_like(raw_w)
    raw_w[..., 0] = 1.0
    raw_w[..., 1] = 4.0
    raw_w[..., 2] = -0.1
    raw_w[..., 3] = -0.1
    raw_c[..., 0] = 4.0
    raw_c[..., 1] = -0.1
    raw_c[..., 2] = 4.0
    raw_c[..., 3] = -0.1
    can_w = canonicalize_boolean_channels(raw_w, (1, 2, 3), threshold=0.0)
    can_c = canonicalize_boolean_channels(raw_c, (0, 1, 2, 3), threshold=0.0)
    op = torch.zeros(BATCH, dtype=torch.int64, device=device)
    return raw_w, raw_c, can_w, can_c, op


def _child(path_name: str, width: int):
    if not torch.cuda.is_available():
        raise RuntimeError("C114 requires CUDA")
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    torch.manual_seed(20261414 + width)

    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=width,
            control_width=CONTROL_WIDTH,
            operation_vocab_size=1,
            hidden_width=HIDDEN_WIDTH,
            action_count=ACTION_COUNT,
        )
    ).to(device).eval()
    raw_w, raw_c, can_w, can_c, op = _inputs(width, device)

    @torch.inference_mode()
    def step():
        if path_name == "router_only":
            return router(can_w, can_c, op)
        if path_name == "adapter_only":
            w = canonicalize_boolean_channels(raw_w, (1, 2, 3), threshold=0.0)
            c = canonicalize_boolean_channels(raw_c, (0, 1, 2, 3), threshold=0.0)
            return w, c
        if path_name == "production":
            w = canonicalize_boolean_channels(raw_w, (1, 2, 3), threshold=0.0)
            c = canonicalize_boolean_channels(raw_c, (0, 1, 2, 3), threshold=0.0)
            return router(w, c, op)
        raise ValueError(path_name)

    # Functional equivalence for the complete production path.
    with torch.inference_mode():
        baseline_logits = router(can_w, can_c, op)
        w = canonicalize_boolean_channels(raw_w, (1, 2, 3), threshold=0.0)
        c = canonicalize_boolean_channels(raw_c, (0, 1, 2, 3), threshold=0.0)
        production_logits = router(w, c, op)
    functional_equal = bool(torch.equal(baseline_logits, production_logits))

    torch.cuda.synchronize()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    free_before, total = torch.cuda.mem_get_info()
    allocated_before = torch.cuda.memory_allocated()
    reserved_before = torch.cuda.memory_reserved()

    for _ in range(WARMUP):
        step()
    torch.cuda.synchronize()
    free_after_warmup, _ = torch.cuda.mem_get_info()

    wall_samples = []
    device_samples = []
    for _ in range(SAMPLES):
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)
        torch.cuda.synchronize()
        wall_start = time.perf_counter()
        start_event.record()
        for _ in range(ITERATIONS):
            step()
        end_event.record()
        torch.cuda.synchronize()
        wall_elapsed = time.perf_counter() - wall_start
        device_ms = start_event.elapsed_time(end_event)
        wall_samples.append(wall_elapsed * 1e6 / ITERATIONS)
        device_samples.append(device_ms * 1000.0 / ITERATIONS)

    torch.cuda.reset_peak_memory_stats()
    allocated_pre_peak = torch.cuda.memory_allocated()
    reserved_pre_peak = torch.cuda.memory_reserved()
    step()
    torch.cuda.synchronize()
    peak_allocated_delta = torch.cuda.max_memory_allocated() - allocated_pre_peak
    peak_reserved_delta = max(0, torch.cuda.max_memory_reserved() - reserved_pre_peak)
    free_after, _ = torch.cuda.mem_get_info()

    return {
        "path": path_name,
        "width": width,
        "batch": BATCH,
        "slots": SLOTS,
        "functional_equal": functional_equal,
        "router_parameter_count": sum(p.numel() for p in router.parameters()),
        "wall_us_per_decision": _stats(wall_samples),
        "device_us_per_decision": _stats(device_samples),
        "free_vram_before_bytes": free_before,
        "free_vram_after_warmup_bytes": free_after_warmup,
        "free_vram_after_bytes": free_after,
        "warmup_operational_free_vram_consumed_bytes": max(0, free_before - free_after_warmup),
        "post_profile_free_vram_consumed_bytes": max(0, free_before - free_after),
        "allocated_before_bytes": allocated_before,
        "reserved_before_bytes": reserved_before,
        "single_decision_peak_allocated_delta_bytes": peak_allocated_delta,
        "single_decision_peak_reserved_delta_bytes": peak_reserved_delta,
    }


def _run_child(path_name: str, width: int):
    cmd = [
        sys.executable,
        "-m",
        "fold_lm.v05_benchmarks.gate_e_c114_control_hot_path_profile",
        "--child",
        "--path-name",
        path_name,
        "--width",
        str(width),
    ]
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("C114_CHILD_JSON=")]
    if len(lines) != 1:
        raise RuntimeError(f"C114 child output malformed: {proc.stdout}\n{proc.stderr}")
    return json.loads(lines[0].split("=", 1)[1])


def run(*, protected_result_path: Path, c113_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c113_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C113_EXPERIMENT_ID:
        raise RuntimeError("C114 requires C113 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "stale_eligibility_preflight_gate_passed"
    ):
        raise RuntimeError("C114 requires accepted C113")

    before = _sha(protected_result_path)
    records = []
    for width in WIDTHS:
        for path_name in PATHS:
            row = _run_child(path_name, width)
            records.append(row)
            print(
                f"[C114] width={width} path={path_name} "
                f"wall_us={row['wall_us_per_decision']['median']:.6f} "
                f"device_us={row['device_us_per_decision']['median']:.6f} "
                f"warmup_vram_kib={row['warmup_operational_free_vram_consumed_bytes']/1024:.1f}",
                flush=True,
            )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C114")

    by = {(r["width"], r["path"]): r for r in records}
    w8 = by[(8, "production")]
    w5120 = by[(5120, "production")]
    r5120 = by[(5120, "router_only")]
    a8 = by[(8, "adapter_only")]
    a5120 = by[(5120, "adapter_only")]

    summary = {
        "widths": list(WIDTHS),
        "paths": list(PATHS),
        "batch": BATCH,
        "slots": SLOTS,
        "warmup": WARMUP,
        "iterations_per_sample": ITERATIONS,
        "samples": SAMPLES,
        "functional_equivalence_all_conditions": all(r["functional_equal"] for r in records),
        "router_parameter_count_width8": by[(8, "router_only")]["router_parameter_count"],
        "router_parameter_count_width5120": r5120["router_parameter_count"],
        "router_parameter_count_width_independent": by[(8, "router_only")]["router_parameter_count"] == r5120["router_parameter_count"],
        "production_wall_width5120_over_width8": w5120["wall_us_per_decision"]["median"] / w8["wall_us_per_decision"]["median"],
        "production_device_width5120_over_width8": w5120["device_us_per_decision"]["median"] / w8["device_us_per_decision"]["median"],
        "adapter_wall_width5120_over_width8": a5120["wall_us_per_decision"]["median"] / a8["wall_us_per_decision"]["median"],
        "adapter_device_width5120_over_width8": a5120["device_us_per_decision"]["median"] / a8["device_us_per_decision"]["median"],
        "width5120_production_over_router_wall": w5120["wall_us_per_decision"]["median"] / r5120["wall_us_per_decision"]["median"],
        "width5120_production_over_router_device": w5120["device_us_per_decision"]["median"] / r5120["device_us_per_decision"]["median"],
        "width5120_extra_warmup_operational_vram_bytes": max(0, w5120["warmup_operational_free_vram_consumed_bytes"] - r5120["warmup_operational_free_vram_consumed_bytes"]),
        "performance_characterization_completed": True,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-PERFORMANCE-DIAGNOSTIC",
        "status": "PASS",
        "status_meaning": "production Control Representation Adapter hot-path performance characterization",
        "summary": summary,
        "records": records,
        "C113_summary_sha256": _sha(c113_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C114 profiles batch=1, slots=1 only",
            "C114 uses synthetic resident CUDA tensors and does not include host-to-device transfer",
            "allocator free-VRAM deltas are process-local operational measurements",
            "C114 is a characterization; no post-hoc performance pass threshold is applied",
            "C114 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--path-name", choices=PATHS)
    parser.add_argument("--width", type=int, choices=WIDTHS)
    args = parser.parse_args(argv)
    if args.child:
        result = _child(args.path_name, args.width)
        print("C114_CHILD_JSON=" + json.dumps(result, separators=(",", ":"), allow_nan=False))
        return 0
    raise RuntimeError("C114 parent execution is driven by gate_e_c114_driver")


if __name__ == "__main__":
    raise SystemExit(main())
