"""C89: diagnose where adaptive sparse execution crosses over in runtime.

C88 was a valid negative result at Composition width=32: despite 50% logical
compute reduction, the learned eager sparse path was slower than fixed-max.
C89 keeps the same 0/1/2-step distribution and scales width while separating:

1. fixed-max two-step execution;
2. oracle sparse execution without controller cost;
3. production-controller cost plus oracle sparse execution.

The third path deliberately uses oracle actions for execution after paying the
controller forward/argmax cost.  This isolates runtime crossover from routing
quality; C87 already established routing quality at the tiny task shape.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

import torch

from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    BATCH,
    MAX_RUNTIME_RATIO,
    WIDTHS,
    measure_width,
)

EXPERIMENT_ID = "C89-v5d-sparse-runtime-width-crossover"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _first_crossover(records: list[dict], prefix: str):
    for row in records:
        device_ratio = float(row[f"{prefix}_over_fixed_device"]["median"])
        wall_ratio = float(row[f"{prefix}_over_fixed_wall"]["median"])
        if device_ratio <= MAX_RUNTIME_RATIO and wall_ratio <= MAX_RUNTIME_RATIO:
            return int(row["width"])
    return None


def run(*, protected_result_path: Path, c88_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C89 requires CUDA")
    c88 = json.loads(c88_summary_path.read_text(encoding="utf-8"))
    if c88.get("experiment_id") != "C88-v5d-composition-learned-sparse-wallclock-runtime":
        raise RuntimeError("C89 requires C88 summary")
    if c88.get("status") != "PASS":
        raise RuntimeError("C89 requires valid C88 execution")
    if bool(c88.get("summary", {}).get("learned_sparse_wallclock_gate_passed")):
        raise RuntimeError("C89 crossover diagnosis expects the C88 runtime gate to have failed")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for index, width in enumerate(WIDTHS, start=1):
        gc.collect()
        torch.cuda.empty_cache()
        row = measure_width(width, device)
        records.append(row)
        print(
            f"[C89] width={width} ({index}/{len(WIDTHS)}) "
            f"oracle_device={row['oracle_sparse_over_fixed_device']['median']:.4f} "
            f"router_device={row['router_plus_sparse_over_fixed_device']['median']:.4f} "
            f"oracle_wall={row['oracle_sparse_over_fixed_wall']['median']:.4f} "
            f"router_wall={row['router_plus_sparse_over_fixed_wall']['median']:.4f} "
            f"router/core_bytes={row['router_over_core_persistent_ratio']:.4f}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C89")

    oracle_crossover = _first_crossover(records, "oracle_sparse")
    router_crossover = _first_crossover(records, "router_plus_sparse")
    summary = {
        "widths": list(WIDTHS),
        "batch": BATCH,
        "logical_compute_reduction_vs_fixed_max": 0.5,
        "runtime_ratio_threshold": MAX_RUNTIME_RATIO,
        "all_outputs_allclose": all(
            bool(row["oracle_output_allclose"])
            and bool(row["router_plus_sparse_output_allclose"])
            for row in records
        ),
        "oracle_sparse_crossover_width": oracle_crossover,
        "router_inclusive_crossover_width": router_crossover,
        "oracle_sparse_crossover_found": oracle_crossover is not None,
        "router_inclusive_crossover_found": router_crossover is not None,
        "records": records,
        "c88_actual_device_ratio_mean": float(
            c88["summary"]["adaptive_over_fixed_device_latency"]["mean"]
        ),
        "c88_actual_wall_ratio_mean": float(
            c88["summary"]["adaptive_over_fixed_wall_latency"]["mean"]
        ),
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "width crossover diagnosis after valid C88 negative runtime result",
        "summary": summary,
        "C88_summary_sha256": _sha256(c88_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C89 uses synthetic runtime states rather than retraining Composition at every width",
            "router-inclusive timing pays the production controller cost but uses oracle actions for execution",
            "C89 keeps one balanced batch size of 216 to match the C88 runtime regime",
            "current sparse execution remains eager nonzero/index_select/index_copy rather than a fused kernel",
            "C89 diagnoses runtime crossover and does not by itself establish Gate D passage",
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
    parser.add_argument("--c88-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c88_summary_path=args.c88_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["summary"] = dict(result["summary"])
    display["summary"]["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C89 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
