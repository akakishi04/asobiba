"""Tracked execution driver for C103."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_acquisition_mechanism_oracle as bench

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


def _latest_c102() -> Path:
    candidates = [p for p in RUNS.glob("c102-v5e-learned-outcome-cycle-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C102 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C103 V5-E acquisition mechanism oracle ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E")
    print("task = acquisition mechanism oracle")
    print("actions = ANSWER,READ_MEMORY,RETRIEVE,OBSERVE,ASK_USER,STOP_UNRESOLVED")
    print("eligible_masks = exhaustive 16")
    print("burden_order = READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER")
    print("authority = runtime owns mechanism eligibility and permission")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C103")

    c102_summary = _latest_c102()
    out_dir = RUNS / f"c103-v5e-acquisition-mechanism-{time.time_ns()}"
    print("=== import preflight ===")
    print("C103 import OK:", bench.EXPERIMENT_ID, [x[1] for x in bench.MECHANISMS])
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C103 benchmark ===")
    report = bench.run(
        protected_result_path=C37,
        c102_summary_path=c102_summary,
        output_dir=out_dir,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C103 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C103 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"acquisition_mechanism_oracle_gate_passed = {s['acquisition_mechanism_oracle_gate_passed']}")
    print(f"answerable_answer_rate = {s['answerable_answer_rate']}")
    print(f"required_no_direct_answer_rate = {s['required_no_direct_answer_rate']}")
    print(f"minimum_burden_eligible_mechanism_rate = {s['minimum_burden_eligible_mechanism_rate']}")
    print(f"no_eligible_mechanism_stop_unresolved_rate = {s['no_eligible_mechanism_stop_unresolved_rate']}")
    print(f"ask_user_avoided_when_self_service_eligible_rate = {s['ask_user_avoided_when_self_service_eligible_rate']}")
    print(f"hidden_counterfactual_action_invariance = {s['missing_evidence_hidden_counterfactual_action_invariance']}")
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
