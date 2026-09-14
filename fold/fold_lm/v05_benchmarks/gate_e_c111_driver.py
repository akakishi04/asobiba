"""Tracked execution driver for C111 production canonicalization integration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c111_production_control_canonicalization as bench

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


def _latest_c110() -> Path:
    candidates = [p for p in RUNS.glob("c110-v5e-sign-canonicalization-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C110 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C111 V5-E production control canonicalization integration ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-REPRESENTATION-INTEGRATION")
    print("task = production schema-aware boolean Control-Lane canonicalization")
    print("known_regression_seed = 20261311")
    print("fresh_seeds = 20261321,20261322,20261323")
    print("signed_threshold = 0.0")
    print("canonical_false_true = -1,+1")
    print("router_architecture_changed = false")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C111")

    c110_summary = _latest_c110()
    out_dir = RUNS / f"c111-v5e-production-canonicalization-{time.time_ns()}"
    print("=== import preflight ===")
    print("C111 import OK:", bench.EXPERIMENT_ID, bench.ALL_SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C111 benchmark ===")

    report = bench.run(
        protected_result_path=C37,
        c110_summary_path=c110_summary,
        output_dir=out_dir,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C111 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C111 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"production_control_canonicalization_gate_passed = {s['production_control_canonicalization_gate_passed']}")
    print(f"adapter_contract_smoke_passed = {s['adapter_contract_smoke_passed']}")
    print(f"known_c108_failure_recovered = {s['known_c108_failure_recovered']}")
    print(f"fresh_seed_validation_all_passed = {s['fresh_seed_validation_all_passed']}")
    print(f"anchor_action_accuracy_min = {s['anchor_action_accuracy']['min']}")
    print(f"anchor_minimum_class_recall_min = {s['anchor_minimum_class_recall']['min']}")
    print(f"ood_action_accuracy_min = {s['ood_action_accuracy']['min']}")
    print(f"ood_minimum_class_recall_min = {s['ood_minimum_class_recall']['min']}")
    print(f"ood_ineligible_mechanism_count_sum = {s['ood_ineligible_mechanism_count']['sum']}")
    print(f"ood_action_flip_count_sum = {s['ood_action_flip_count']['sum']}")
    print(f"C37_preserved = {c37_after == EXPECTED_C37}")
    print(f"fixture_preserved = {fixture_after == EXPECTED_FIXTURE}")
    print(f"repository_tracked_clean = {not bool(dirty_after)}")
    print(f"output_directory = {out_dir}")
    print("production_runtime_modified = True")
    print("gate_e_candidate = False")
    print("\n=== script error, if any ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
