from __future__ import annotations
import fold_lm.v05_benchmarks.gate_e_acquisition_mechanism_closed_loop as b

EXPERIMENT_ID = b.EXPERIMENT_ID
SEEDS = b.SEEDS
_orig_scenario = b._evaluate_scenario
_orig_closed = b._evaluate_closed_loop


def _guard_scenario(router, row, initial_mask, scenario_name, success_index, device):
    r = _orig_scenario(router, row, initial_mask, scenario_name, success_index, device)
    rem = list(initial_mask)
    for a in r["attempt_trace"]:
        if a["outcome"] != "SUCCESS" and a["action"] in b.ACTION_TO_BIT:
            rem[b.ACTION_TO_BIT[a["action"]]] = 0
    if r["final_status"] == "UNRESOLVED" and any(rem):
        r["scenario_passed"] = False
    return r


def _safe_closed(router, device):
    try:
        return _orig_closed(router, device)
    except ZeroDivisionError:
        metrics = {
            "answerable_answer_rate": 0.0,
            "answerable_zero_acquisition_rate": 0.0,
            "required_scenario_pass_rate": 0.0,
            "per_decision_minimum_burden_rate": 0.0,
            "eventual_success_answer_rate": 0.0,
            "eventual_success_final_accuracy": 0.0,
            "all_fail_stop_unresolved_rate": 0.0,
            "failure_no_evidence_commit_rate": 0.0,
            "ineligible_mechanism_count": 1,
            "repeat_failed_mechanism_count": 0,
            "budget_violation_count": 0,
            "ask_user_before_self_service_exhausted_count": 0,
            "hidden_counterfactual_action_trace_invariance": 0.0,
            "closed_loop_passed": False,
        }
        return metrics, [{"diagnostic": "learned trajectory skipped an expected conditional branch"}]


def run(*args, **kwargs):
    prev_scenario = b._evaluate_scenario
    prev_closed = b._evaluate_closed_loop
    b._evaluate_scenario = _guard_scenario
    b._evaluate_closed_loop = _safe_closed
    try:
        return b.run(*args, **kwargs)
    finally:
        b._evaluate_scenario = prev_scenario
        b._evaluate_closed_loop = prev_closed


def main(argv=None):
    prev = b.run
    b.run = run
    try:
        return b.main(argv)
    finally:
        b.run = prev


if __name__ == "__main__":
    raise SystemExit(main())
