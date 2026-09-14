"""C100: V5-E acquisition-failure and STOP_UNRESOLVED oracle baseline.

C99 established the successful learned acquisition cycle. C100 freezes the
runtime/policy semantics for acquisition outcomes before learning them:

    SUCCESS      -> commit validated evidence -> ANSWER
    UNAVAILABLE  -> no evidence commit        -> STOP_UNRESOLVED
    DENIED       -> no evidence commit        -> STOP_UNRESOLVED
    INVALID      -> no evidence commit        -> STOP_UNRESOLVED

A failed acquisition must not be retried past the one-read budget and must not
be converted into a guessed direct answer. The model/policy proposes actions;
the runtime alone owns acquisition outcome and evidence mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    ACQUIRE,
    ANSWER,
    _direct_answer,
    _target,
    _visible_signature,
)

EXPERIMENT_ID = "C100-v5e-acquisition-failure-oracle"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
C99_EXPERIMENT_ID = "C99-v5e-acquire-reobserve-answer-cycle"
STOP_UNRESOLVED = 2

NOT_ATTEMPTED = "NOT_ATTEMPTED"
SUCCESS = "SUCCESS"
UNAVAILABLE = "UNAVAILABLE"
DENIED = "DENIED"
INVALID = "INVALID"
OUTCOMES = (SUCCESS, UNAVAILABLE, DENIED, INVALID)
FAILURE_OUTCOMES = (UNAVAILABLE, DENIED, INVALID)
ACQUISITION_BUDGET = 1


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _oracle_action(dependency: int, evidence_present: int, acquisition_status: str) -> int:
    if dependency == 0 or evidence_present == 1:
        return ANSWER
    if acquisition_status == NOT_ATTEMPTED:
        return ACQUIRE
    return STOP_UNRESOLVED


def _runtime_apply_outcome(row: dict, outcome: str, remaining_budget: int):
    if remaining_budget <= 0:
        return None, remaining_budget, False, False
    if outcome == SUCCESS:
        visible_after = _visible_signature(
            int(row["base"]), int(row["dependency"]), 1, int(row["hidden"])
        )
        return visible_after, remaining_budget - 1, True, True
    if outcome in FAILURE_OUTCOMES:
        # Failed/untrusted acquisitions never become authoritative evidence.
        return tuple(row["visible"]), remaining_budget - 1, True, False
    raise ValueError(f"unknown C100 acquisition outcome: {outcome}")


def _evaluate_case(row: dict, outcome: str | None) -> dict:
    visible_before = tuple(row["visible"])
    status_before = NOT_ATTEMPTED
    first_action = _oracle_action(
        int(row["dependency"]), int(row["evidence_present"]), status_before
    )
    remaining_budget = ACQUISITION_BUDGET
    acquisition_count = 0
    evidence_commit_count = 0
    repeat_acquisition_count = 0
    budget_violation_count = 0
    guessed_answer_after_failure_count = 0
    second_action = None
    visible_after = visible_before
    final_answer = None
    final_status = "ANSWERED"

    if first_action == ANSWER:
        final_answer = _direct_answer(*visible_before)
    elif first_action == ACQUIRE:
        if outcome is None:
            raise RuntimeError("C100 required acquisition case missing outcome")
        visible_after, remaining_budget, applied, committed = _runtime_apply_outcome(
            row, outcome, remaining_budget
        )
        if not applied:
            budget_violation_count += 1
        else:
            acquisition_count += 1
            evidence_commit_count += int(committed)
            second_action = _oracle_action(
                int(row["dependency"]), int(visible_after[2]), outcome
            )
            if second_action == ANSWER:
                final_answer = _direct_answer(*visible_after)
            elif second_action == ACQUIRE:
                repeat_acquisition_count += 1
                _again, _budget, applied_again, _committed_again = _runtime_apply_outcome(
                    row, outcome, remaining_budget
                )
                if applied_again:
                    budget_violation_count += 1
            elif second_action == STOP_UNRESOLVED:
                final_status = "UNRESOLVED"
                if outcome == SUCCESS:
                    raise RuntimeError("C100 SUCCESS unexpectedly unresolved")
            else:
                raise RuntimeError(f"C100 unknown second action: {second_action}")
    else:
        raise RuntimeError("C100 initial STOP_UNRESOLVED is not valid before acquisition")

    if outcome in FAILURE_OUTCOMES and final_answer is not None:
        guessed_answer_after_failure_count += 1

    if acquisition_count > ACQUISITION_BUDGET:
        budget_violation_count += 1

    expected_unresolved = outcome in FAILURE_OUTCOMES
    success_final_correct = None
    if outcome == SUCCESS:
        success_final_correct = final_answer == row["target"]

    return {
        "base": row["base"],
        "dependency": row["dependency"],
        "hidden": row["hidden"],
        "initial_evidence_present": row["evidence_present"],
        "outcome": outcome,
        "first_action": first_action,
        "second_action": second_action,
        "runtime_acquisition_count": acquisition_count,
        "evidence_commit_count": evidence_commit_count,
        "repeat_acquisition_count": repeat_acquisition_count,
        "budget_violation_count": budget_violation_count,
        "guessed_answer_after_failure_count": guessed_answer_after_failure_count,
        "final_status": final_status,
        "final_answer": final_answer,
        "target": row["target"],
        "expected_unresolved": expected_unresolved,
        "success_final_correct": success_final_correct,
    }


def run(*, protected_result_path: Path, c99_summary_path: Path, output_dir: Path):
    c99 = json.loads(c99_summary_path.read_text(encoding="utf-8"))
    if c99.get("experiment_id") != C99_EXPERIMENT_ID:
        raise RuntimeError("C100 requires C99 summary")
    if c99.get("status") != "PASS" or not bool(
        c99.get("summary", {}).get("acquire_reobserve_answer_cycle_gate_passed")
    ):
        raise RuntimeError("C100 requires accepted C99 acquisition cycle")

    protected_before = _sha256(protected_result_path)

    base_rows = []
    for base, dependency, hidden, evidence_present in itertools.product(
        range(4), (0, 1), (0, 1), (0, 1)
    ):
        visible = _visible_signature(base, dependency, evidence_present, hidden)
        base_rows.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": visible,
                "target": _target(base, dependency, hidden),
            }
        )

    records = []
    for row in base_rows:
        required = row["dependency"] == 1 and row["evidence_present"] == 0
        if required:
            for outcome in OUTCOMES:
                records.append(_evaluate_case(row, outcome))
        else:
            records.append(_evaluate_case(row, None))

    answerable = [r for r in records if r["outcome"] is None]
    success = [r for r in records if r["outcome"] == SUCCESS]
    failures = [r for r in records if r["outcome"] in FAILURE_OUTCOMES]

    answerable_zero_acquire = sum(r["runtime_acquisition_count"] == 0 for r in answerable) / len(answerable)
    success_answer_rate = sum(r["second_action"] == ANSWER for r in success) / len(success)
    success_final_accuracy = sum(bool(r["success_final_correct"]) for r in success) / len(success)
    failure_stop_rate = sum(r["second_action"] == STOP_UNRESOLVED for r in failures) / len(failures)
    failure_no_commit_rate = sum(r["evidence_commit_count"] == 0 for r in failures) / len(failures)
    failure_no_guess_rate = sum(r["guessed_answer_after_failure_count"] == 0 for r in failures) / len(failures)
    repeat_count = sum(r["repeat_acquisition_count"] for r in records)
    budget_violations = sum(r["budget_violation_count"] for r in records)
    successful_commit_rate = sum(r["evidence_commit_count"] == 1 for r in success) / len(success)

    gate = (
        answerable_zero_acquire == 1.0
        and success_answer_rate == 1.0
        and success_final_accuracy == 1.0
        and successful_commit_rate == 1.0
        and failure_stop_rate == 1.0
        and failure_no_commit_rate == 1.0
        and failure_no_guess_rate == 1.0
        and repeat_count == 0
        and budget_violations == 0
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C100")

    summary = {
        "base_example_count": len(base_rows),
        "evaluated_case_count": len(records),
        "action_space": ["ANSWER", "ACQUIRE", "STOP_UNRESOLVED"],
        "acquisition_outcomes": list(OUTCOMES),
        "acquisition_budget": ACQUISITION_BUDGET,
        "model_proposes_runtime_owns_outcome_and_evidence_mutation": True,
        "answerable_zero_acquisition_rate": answerable_zero_acquire,
        "success_post_acquisition_answer_rate": success_answer_rate,
        "success_final_accuracy": success_final_accuracy,
        "success_evidence_commit_rate": successful_commit_rate,
        "failure_stop_unresolved_rate": failure_stop_rate,
        "failure_no_evidence_commit_rate": failure_no_commit_rate,
        "failure_no_guessed_answer_rate": failure_no_guess_rate,
        "repeat_acquisition_count": repeat_count,
        "budget_violation_count": budget_violations,
        "acquisition_failure_oracle_gate_passed": gate,
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "oracle acquisition-outcome authority and safe failure termination",
        "summary": summary,
        "records": records,
        "C99_summary_sha256": _sha256(c99_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C100 is an oracle failure-policy baseline, not a learned STOP_UNRESOLVED controller",
            "UNAVAILABLE, DENIED, and INVALID are abstract runtime outcome classes",
            "C100 does not yet select among memory, retrieval, observation, or user-question mechanisms",
            "C100 does not test retries with changed acquisition mechanisms",
            "C100 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c99-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c99_summary_path=args.c99_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C100 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
