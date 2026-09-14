"""Tracked execution driver for C110."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c110_signed_control_canonicalization_diagnostic as bench

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


def _latest_c109() -> Path:
    candidates = [p for p in RUNS.glob("c109-v5e-reencoding-localization-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C109 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C110 V5-E diagnostic: signed control canonicalization ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-FALSIFICATION-DIAGNOSTIC")
    print("task = paired raw-vs-sign-canonicalized C108 replay")
    print("adapter = schema-known signed boolean -> sign(value) in {-1,+1}")
    print("replay_seeds = 20261311,20261312,20261313")
    print("architecture_training_optimizer_codebooks_changed = false")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C110")

    c109_summary = _latest_c109()
    out_dir = RUNS / f"c110-v5e-sign-canonicalization-{time.time_ns()}"
    print("=== import preflight ===")
    print("C110 import OK:", bench.EXPERIMENT_ID, bench.REPLAY_SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C110 benchmark ===")

    report = bench.run(protected_result_path=C37, c109_summary_path=c109_summary, output_dir=out_dir)
    shown = dict(report)
    shown["raw_records"] = "omitted; see summary.json"
    shown["canonical_records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C110 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C110 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"signed_control_canonicalization_diagnostic_gate_passed = {s['signed_control_canonicalization_diagnostic_gate_passed']}")
    print(f"raw_c108_negative_reproduced = {s['raw_c108_negative_reproduced']}")
    print(f"canonical_anchor_action_accuracy_min = {s['canonical_anchor_action_accuracy']['min']}")
    print(f"canonical_anchor_minimum_class_recall_min = {s['canonical_anchor_minimum_class_recall']['min']}")
    print(f"canonical_ood_action_accuracy_min = {s['canonical_ood_action_accuracy']['min']}")
    print(f"canonical_ood_minimum_class_recall_min = {s['canonical_ood_minimum_class_recall']['min']}")
    print(f"canonical_ood_ineligible_mechanism_count_sum = {s['canonical_ood_ineligible_mechanism_count']['sum']}")
    print(f"canonical_ood_action_flip_count_sum = {s['canonical_ood_action_flip_count']['sum']}")
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
