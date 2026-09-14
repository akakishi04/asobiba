"""Tracked execution driver for C104."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_supervised_acquisition_mechanism_selector as bench

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


def _latest_c103() -> Path:
    candidates = [p for p in RUNS.glob("c103-v5e-acquisition-mechanism-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C103 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C104 V5-E supervised acquisition mechanism selector ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E")
    print("task = supervised acquisition mechanism selection")
    print("actions = ANSWER,READ_MEMORY,RETRIEVE,OBSERVE,ASK_USER,STOP_UNRESOLVED")
    print("fresh_seeds = 20261211,20261212,20261213")
    print("train_bases = 0,1,2")
    print("validation_base = 3 (unseen)")
    print("working_lane = base,dependency,evidence_present,observed_hidden")
    print("context_lane = memory,retrieval,observation,user eligibility bits")
    print("control_width = 4")
    print("hidden_width = 8")
    print("training_steps = 640")
    print("burden_order = READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C104")

    c103_summary = _latest_c103()
    out_dir = RUNS / f"c104-v5e-supervised-mechanism-{time.time_ns()}"
    print("=== import preflight ===")
    print("C104 import OK:", bench.EXPERIMENT_ID, bench.SEEDS, bench.TRAIN_BASES, bench.VALIDATION_BASES)
    print("=== focused regression ===")
    _run(
        str(REPO / ".venv-py31315" / "Scripts" / "python.exe"),
        "-m",
        "unittest",
        "tests_lm.test_v05_controller",
        "-v",
    )
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C104 benchmark ===")
    report = bench.run(
        protected_result_path=C37,
        c103_summary_path=c103_summary,
        output_dir=out_dir,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C104 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C104 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"supervised_acquisition_mechanism_selector_gate_passed = {s['supervised_acquisition_mechanism_selector_gate_passed']}")
    print(f"validation_action_accuracy_min = {s['validation_action_accuracy']['min']}")
    print(f"validation_minimum_class_recall_min = {s['validation_minimum_class_recall']['min']}")
    print(f"validation_action_flip_count_sum = {s['validation_action_flip_count']['sum']}")
    print(f"validation_answerable_answer_rate_min = {s['validation_answerable_answer_rate']['min']}")
    print(f"validation_required_no_direct_answer_rate_min = {s['validation_required_no_direct_answer_rate']['min']}")
    print(f"validation_minimum_burden_rate_min = {s['validation_minimum_burden_eligible_mechanism_rate']['min']}")
    print(f"validation_no_eligible_stop_rate_min = {s['validation_no_eligible_mechanism_stop_unresolved_rate']['min']}")
    print(f"validation_ask_user_avoided_rate_min = {s['validation_ask_user_avoided_when_self_service_eligible_rate']['min']}")
    print(f"validation_ineligible_mechanism_count_sum = {s['validation_ineligible_mechanism_count']['sum']}")
    print(f"validation_hidden_invariance_min = {s['validation_hidden_counterfactual_action_invariance']['min']}")
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
