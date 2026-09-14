"""Tracked execution driver for C118."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as bench

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


def _latest_c117() -> Path:
    candidates = [p for p in RUNS.glob("c117-v5e-post-preflight-fallback-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C117 summary not found")
    valid = []
    for p in candidates:
        try:
            data = json.loads((p / "summary.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("experiment_id") == "C117-v5e-post-preflight-execution-failure-fallback" and data.get("status") == "PASS":
            valid.append(p)
    if not valid:
        raise RuntimeError("valid C117 summary not found")
    return max(valid, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C118 V5-E falsification: unknown-effect containment ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-RUNTIME-OUTCOME-FALSIFICATION")
    print("task = contain ambiguous non-idempotent outcome after authoritative preflight")
    print("fresh_seeds = 20261381,20261382,20261383")
    print("runtime_rule = UNKNOWN_EFFECT -> no evidence commit, no retry, no automatic fallback")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    if _capture("git", "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Tracked working tree is not clean")

    if _sha(C37) != EXPECTED_C37 or _sha(FIXTURE) != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C118")

    prior = _latest_c117()
    out = RUNS / f"c118-v5e-unknown-effect-{time.time_ns()}"
    print("=== import preflight ===")
    print("C118 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out}")
    print(f"C37_result_sha256_before = {_sha(C37)}")
    print(f"fixture_sha256_before = {_sha(FIXTURE)}")
    print("=== C118 benchmark ===")

    report = bench.run(protected_result_path=C37, c117_summary_path=prior, output_dir=out)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C118 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    s = report["summary"]
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    print("\n=== C118 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"unknown_effect_containment_gate_passed = {s['unknown_effect_containment_gate_passed']}")
    print(f"mask_pair_count = {s['mask_pair_count']}")
    print(f"scenario_count = {s['scenario_count']}")
    print(f"unknown_effect_case_count = {s['unknown_effect_case_count']}")
    print(f"success_control_answer_rate_min = {s['success_control_answer_rate']['min']}")
    print(f"unknown_effect_containment_rate_min = {s['unknown_effect_containment_rate']['min']}")
    print(f"unknown_effect_zero_commit_rate_min = {s['unknown_effect_zero_commit_rate']['min']}")
    print(f"unknown_effect_zero_retry_rate_min = {s['unknown_effect_zero_retry_rate']['min']}")
    print(f"unknown_effect_zero_fallback_execution_rate_min = {s['unknown_effect_zero_fallback_execution_rate']['min']}")
    print(f"hidden_trace_invariance_min = {s['hidden_action_trace_invariance']['min']}")
    print(f"C37_preserved = {_sha(C37) == EXPECTED_C37}")
    print(f"fixture_preserved = {_sha(FIXTURE) == EXPECTED_FIXTURE}")
    print(f"repository_tracked_clean = {not bool(dirty)}")
    print(f"output_directory = {out}")
    print("production_runtime_modified = False")
    print("gate_e_candidate = False")
    print("\n=== script error, if any ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
