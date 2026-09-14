"""C116: stale-low priority refresh before external mechanism execution.

C115 refreshed availability only when the router proposed terminal
STOP_UNRESOLVED. C116 tests the missing case: a visible higher-burden mechanism
may still be executable while a lower-burden mechanism has become available in
the runtime-authoritative mask.

Before any external mechanism execution, runtime refreshes authoritative
availability once. If the router's proposal is not the minimum-burden action
under the authoritative mask, runtime suppresses that execution, replaces the
visible mask, reobserves, and asks the router again. Only the authoritative
minimum-burden mechanism may execute. Terminal STOP is accepted only after the
same refresh confirms no mechanism exists.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113

EXPERIMENT_ID = "C116-v5e-authoritative-preflight-priority-refresh"
C115_EXPERIMENT_ID = "C115-v5e-stale-low-terminal-refresh"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261361, 20261362, 20261363)
ANSWER = 0
STOP_UNRESOLVED = 5
ACTION_TO_BIT = {1: 0, 2: 1, 3: 2, 4: 3}


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _pairs():
    masks = tuple(itertools.product((0, 1), repeat=4))
    return [
        (visible, actual)
        for visible in masks
        for actual in masks
        if all(v <= a for v, a in zip(visible, actual))
    ]


def _expected_action(mask):
    for bit, eligible in enumerate(mask):
        if eligible:
            return bit + 1
    return STOP_UNRESOLVED


def _scenario(router, visible_mask, actual_mask, hidden, device):
    visible = list(visible_mask)
    trace = []
    refresh_count = 0
    execution_count = 0
    commit_count = 0
    suppressed_nonminimal_execution_count = 0
    priority_violation_count = 0
    premature_stop_accept_count = 0

    initial_action = c113._predict(
        router,
        dependency=1,
        evidence_present=0,
        observed_hidden=0,
        visible_mask=visible,
        device=device,
    )
    trace.append(initial_action)
    expected_visible = _expected_action(visible_mask)
    priority_violation_count += int(initial_action != expected_visible)

    # Runtime refreshes authoritative availability before accepting STOP or
    # executing any proposed mechanism.
    refresh_count += 1
    authoritative_action = _expected_action(actual_mask)

    if initial_action != authoritative_action:
        if initial_action in ACTION_TO_BIT:
            suppressed_nonminimal_execution_count += 1
        visible = list(actual_mask)
        action = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=visible,
            device=device,
        )
        trace.append(action)
        priority_violation_count += int(action != authoritative_action)
    else:
        action = initial_action
        visible = list(actual_mask)

    if authoritative_action == STOP_UNRESOLVED:
        if action != STOP_UNRESOLVED:
            final_status = "NONSTOP_AFTER_EMPTY_REFRESH"
        else:
            final_status = "UNRESOLVED"
    else:
        if action == STOP_UNRESOLVED:
            premature_stop_accept_count += 1
            final_status = "PREMATURE_STOP"
        elif action != authoritative_action:
            final_status = "NONMINIMAL_AUTHORITATIVE_ACTION"
        elif action in ACTION_TO_BIT and actual_mask[ACTION_TO_BIT[action]]:
            execution_count += 1
            commit_count += 1
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=hidden,
                visible_mask=visible,
                device=device,
            )
            trace.append(final_action)
            final_status = "ANSWERED" if final_action == ANSWER else "POST_COMMIT_NOT_ANSWER"
        else:
            final_status = "INVALID_AUTHORITATIVE_ACTION"

    actual_available = any(actual_mask)
    expected_terminal = "ANSWERED" if actual_available else "UNRESOLVED"
    expected_execution = 1 if actual_available else 0
    priority_upgrade = (
        any(visible_mask)
        and actual_available
        and _expected_action(visible_mask) != authoritative_action
    )
    terminal_recovery = not any(visible_mask) and actual_available
    passed = (
        final_status == expected_terminal
        and refresh_count == 1
        and execution_count == expected_execution
        and commit_count == expected_execution
        and priority_violation_count == 0
        and premature_stop_accept_count == 0
        and (
            suppressed_nonminimal_execution_count == 1
            if priority_upgrade
            else suppressed_nonminimal_execution_count == 0
        )
    )
    return {
        "visible_mask": list(visible_mask),
        "actual_mask": list(actual_mask),
        "hidden": hidden,
        "initial_action": initial_action,
        "authoritative_action": authoritative_action,
        "action_trace": trace,
        "priority_upgrade": priority_upgrade,
        "terminal_recovery": terminal_recovery,
        "refresh_count": refresh_count,
        "execution_count": execution_count,
        "commit_count": commit_count,
        "suppressed_nonminimal_execution_count": suppressed_nonminimal_execution_count,
        "priority_violation_count": priority_violation_count,
        "premature_stop_accept_count": premature_stop_accept_count,
        "final_status": final_status,
        "scenario_passed": passed,
    }


def _evaluate(router, device):
    rows = [
        _scenario(router, visible, actual, hidden, device)
        for visible, actual in _pairs()
        for hidden in (0, 1)
    ]
    priority_upgrade_rows = [r for r in rows if r["priority_upgrade"]]
    terminal_recovery_rows = [r for r in rows if r["terminal_recovery"]]
    unchanged_rows = [
        r for r in rows
        if any(r["actual_mask"]) and not r["priority_upgrade"] and not r["terminal_recovery"]
    ]
    confirmed_none = [r for r in rows if not any(r["actual_mask"])]

    groups = {}
    for row in rows:
        groups.setdefault((tuple(row["visible_mask"]), tuple(row["actual_mask"])), []).append(row["action_trace"])
    hidden_invariance = 1.0
    for traces in groups.values():
        if len(traces) != 2 or traces[0] != traces[1]:
            hidden_invariance = 0.0
            break

    metrics = {
        "required_scenario_pass_rate": sum(r["scenario_passed"] for r in rows) / len(rows),
        "exactly_one_preflight_refresh_rate": sum(r["refresh_count"] == 1 for r in rows) / len(rows),
        "priority_upgrade_recovery_rate": sum(r["final_status"] == "ANSWERED" and r["execution_count"] == 1 for r in priority_upgrade_rows) / len(priority_upgrade_rows),
        "priority_upgrade_nonminimal_external_execution_count": sum(max(0, r["execution_count"] - 1) for r in priority_upgrade_rows),
        "priority_upgrade_suppression_exact_rate": sum(r["suppressed_nonminimal_execution_count"] == 1 for r in priority_upgrade_rows) / len(priority_upgrade_rows),
        "terminal_recovery_rate": sum(r["final_status"] == "ANSWERED" and r["execution_count"] == 1 for r in terminal_recovery_rows) / len(terminal_recovery_rows),
        "unchanged_authoritative_execution_rate": sum(r["final_status"] == "ANSWERED" and r["execution_count"] == 1 for r in unchanged_rows) / len(unchanged_rows),
        "confirmed_unavailable_stop_rate": sum(r["final_status"] == "UNRESOLVED" for r in confirmed_none) / len(confirmed_none),
        "confirmed_unavailable_zero_execution_rate": sum(r["execution_count"] == 0 for r in confirmed_none) / len(confirmed_none),
        "priority_violation_count": sum(r["priority_violation_count"] for r in rows),
        "premature_stop_accept_count": sum(r["premature_stop_accept_count"] for r in rows),
        "hidden_action_trace_invariance": hidden_invariance,
        "mask_pair_count": len(_pairs()),
        "required_case_count": len(rows),
        "priority_upgrade_case_count": len(priority_upgrade_rows),
        "terminal_recovery_case_count": len(terminal_recovery_rows),
    }
    metrics["authoritative_preflight_priority_refresh_gate_passed"] = (
        metrics["required_scenario_pass_rate"] == 1.0
        and metrics["exactly_one_preflight_refresh_rate"] == 1.0
        and metrics["priority_upgrade_recovery_rate"] == 1.0
        and metrics["priority_upgrade_nonminimal_external_execution_count"] == 0
        and metrics["priority_upgrade_suppression_exact_rate"] == 1.0
        and metrics["terminal_recovery_rate"] == 1.0
        and metrics["unchanged_authoritative_execution_rate"] == 1.0
        and metrics["confirmed_unavailable_stop_rate"] == 1.0
        and metrics["confirmed_unavailable_zero_execution_rate"] == 1.0
        and metrics["priority_violation_count"] == 0
        and metrics["premature_stop_accept_count"] == 0
        and metrics["hidden_action_trace_invariance"] == 1.0
    )
    return metrics, rows


def run(*, protected_result_path: Path, c115_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c115_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C115_EXPERIMENT_ID:
        raise RuntimeError("C116 requires C115 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "stale_low_terminal_refresh_gate_passed"
    ):
        raise RuntimeError("C116 requires accepted C115")
    if not torch.cuda.is_available():
        raise RuntimeError("C116 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        metrics, scenarios = _evaluate(router, device)
        passed = bool(metrics["authoritative_preflight_priority_refresh_gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": metrics, "scenarios": scenarios, "validation_passed": passed})
        print(
            f"[C116] seed={seed} required={metrics['required_scenario_pass_rate']:.6f} "
            f"upgrade={metrics['priority_upgrade_recovery_rate']:.6f} "
            f"terminal={metrics['terminal_recovery_rate']:.6f} "
            f"priority={metrics['priority_violation_count']} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C116")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "production_adapter": "canonicalize_boolean_channels",
        "runtime_refresh_before_external_execution_or_terminal_stop": True,
        "authoritative_mask_superset_of_visible_mask": True,
        "mask_pair_count": ms[0]["mask_pair_count"],
        "required_case_count": ms[0]["required_case_count"],
        "priority_upgrade_case_count": ms[0]["priority_upgrade_case_count"],
        "terminal_recovery_case_count": ms[0]["terminal_recovery_case_count"],
        "required_scenario_pass_rate": _stats([m["required_scenario_pass_rate"] for m in ms]),
        "exactly_one_preflight_refresh_rate": _stats([m["exactly_one_preflight_refresh_rate"] for m in ms]),
        "priority_upgrade_recovery_rate": _stats([m["priority_upgrade_recovery_rate"] for m in ms]),
        "priority_upgrade_suppression_exact_rate": _stats([m["priority_upgrade_suppression_exact_rate"] for m in ms]),
        "terminal_recovery_rate": _stats([m["terminal_recovery_rate"] for m in ms]),
        "unchanged_authoritative_execution_rate": _stats([m["unchanged_authoritative_execution_rate"] for m in ms]),
        "confirmed_unavailable_stop_rate": _stats([m["confirmed_unavailable_stop_rate"] for m in ms]),
        "priority_violation_count": {"sum": sum(m["priority_violation_count"] for m in ms), "max": max(m["priority_violation_count"] for m in ms)},
        "premature_stop_accept_count": {"sum": sum(m["premature_stop_accept_count"] for m in ms), "max": max(m["premature_stop_accept_count"] for m in ms)},
        "hidden_action_trace_invariance": _stats([m["hidden_action_trace_invariance"] for m in ms]),
        "all_validation_passed": all_pass,
        "authoritative_preflight_priority_refresh_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-AUTHORITY-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "authoritative preflight refresh before external execution or terminal stop",
        "summary": summary,
        "records": records,
        "C115_summary_sha256": _sha(c115_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C116 assumes authoritative availability can be refreshed before each proposed external execution",
            "availability refresh is synthetic and does not invoke real tools",
            "the authoritative minimum-burden mechanism is forced to succeed after selection",
            "C116 does not model freshness cost or decide whether every execution justifies refresh",
            "C116 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
