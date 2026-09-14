"""Tracked execution driver for C112."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c112_natural_class_frequency_falsification as bench

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


def _latest_c111() -> Path:
    candidates = [p for p in RUNS.glob("c111-v5e-production-canonicalization-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C111 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C112 V5-E falsification: natural class frequency ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-FALSIFICATION")
    print("task = remove class-balanced training from six-action selector")
    print("sampling = uniform training-row sampling with replacement")
    print("fresh_seeds = 20261331,20261332,20261333")
    print("train_bases = 0,1,2")
    print("validation_base = 3 (unseen)")
    print("production_adapter = canonicalize_boolean_channels")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C112")

    c111_summary = _latest_c111()
    out_dir = RUNS / f"c112-v5e-natural-frequency-{time.time_ns()}"
    print("=== import preflight ===")
    print("C112 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C112 benchmark ===")

    report = bench.run(protected_result_path=C37, c111_summary_path=c111_summary, output_dir=out_dir)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C112 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C112 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"natural_class_frequency_falsification_gate_passed = {s['natural_class_frequency_falsification_gate_passed']}")
    print(f"class_balanced_training = {s['class_balanced_training']}")
    print(f"natural_training_class_fractions = {s['natural_training_class_fractions']}")
    print(f"anchor_action_accuracy_min = {s['anchor_action_accuracy']['min']}")
    print(f"anchor_minimum_class_recall_min = {s['anchor_minimum_class_recall']['min']}")
    print(f"ood_action_accuracy_min = {s['ood_action_accuracy']['min']}")
    print(f"ood_minimum_class_recall_min = {s['ood_minimum_class_recall']['min']}")
    print(f"ood_minimum_burden_rate_min = {s['ood_minimum_burden_rate']['min']}")
    print(f"ood_ineligible_mechanism_count_sum = {s['ood_ineligible_mechanism_count']['sum']}")
    print(f"ood_action_flip_count_sum = {s['ood_action_flip_count']['sum']}")
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
