"""Tracked execution driver for C114 production hot-path profiling."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c114_control_hot_path_profile as bench

REPO = Path(r"M:\asobiba\fold")
RUNS = REPO / "runs"
C37 = RUNS / "chatgpt-last-result.json"
FIXTURE = RUNS / "fixtures" / "v05-c-composition-20260921.pt"
EXPECTED_C37 = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
EXPECTED_FIXTURE = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
BRANCH = "feat/sft-target-loss"


def _run(*args: str) -> str:
    result = subprocess.run(args, cwd=REPO, check=True, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    return result.stdout.strip()


def _capture(*args: str) -> str:
    return subprocess.run(args, cwd=REPO, check=True, text=True, capture_output=True).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _latest_c113() -> Path:
    candidates = [p for p in RUNS.glob("c113-v5e-stale-preflight-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C113 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C114 V5-E performance diagnostic: production control hot path ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-PERFORMANCE-DIAGNOSTIC")
    print("task = profile router-only vs adapter-only vs production adapter+router")
    print("widths = 8,5120")
    print("batch = 1")
    print("slots = 1")
    print("separate_cuda_process_per_condition = true")
    print("no_post_hoc_performance_threshold = true")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C114")

    c113_summary = _latest_c113()
    out_dir = RUNS / f"c114-v5e-control-hot-path-{time.time_ns()}"
    print("=== import preflight ===")
    print("C114 import OK:", bench.EXPERIMENT_ID, bench.WIDTHS, bench.PATHS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C114 benchmark ===")

    report = bench.run(protected_result_path=C37, c113_summary_path=c113_summary, output_dir=out_dir)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C114 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C114 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"performance_characterization_completed = {s['performance_characterization_completed']}")
    print(f"functional_equivalence_all_conditions = {s['functional_equivalence_all_conditions']}")
    print(f"router_parameter_count_width_independent = {s['router_parameter_count_width_independent']}")
    print(f"production_wall_width5120_over_width8 = {s['production_wall_width5120_over_width8']}")
    print(f"production_device_width5120_over_width8 = {s['production_device_width5120_over_width8']}")
    print(f"adapter_wall_width5120_over_width8 = {s['adapter_wall_width5120_over_width8']}")
    print(f"adapter_device_width5120_over_width8 = {s['adapter_device_width5120_over_width8']}")
    print(f"width5120_production_over_router_wall = {s['width5120_production_over_router_wall']}")
    print(f"width5120_production_over_router_device = {s['width5120_production_over_router_device']}")
    print(f"width5120_extra_warmup_operational_vram_bytes = {s['width5120_extra_warmup_operational_vram_bytes']}")
    print(f"C37_preserved = {c37_after == EXPECTED_C37}")
    print(f"fixture_preserved = {fixture_after == EXPECTED_FIXTURE}")
    print(f"repository_tracked_clean = {not bool(dirty_after)}")
    print(f"output_directory = {out_dir}")
    print("production_runtime_modified = False")
    print("gate_e_candidate = False")
    print("\n=== script error, if any ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
