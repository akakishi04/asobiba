"""Tracked execution driver for C116."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as bench

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


def _latest_c115() -> Path:
    candidates = [p for p in RUNS.glob("c115-v5e-stale-low-refresh-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C115 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C116 V5-E falsification: authoritative priority refresh ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-RUNTIME-AUTHORITY-FALSIFICATION")
    print("task = refresh authoritative availability before external execution or terminal stop")
    print("fresh_seeds = 20261361,20261362,20261363")
    print("runtime_rule = if refresh reveals a lower-burden mechanism, suppress current proposal and reobserve")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C116")

    c115_summary = _latest_c115()
    out_dir = RUNS / f"c116-v5e-priority-refresh-{time.time_ns()}"
    print("=== import preflight ===")
    print("C116 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C116 benchmark ===")

    report = bench.run(protected_result_path=C37, c115_summary_path=c115_summary, output_dir=out_dir)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C116 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C116 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"authoritative_preflight_priority_refresh_gate_passed = {s['authoritative_preflight_priority_refresh_gate_passed']}")
    print(f"mask_pair_count = {s['mask_pair_count']}")
    print(f"required_case_count = {s['required_case_count']}")
    print(f"priority_upgrade_case_count = {s['priority_upgrade_case_count']}")
    print(f"terminal_recovery_case_count = {s['terminal_recovery_case_count']}")
    print(f"required_scenario_pass_rate_min = {s['required_scenario_pass_rate']['min']}")
    print(f"priority_upgrade_recovery_rate_min = {s['priority_upgrade_recovery_rate']['min']}")
    print(f"priority_upgrade_suppression_exact_rate_min = {s['priority_upgrade_suppression_exact_rate']['min']}")
    print(f"terminal_recovery_rate_min = {s['terminal_recovery_rate']['min']}")
    print(f"confirmed_unavailable_stop_rate_min = {s['confirmed_unavailable_stop_rate']['min']}")
    print(f"priority_violation_count_sum = {s['priority_violation_count']['sum']}")
    print(f"premature_stop_accept_count_sum = {s['premature_stop_accept_count']['sum']}")
    print(f"hidden_trace_invariance_min = {s['hidden_action_trace_invariance']['min']}")
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
