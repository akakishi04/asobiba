"""Tracked execution driver for C105."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from fold_lm.v05_benchmarks import gate_e_c105_guard as bench

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


def _latest_c104() -> Path:
    candidates = [p for p in RUNS.glob("c104-v5e-supervised-mechanism-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C104 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C105 V5-E learned acquisition mechanism closed loop ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E")
    print("task = learned acquisition mechanism fallback closed loop")
    print("actions = ANSWER,READ_MEMORY,RETRIEVE,OBSERVE,ASK_USER,STOP_UNRESOLVED")
    print("fresh_seeds = 20261221,20261222,20261223")
    print("train_bases = 0,1,2")
    print("validation_base = 3 (unseen)")
    print("acquisition_budget = 4")
    print("runtime_rule = failed mechanism becomes ineligible; SUCCESS alone commits evidence")
    print("fallback_order = READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C105")

    c104_summary = _latest_c104()
    c104 = json.loads(c104_summary.read_text(encoding="utf-8"))
    if c104.get("experiment_id") != "C104-v5e-supervised-acquisition-mechanism-selector":
        raise RuntimeError("C105 requires C104 summary")
    if c104.get("status") != "PASS" or not bool(
        c104.get("summary", {}).get("supervised_acquisition_mechanism_selector_gate_passed")
    ):
        raise RuntimeError("C105 requires accepted C104 mechanism selector")

    print("=== import preflight ===")
    print("C105 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(sys.executable, "-m", "unittest", "tests_lm.test_v05_controller", "-v")

    out_dir = RUNS / f"c105-v5e-mechanism-cycle-{time.time_ns()}"
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C105 benchmark ===")
    report = bench.run(
        protected_result_path=C37,
        c104_summary_path=c104_summary,
        output_dir=out_dir,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C105 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C105 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"learned_acquisition_mechanism_closed_loop_gate_passed = {s['learned_acquisition_mechanism_closed_loop_gate_passed']}")
    print(f"answerable_answer_rate_min = {s['answerable_answer_rate']['min']}")
    print(f"answerable_zero_acquisition_rate_min = {s['answerable_zero_acquisition_rate']['min']}")
    print(f"required_scenario_pass_rate_min = {s['required_scenario_pass_rate']['min']}")
    print(f"minimum_burden_rate_min = {s['per_decision_minimum_burden_rate']['min']}")
    print(f"eventual_success_answer_rate_min = {s['eventual_success_answer_rate']['min']}")
    print(f"eventual_success_final_accuracy_min = {s['eventual_success_final_accuracy']['min']}")
    print(f"all_fail_stop_rate_min = {s['all_fail_stop_unresolved_rate']['min']}")
    print(f"failure_no_commit_rate_min = {s['failure_no_evidence_commit_rate']['min']}")
    print(f"ineligible_mechanism_count_sum = {s['ineligible_mechanism_count']['sum']}")
    print(f"repeat_failed_mechanism_count_sum = {s['repeat_failed_mechanism_count']['sum']}")
    print(f"budget_violation_count_sum = {s['budget_violation_count']['sum']}")
    print(f"premature_ask_user_count_sum = {s['ask_user_before_self_service_exhausted_count']['sum']}")
    print(f"hidden_trace_invariance_min = {s['hidden_counterfactual_action_trace_invariance']['min']}")
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
