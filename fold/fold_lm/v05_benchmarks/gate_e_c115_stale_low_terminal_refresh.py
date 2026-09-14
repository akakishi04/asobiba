"""C115: stale-low availability recovery before terminal STOP_UNRESOLVED.

C113 covered stale-high model-visible eligibility with authoritative per-action
preflight. C115 covers the opposite terminal case: the model-visible mask may
be stale-low and contain no eligible mechanism even though runtime-authoritative
availability has recovered.

Registered policy for this experiment:
- if the router proposes STOP_UNRESOLVED while critical evidence is still
  missing, runtime performs one authoritative availability refresh before
  accepting the terminal action;
- if refresh reveals an available mechanism, visible state is replaced by the
  authoritative mask and the router reobserves it;
- if refresh confirms no mechanisms are available, STOP_UNRESOLVED is accepted;
- when a visible mechanism is already executable, C115 does not refresh merely
  to discover a potentially lower-burden hidden mechanism. That is a separate
  freshness/value question.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113

EXPERIMENT_ID = "C115-v5e-stale-low-terminal-refresh"
C114_EXPERIMENT_ID = "C114-v5e-production-control-hot-path-profile"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261351, 20261352, 20261353)
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


def _expected_mechanism(mask):
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
    priority_violations = 0
    premature_stop_accepts = 0

    action = c113._predict(
        router,
        dependency=1,
        evidence_present=0,
        observed_hidden=0,
        visible_mask=visible,
        device=device,
    )
    trace.append(action)
    expected_visible = _expected_mechanism(visible)
    priority_violations += int(action != expected_visible)

    if action == STOP_UNRESOLVED:
        refresh_count += 1
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
        expected_actual = _expected_mechanism(actual_mask)
        priority_violations += int(action != expected_actual)

        if any(actual_mask):
            if action == STOP_UNRESOLVED:
                premature_stop_accepts += 1
                final_status = "PREMATURE_STOP"
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
                final_status = "INVALID_POST_REFRESH_ACTION"
        else:
            final_status = "UNRESOLVED" if action == STOP_UNRESOLVED else "FALSE_EXECUTION_AFTER_EMPTY_REFRESH"
    elif action in ACTION_TO_BIT and visible[ACTION_TO_BIT[action]] and actual_mask[ACTION_TO_BIT[action]]:
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
        final_status = "INVALID_INITIAL_ACTION"

    if any(actual_mask):
        expected_terminal = "ANSWERED"
        expected_execution = 1
    else:
        expected_terminal = "UNRESOLVED"
        expected_execution = 0

    expected_refresh = 1 if not any(visible_mask) else 0
    passed = (
        final_status == expected_terminal
        and execution_count == expected_execution
        and commit_count == expected_execution
        and refresh_count == expected_refresh
        and priority_violations == 0
        and premature_stop_accepts == 0
    )
    return {
        "visible_mask": list(visible_mask),
        "actual_mask": list(actual_mask),
        "hidden": hidden,
        "action_trace": trace,
        "refresh_count": refresh_count,
        "execution_count": execution_count,
        "commit_count": commit_count,
        "priority_violation_count": priority_violations,
        "premature_stop_accept_count": premature_stop_accepts,
        "final_status": final_status,
        "scenario_passed": passed,
    }


def _evaluate(router, device):
    pairs = _pairs()
    rows = [
        _scenario(router, visible, actual, hidden, device)
        for visible, actual in pairs
        for hidden in (0, 1)
    ]
    false_negative = [r for r in rows if not any(r["visible_mask"]) and any(r["actual_mask"])]
    confirmed_none = [r for r in rows if not any(r["visible_mask"]) and not any(r["actual_mask"])]
    visible_available = [r for r in rows if any(r["visible_mask"])]

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
        "false_negative_recovery_rate": sum(r["final_status"] == "ANSWERED" and r["execution_count"] == 1 for r in false_negative) / len(false_negative),
        "false_negative_exactly_one_refresh_rate": sum(r["refresh_count"] == 1 for r in false_negative) / len(false_negative),
        "confirmed_unavailable_stop_rate": sum(r["final_status"] == "UNRESOLVED" for r in confirmed_none) / len(confirmed_none),
        "confirmed_unavailable_zero_execution_rate": sum(r["execution_count"] == 0 for r in confirmed_none) / len(confirmed_none),
        "visible_available_zero_refresh_rate": sum(r["refresh_count"] == 0 for r in visible_available) / len(visible_available),
        "priority_violation_count": sum(r["priority_violation_count"] for r in rows),
        "premature_stop_accept_count": sum(r["premature_stop_accept_count"] for r in rows),
        "hidden_action_trace_invariance": hidden_invariance,
        "mask_pair_count": len(pairs),
        "required_case_count": len(rows),
        "false_negative_case_count": len(false_negative),
    }
    metrics["stale_low_terminal_refresh_gate_passed"] = (
        metrics["required_scenario_pass_rate"] == 1.0
        and metrics["false_negative_recovery_rate"] == 1.0
        and metrics["false_negative_exactly_one_refresh_rate"] == 1.0
        and metrics["confirmed_unavailable_stop_rate"] == 1.0
        and metrics["confirmed_unavailable_zero_execution_rate"] == 1.0
        and metrics["visible_available_zero_refresh_rate"] == 1.0
        and metrics["priority_violation_count"] == 0
        and metrics["premature_stop_accept_count"] == 0
        and metrics["hidden_action_trace_invariance"] == 1.0
    )
    return metrics, rows


def run(*, protected_result_path: Path, c114_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c114_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C114_EXPERIMENT_ID:
        raise RuntimeError("C115 requires C114 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get("performance_characterization_completed"):
        raise RuntimeError("C115 requires completed C114 characterization")
    if not torch.cuda.is_available():
        raise RuntimeError("C115 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        metrics, scenarios = _evaluate(router, device)
        passed = bool(metrics["stale_low_terminal_refresh_gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": metrics, "scenarios": scenarios, "validation_passed": passed})
        print(
            f"[C115] seed={seed} required={metrics['required_scenario_pass_rate']:.6f} "
            f"recovery={metrics['false_negative_recovery_rate']:.6f} "
            f"stop={metrics['confirmed_unavailable_stop_rate']:.6f} "
            f"priority={metrics['priority_violation_count']} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C115")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "production_adapter": "canonicalize_boolean_channels",
        "visible_eligibility_can_be_stale_low": True,
        "runtime_refresh_before_terminal_stop": True,
        "refresh_when_visible_action_exists": False,
        "mask_pair_count": ms[0]["mask_pair_count"],
        "required_case_count": ms[0]["required_case_count"],
        "false_negative_case_count": ms[0]["false_negative_case_count"],
        "required_scenario_pass_rate": _stats([m["required_scenario_pass_rate"] for m in ms]),
        "false_negative_recovery_rate": _stats([m["false_negative_recovery_rate"] for m in ms]),
        "false_negative_exactly_one_refresh_rate": _stats([m["false_negative_exactly_one_refresh_rate"] for m in ms]),
        "confirmed_unavailable_stop_rate": _stats([m["confirmed_unavailable_stop_rate"] for m in ms]),
        "confirmed_unavailable_zero_execution_rate": _stats([m["confirmed_unavailable_zero_execution_rate"] for m in ms]),
        "visible_available_zero_refresh_rate": _stats([m["visible_available_zero_refresh_rate"] for m in ms]),
        "priority_violation_count": {"sum": sum(m["priority_violation_count"] for m in ms), "max": max(m["priority_violation_count"] for m in ms)},
        "premature_stop_accept_count": {"sum": sum(m["premature_stop_accept_count"] for m in ms), "max": max(m["premature_stop_accept_count"] for m in ms)},
        "hidden_action_trace_invariance": _stats([m["hidden_action_trace_invariance"] for m in ms]),
        "all_validation_passed": all_pass,
        "stale_low_terminal_refresh_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-AUTHORITY-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "stale-low eligibility recovery before terminal STOP_UNRESOLVED",
        "summary": summary,
        "records": records,
        "C114_summary_sha256": _sha(c114_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C115 refreshes only before terminal STOP_UNRESOLVED",
            "C115 does not discover a newly available lower-burden mechanism while another visible mechanism is executable",
            "availability refresh is synthetic and does not invoke real tools",
            "C115 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
