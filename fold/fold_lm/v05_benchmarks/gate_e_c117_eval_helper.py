"""Evaluation helper for C117 preflight plus fallback composition."""
from __future__ import annotations

from fold_lm.v05_benchmarks import gate_e_acquisition_mechanism_closed_loop as c105
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116


def _predict(router, visible, mask, device):
    _, dependency, present, observed = visible
    return c113._predict(
        router,
        dependency=int(dependency),
        evidence_present=int(present),
        observed_hidden=int(observed),
        visible_mask=mask,
        device=device,
    )


def _row(hidden):
    return {
        "base": 3,
        "dependency": 1,
        "hidden": hidden,
        "evidence_present": 0,
        "visible": (3, 1, 0, 0),
        "target": c105._target(3, 1, hidden),
    }


def evaluate_router(router, device):
    rows = []
    previous = c105._predict
    c105._predict = _predict
    try:
        for visible, actual in c116._pairs():
            initial = c113._predict(
                router,
                dependency=1,
                evidence_present=0,
                observed_hidden=0,
                visible_mask=visible,
                device=device,
            )
            preflight_ok = initial == c116._expected_action(visible)
            if initial != c116._expected_action(actual):
                refreshed = c113._predict(
                    router,
                    dependency=1,
                    evidence_present=0,
                    observed_hidden=0,
                    visible_mask=actual,
                    device=device,
                )
                preflight_ok = preflight_ok and refreshed == c116._expected_action(actual)
            for hidden in (0, 1):
                for name, index in c105._scenario_names(actual):
                    result = c105._evaluate_scenario(
                        router, _row(hidden), actual, name, index, device
                    )
                    result.update(
                        {
                            "visible_mask": list(visible),
                            "actual_mask": list(actual),
                            "hidden": hidden,
                            "preflight_ok": bool(preflight_ok),
                        }
                    )
                    result["combined_passed"] = bool(
                        preflight_ok and result["scenario_passed"]
                    )
                    rows.append(result)
    finally:
        c105._predict = previous

    failure_rows = [
        r for r in rows
        if any(a["outcome"] != "SUCCESS" for a in r["attempt_trace"])
    ]
    groups = {}
    for row in rows:
        key = (
            tuple(row["visible_mask"]),
            tuple(row["actual_mask"]),
            row["scenario"],
            row["success_index"],
        )
        groups.setdefault(key, []).append(row["action_trace"])
    hidden_invariance = float(
        all(len(traces) == 2 and traces[0] == traces[1] for traces in groups.values())
    )
    metrics = {
        "trajectory_pass_rate": sum(r["combined_passed"] for r in rows) / len(rows),
        "preflight_correct_rate": sum(r["preflight_ok"] for r in rows) / len(rows),
        "failure_fallback_recovery_rate": sum(r["combined_passed"] for r in failure_rows) / len(failure_rows),
        "hidden_action_trace_invariance": hidden_invariance,
        "mask_pair_count": len(c116._pairs()),
        "trajectory_count": len(rows),
        "ineligible_mechanism_count": sum(r["ineligible_action_count"] for r in rows),
        "repeat_failed_mechanism_count": sum(r["repeated_failed_mechanism_count"] for r in rows),
        "budget_violation_count": sum(r["budget_violation_count"] for r in rows),
    }
    metrics["gate_passed"] = (
        metrics["trajectory_pass_rate"] == 1.0
        and metrics["preflight_correct_rate"] == 1.0
        and metrics["failure_fallback_recovery_rate"] == 1.0
        and metrics["hidden_action_trace_invariance"] == 1.0
        and metrics["ineligible_mechanism_count"] == 0
        and metrics["repeat_failed_mechanism_count"] == 0
        and metrics["budget_violation_count"] == 0
    )
    return metrics, rows
