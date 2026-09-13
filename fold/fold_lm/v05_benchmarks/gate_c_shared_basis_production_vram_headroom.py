"""C83: fresh-process production VRAM/headroom gate.

The primary product goal is to leave more GPU memory available to other
applications.  Each Dense/Shared point therefore runs in a fresh Python process.
The child records CUDA allocator state and cudaMemGetInfo before model creation,
after model residency, after warmup/inference readiness, and at inference peak.

Primary metric:

    incremental device VRAM consumed
      = free VRAM after CUDA context init - free VRAM when inference-ready

The comparison is baseline-referenced inside each child so CUDA context cost is
not charged to either architecture.
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

from fold_lm.v05_benchmarks.gate_c_shared_basis_c83_vram_helpers import (
    BATCHES,
    GIB,
    PROFILES,
    WIDTH,
)

EXPERIMENT_ID = "C83-shared-basis-production-vram-headroom"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
REPEATS = 3
MIN_HEADROOM_GAIN_GIB = 0.15


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _median(rows: list[dict], key: str) -> float:
    return float(statistics.median(float(row[key]) for row in rows))


def _run_child(*, variant: str, profile: str, batch: int, repeat: int, work: Path) -> dict:
    output = work / f"{variant}-{profile}-b{batch}-r{repeat}.json"
    command = [
        sys.executable,
        "-m",
        "fold_lm.v05_benchmarks.gate_c_shared_basis_c83_vram_helpers",
        "--variant",
        variant,
        "--profile",
        profile,
        "--batch",
        str(batch),
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"C83 child failed variant={variant} profile={profile} batch={batch} "
            f"repeat={repeat}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    row = json.loads(output.read_text(encoding="utf-8"))
    output.unlink(missing_ok=True)
    row["repeat"] = repeat
    return row


def run(*, protected_result_path: Path, c82_summary_path: Path, output_dir: Path) -> dict:
    c82 = json.loads(c82_summary_path.read_text(encoding="utf-8"))
    if c82.get("experiment_id") != "C82-shared-basis-production-serialized-artifact":
        raise RuntimeError("C83 requires accepted C82 summary")
    if c82.get("status") != "PASS" or not bool(
        c82.get("summary", {}).get("production_serialized_artifact_gate_passed")
    ):
        raise RuntimeError("C82 prerequisite is not accepted")

    protected_before = _sha256(protected_result_path)
    output_dir.mkdir(parents=True, exist_ok=False)
    work = output_dir / "child-temp"
    work.mkdir()

    records: list[dict] = []
    total = len(BATCHES) * REPEATS * (1 + len(PROFILES))
    completed_count = 0

    for batch in BATCHES:
        for repeat in range(1, REPEATS + 1):
            row = _run_child(
                variant="dense", profile="lean", batch=batch, repeat=repeat, work=work
            )
            records.append(row)
            completed_count += 1
            print(
                f"[C83] dense batch={batch} repeat={repeat} "
                f"ready={row['ready_device_vram_consumed_bytes']/GIB:.3f}GiB "
                f"({completed_count}/{total})",
                flush=True,
            )
        for profile in PROFILES:
            for repeat in range(1, REPEATS + 1):
                row = _run_child(
                    variant="shared", profile=profile, batch=batch, repeat=repeat, work=work
                )
                records.append(row)
                completed_count += 1
                print(
                    f"[C83] shared profile={profile} batch={batch} repeat={repeat} "
                    f"ready={row['ready_device_vram_consumed_bytes']/GIB:.3f}GiB "
                    f"({completed_count}/{total})",
                    flush=True,
                )

    work.rmdir()
    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C83")

    comparisons = []
    for batch in BATCHES:
        dense_rows = [
            row for row in records if row["variant"] == "dense" and int(row["batch"]) == batch
        ]
        dense_ready = _median(dense_rows, "ready_device_vram_consumed_bytes")
        dense_peak_alloc = _median(dense_rows, "peak_allocated_delta_from_baseline_bytes")
        dense_peak_reserved = _median(dense_rows, "peak_reserved_delta_from_baseline_bytes")
        dense_free = _median(dense_rows, "ready_device_free_bytes")
        for profile in PROFILES:
            shared_rows = [
                row
                for row in records
                if row["variant"] == "shared"
                and row["profile"] == profile
                and int(row["batch"]) == batch
            ]
            shared_ready = _median(shared_rows, "ready_device_vram_consumed_bytes")
            shared_peak_alloc = _median(
                shared_rows, "peak_allocated_delta_from_baseline_bytes"
            )
            shared_peak_reserved = _median(
                shared_rows, "peak_reserved_delta_from_baseline_bytes"
            )
            shared_free = _median(shared_rows, "ready_device_free_bytes")
            gain = dense_ready - shared_ready
            comparisons.append(
                {
                    "profile": profile,
                    "batch": batch,
                    "dense_ready_vram_consumed_bytes": dense_ready,
                    "shared_ready_vram_consumed_bytes": shared_ready,
                    "headroom_gain_bytes": gain,
                    "headroom_gain_gib": gain / GIB,
                    "dense_peak_allocated_delta_bytes": dense_peak_alloc,
                    "shared_peak_allocated_delta_bytes": shared_peak_alloc,
                    "dense_peak_reserved_delta_bytes": dense_peak_reserved,
                    "shared_peak_reserved_delta_bytes": shared_peak_reserved,
                    "dense_ready_device_free_bytes_median": dense_free,
                    "shared_ready_device_free_bytes_median": shared_free,
                }
            )

    all_finite = all(bool(row["output_finite"]) for row in records)
    all_headroom = all(row["headroom_gain_gib"] >= MIN_HEADROOM_GAIN_GIB for row in comparisons)
    all_peak_alloc = all(
        row["shared_peak_allocated_delta_bytes"] < row["dense_peak_allocated_delta_bytes"]
        for row in comparisons
    )
    all_peak_reserved = all(
        row["shared_peak_reserved_delta_bytes"] < row["dense_peak_reserved_delta_bytes"]
        for row in comparisons
    )
    summary = {
        "width": WIDTH,
        "batches": list(BATCHES),
        "profiles": {name: list(value) for name, value in PROFILES.items()},
        "fresh_process_repeats": REPEATS,
        "primary_metric": "baseline_free_vram_minus_inference_ready_free_vram",
        "minimum_headroom_gain_gib": MIN_HEADROOM_GAIN_GIB,
        "all_outputs_finite": all_finite,
        "all_shared_headroom_gains_meet_minimum": all_headroom,
        "all_shared_peak_allocated_below_dense": all_peak_alloc,
        "all_shared_peak_reserved_below_dense": all_peak_reserved,
        "comparisons": comparisons,
        "production_vram_headroom_gate_passed": (
            all_finite and all_headroom and all_peak_alloc and all_peak_reserved
        ),
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "fresh-process production VRAM/headroom priority gate",
        "records": records,
        "summary": summary,
        "C82_summary_sha256": _sha256(c82_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "default_dense_runtime_changed": False,
        "gate_c_candidate": False,
        "limitations": [
            "single RTX 4070 Ti SUPER / Windows CUDA environment",
            "cudaMemGetInfo can vary with unrelated GPU activity; three fresh-process repeats use medians",
            "C83 measures incremental VRAM after CUDA context initialization, not total system GPU usage",
            "C83 is a VRAM/headroom gate, not a fresh quality experiment",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c82-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c82_summary_path=args.c82_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C83 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
