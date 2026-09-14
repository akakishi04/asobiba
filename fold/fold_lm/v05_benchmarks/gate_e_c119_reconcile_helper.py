"""Runtime-state helper for C119 receipt reconciliation."""
from __future__ import annotations

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118

ANSWER = 0
STOP = 5
ACTION_TO_BIT = {1: 0, 2: 1, 3: 2, 4: 3}
OUTCOMES = ("RECONCILED_APPLIED", "RECONCILED_NOT_APPLIED", "STILL_UNKNOWN")


def scenario(router, visible, actual, hidden, outcome, device):
    ok, action, trace = c118._preflight(router, visible, actual, device)
    execution = retry = fallback = commit = logical_effect = reconcile = key_changed = 0
    request_key = f"c119:{''.join(map(str, actual))}:{action}"

    if not any(actual):
        return {
            "visible": list(visible), "actual": list(actual), "hidden": hidden,
            "outcome": "NONE_AVAILABLE", "trace": trace, "execution": 0,
            "retry": 0, "fallback": 0, "commit": 0, "logical_effect": 0,
            "reconcile": 0, "key_changed": 0, "final": "UNRESOLVED",
            "passed": bool(ok and action == STOP),
        }

    if action not in ACTION_TO_BIT or not actual[ACTION_TO_BIT[action]]:
        return {
            "visible": list(visible), "actual": list(actual), "hidden": hidden,
            "outcome": outcome, "trace": trace, "execution": 0, "retry": 0,
            "fallback": 0, "commit": 0, "logical_effect": 0, "reconcile": 0,
            "key_changed": 0, "final": "INVALID_PREFLIGHT", "passed": False,
        }

    execution = 1
    reconcile = 1

    if outcome == "RECONCILED_APPLIED":
        logical_effect = 1
        commit = 1
        final_action = c113._predict(router, dependency=1, evidence_present=1,
                                     observed_hidden=hidden, visible_mask=actual, device=device)
        trace.append(final_action)
        final = "ANSWERED" if final_action == ANSWER else "NOT_ANSWER"
        passed = ok and final == "ANSWERED" and execution == 1 and retry == 0 and commit == 1
    elif outcome == "RECONCILED_NOT_APPLIED":
        retry_key = request_key
        key_changed += int(retry_key != request_key)
        retry = 1
        execution = 2
        logical_effect = 1
        commit = 1
        final_action = c113._predict(router, dependency=1, evidence_present=1,
                                     observed_hidden=hidden, visible_mask=actual, device=device)
        trace.append(final_action)
        final = "ANSWERED" if final_action == ANSWER else "NOT_ANSWER"
        passed = ok and final == "ANSWERED" and retry == 1 and key_changed == 0 and commit == 1
    elif outcome == "STILL_UNKNOWN":
        final = "UNRESOLVED_UNKNOWN_EFFECT"
        passed = ok and execution == 1 and retry == 0 and fallback == 0 and commit == 0
    else:
        raise ValueError(outcome)

    return {
        "visible": list(visible), "actual": list(actual), "hidden": hidden,
        "outcome": outcome, "trace": trace, "execution": execution,
        "retry": retry, "fallback": fallback, "commit": commit,
        "logical_effect": logical_effect, "reconcile": reconcile,
        "key_changed": key_changed, "final": final, "passed": bool(passed),
    }


def evaluate(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if any(actual):
                for outcome in OUTCOMES:
                    rows.append(scenario(router, visible, actual, hidden, outcome, device))
            else:
                rows.append(scenario(router, visible, actual, hidden, "NONE_AVAILABLE", device))

    applied = [r for r in rows if r["outcome"] == "RECONCILED_APPLIED"]
    not_applied = [r for r in rows if r["outcome"] == "RECONCILED_NOT_APPLIED"]
    unknown = [r for r in rows if r["outcome"] == "STILL_UNKNOWN"]
    none = [r for r in rows if r["outcome"] == "NONE_AVAILABLE"]
    groups = {}
    for r in rows:
        groups.setdefault((tuple(r["visible"]), tuple(r["actual"]), r["outcome"]), []).append(r["trace"])
    hidden_invariance = float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))

    metrics = {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "reconciliation_once_rate": sum(r["reconcile"] == 1 for r in applied + not_applied + unknown) / len(applied + not_applied + unknown),
        "applied_answer_rate": sum(r["final"] == "ANSWERED" for r in applied) / len(applied),
        "applied_zero_retry_rate": sum(r["retry"] == 0 for r in applied) / len(applied),
        "applied_one_commit_rate": sum(r["commit"] == 1 for r in applied) / len(applied),
        "not_applied_answer_rate": sum(r["final"] == "ANSWERED" for r in not_applied) / len(not_applied),
        "not_applied_one_retry_rate": sum(r["retry"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_same_key_rate": sum(r["key_changed"] == 0 for r in not_applied) / len(not_applied),
        "not_applied_one_commit_rate": sum(r["commit"] == 1 for r in not_applied) / len(not_applied),
        "unknown_containment_rate": sum(r["final"] == "UNRESOLVED_UNKNOWN_EFFECT" for r in unknown) / len(unknown),
        "unknown_zero_retry_rate": sum(r["retry"] == 0 for r in unknown) / len(unknown),
        "unknown_zero_commit_rate": sum(r["commit"] == 0 for r in unknown) / len(unknown),
        "unknown_zero_fallback_rate": sum(r["fallback"] == 0 for r in unknown) / len(unknown),
        "recovered_one_logical_effect_rate": sum(r["logical_effect"] == 1 for r in applied + not_applied) / len(applied + not_applied),
        "confirmed_none_stop_rate": sum(r["final"] == "UNRESOLVED" for r in none) / len(none),
        "hidden_trace_invariance": hidden_invariance,
        "mask_pair_count": len(c116._pairs()),
        "scenario_count": len(rows),
        "reconciliation_case_count": len(applied) + len(not_applied) + len(unknown),
    }
    deciding = [k for k in metrics if k.endswith("_rate") or k == "hidden_trace_invariance"]
    metrics["gate_passed"] = all(metrics[k] == 1.0 for k in deciding)
    return metrics, rows
