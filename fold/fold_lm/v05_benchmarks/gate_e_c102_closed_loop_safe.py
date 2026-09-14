"""Execution-safe wrapper for C102.

The C102 scientific gate should remain a valid completed experiment even if a
fresh-seed router is catastrophically wrong and never enters an expected outcome
branch.  The base benchmark computes conditional rates whose denominator can be
zero only under such a scientific failure.  This wrapper converts that case into
an explicit gate-false record instead of treating it as an invalid execution.
"""
from __future__ import annotations

import fold_lm.v05_benchmarks.gate_e_learned_acquisition_outcome_closed_loop as base

EXPERIMENT_ID = base.EXPERIMENT_ID
SEEDS = base.SEEDS


def _execution_safe_evaluate(router, device):
    try:
        return _ORIGINAL_EVALUATE(router, device)
    except ZeroDivisionError:
        return {
            "initial_required_acquisition_recall": 0.0,
            "initial_answerable_answer_rate": 0.0,
            "initial_unnecessary_acquisition_rate": 1.0,
            "premature_stop_count": 1,
            "success_evidence_commit_rate": 0.0,
            "success_post_acquisition_answer_rate": 0.0,
            "success_final_accuracy": 0.0,
            "failure_stop_unresolved_rate": 0.0,
            "failure_no_evidence_commit_rate": 0.0,
            "failure_no_guessed_answer_rate": 0.0,
            "repeat_acquisition_count": 0,
            "budget_violation_count": 0,
            "total_runtime_acquisitions": 0,
            "closed_loop_passed": False,
            "records": [
                {
                    "diagnostic": "conditional metric denominator reached zero because the learned trajectory never entered an expected branch",
                    "scientific_result": "valid negative",
                }
            ],
        }


_ORIGINAL_EVALUATE = base._evaluate_closed_loop


def run(*args, **kwargs):
    previous = base._evaluate_closed_loop
    base._evaluate_closed_loop = _execution_safe_evaluate
    try:
        return base.run(*args, **kwargs)
    finally:
        base._evaluate_closed_loop = previous


def main(argv=None):
    previous_run = base.run
    base.run = run
    try:
        return base.main(argv)
    finally:
        base.run = previous_run


if __name__ == "__main__":
    raise SystemExit(main())
