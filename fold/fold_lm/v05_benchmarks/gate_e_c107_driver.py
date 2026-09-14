"""Tracked execution driver for C107 independent-evaluator falsification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c107_independent_generator_falsification as bench

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


def _latest_c106() -> Path:
    candidates = [p for p in RUNS.glob("c106-v5e-unseen-mask-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C106 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C107 V5-E falsification: independent evaluator ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-FALSIFICATION")
    print("task = independent train/eval generator cross-check")
    print("training_generator = C106 canonical family")
    print("evaluation_generator = C107 independent fixture")
    print("fresh_seeds = 20261301,20261302,20261303")
    print("validation_base = 3 (unseen)")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C107")

    c106_summary = _latest_c106()
    out_dir = RUNS / f"c107-v5e-independent-eval-{time.time_ns()}"
    print("=== import preflight ===")
    print("C107 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C107 benchmark ===")

    report = bench.run(protected_result_path=C37, c106_summary_path=c106_summary, output_dir=out_dir)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C107 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C107 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"independent_evaluator_falsification_gate_passed = {s['independent_evaluator_falsification_gate_passed']}")
    print(f"label_agreement = {s['independent_vs_canonical_label_agreement_rate']}")
    print(f"key_coverage_complete = {s['independent_vs_canonical_key_coverage_complete']}")
    print(f"independent_action_accuracy_min = {s['independent_action_accuracy']['min']}")
    print(f"independent_minimum_class_recall_min = {s['independent_minimum_class_recall']['min']}")
    print(f"independent_minimum_burden_rate_min = {s['independent_minimum_burden_rate']['min']}")
    print(f"independent_ineligible_count_sum = {s['independent_ineligible_mechanism_count']['sum']}")
    print(f"independent_action_flip_count_sum = {s['independent_action_flip_count']['sum']}")
    print(f"independent_hidden_invariance_min = {s['independent_hidden_counterfactual_action_invariance']['min']}")
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
