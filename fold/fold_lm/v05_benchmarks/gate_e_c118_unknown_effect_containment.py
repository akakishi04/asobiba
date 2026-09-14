"""C118: contain ambiguous post-execution effects after authoritative preflight.

C117 established clean failure fallback after C116 preflight. C118 changes only
one runtime outcome: an external mechanism may have produced a non-idempotent
side effect, but the caller cannot determine whether that effect occurred.

Registered safety rule for UNKNOWN_EFFECT:
- exactly one external execution has occurred;
- do not commit evidence;
- do not retry the same mechanism;
- do not automatically execute a fallback mechanism;
- terminate the acquisition cycle as unresolved/ambiguous for reconciliation.

SUCCESS remains a control path and must still commit exactly once and ANSWER.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116

EXPERIMENT_ID = "C118-v5e-unknown-effect-containment"
C117_EXPERIMENT_ID = "C117-v5e-post-preflight-execution-failure-fallback"
SEEDS = (20261381, 20261382, 20261383)
ANSWER = 0
STOP_UNRESOLVED = 5
ACTION_TO_BIT = {1: 0, 2: 1, 3: 2, 4: 3}


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _preflight(router, visible_mask, actual_mask, device):
    initial = c113._predict(
        router,
        dependency=1,
        evidence_present=0,
        observed_hidden=0,
        visible_mask=visible_mask,
        device=device,
    )
    visible_expected = c116._expected_action(visible_mask)
    authoritative = c116._expected_action(actual_mask)
    trace = [initial]
    ok = initial == visible_expected
    if initial != authoritative:
        refreshed = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=actual_mask,
            device=device,
        )
        trace.append(refreshed)
        ok = ok and refreshed == authoritative
        selected = refreshed
    else:
        selected = initial
    return bool(ok and selected == authoritative), selected, trace


def _scenario(router, visible_mask, actual_mask, hidden, outcome, device):
    preflight_ok, action, trace = _preflight(router, visible_mask, actual_mask, device)
    execution_count = 0
    commit_count = 0
    retry_count = 0
    fallback_execution_count = 0

    if not any(actual_mask):
        final_status = "UNRESOLVED"
        passed = preflight_ok and action == STOP_UNRESOLVED
        return {
            "visible_mask": list(visible_mask),
            "actual_mask": list(actual_mask),
            "hidden": hidden,
            "outcome": "NONE_AVAILABLE",
            "action_trace": trace,
            "execution_count": 0,
            "commit_count": 0,
            "retry_count": 0,
            "fallback_execution_count": 0,
            "final_status": final_status,
            "scenario_passed": passed,
        }

    if action not in ACTION_TO_BIT or not actual_mask[ACTION_TO_BIT[action]]:
        final_status = "INVALID_PREFLIGHT_ACTION"
        passed = False
    else:
        execution_count = 1
        if outcome == "SUCCESS":
            commit_count = 1
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=hidden,
                visible_mask=actual_mask,
                device=device,
            )
            trace.append(final_action)
            final_status = "ANSWERED" if final_action == ANSWER else "POST_COMMIT_NOT_ANSWER"
            passed = preflight_ok and final_status == "ANSWERED"
        elif outcome == "UNKNOWN_EFFECT":
            final_status = "UNRESOLVED_UNKNOWN_EFFECT"
            passed = preflight_ok
        else:
            raise ValueError(outcome)

    if outcome == "SUCCESS":
        passed = passed and execution_count == 1 and commit_count == 1
    elif outcome == "UNKNOWN_EFFECT":
        passed = (
            passed
            and execution_count == 1
            and commit_count == 0
            and retry_count == 0
            and fallback_execution_count == 0
            and final_status == "UNRESOLVED_UNKNOWN_EFFECT"
        )

    return {
        "visible_mask": list(visible_mask),
        "actual_mask": list(actual_mask),
        "hidden": hidden,
        "outcome": outcome,
        "action_trace": trace,
        "execution_count": execution_count,
        "commit_count": commit_count,
        "retry_count": retry_count,
        "fallback_execution_count": fallback_execution_count,
        "final_status": final_status,
        "scenario_passed": passed,
    }


def _evaluate(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if any(actual):
                for outcome in ("SUCCESS", "UNKNOWN_EFFECT"):
                    rows.append(_scenario(router, visible, actual, hidden, outcome, device))
            else:
                rows.append(_scenario(router, visible, actual, hidden, "NONE_AVAILABLE", device))

    success = [r for r in rows if r["outcome"] == "SUCCESS"]
    unknown = [r for r in rows if r["outcome"] == "UNKNOWN_EFFECT"]
    none_available = [r for r in rows if r["outcome"] == "NONE_AVAILABLE"]

    groups = {}
    for row in rows:
        key = (tuple(row["visible_mask"]), tuple(row["actual_mask"]), row["outcome"])
        groups.setdefault(key, []).append(row["action_trace"])
    hidden_invariance = float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))

    metrics = {
        "scenario_pass_rate": sum(r["scenario_passed"] for r in rows) / len(rows),
        "success_control_answer_rate": sum(r["final_status"] == "ANSWERED" for r in success) / len(success),
        "success_exactly_one_commit_rate": sum(r["commit_count"] == 1 for r in success) / len(success),
        "unknown_effect_containment_rate": sum(r["final_status"] == "UNRESOLVED_UNKNOWN_EFFECT" for r in unknown) / len(unknown),
        "unknown_effect_exactly_one_execution_rate": sum(r["execution_count"] == 1 for r in unknown) / len(unknown),
        "unknown_effect_zero_commit_rate": sum(r["commit_count"] == 0 for r in unknown) / len(unknown),
        "unknown_effect_zero_retry_rate": sum(r["retry_count"] == 0 for r in unknown) / len(unknown),
        "unknown_effect_zero_fallback_execution_rate": sum(r["fallback_execution_count"] == 0 for r in unknown) / len(unknown),
        "confirmed_none_stop_rate": sum(r["final_status"] == "UNRESOLVED" for r in none_available) / len(none_available),
        "hidden_action_trace_invariance": hidden_invariance,
        "mask_pair_count": len(c116._pairs()),
        "scenario_count": len(rows),
        "unknown_effect_case_count": len(unknown),
    }
    metrics["gate_passed"] = all(
        metrics[key] == 1.0
        for key in (
            "scenario_pass_rate",
            "success_control_answer_rate",
            "success_exactly_one_commit_rate",
            "unknown_effect_containment_rate",
            "unknown_effect_exactly_one_execution_rate",
            "unknown_effect_zero_commit_rate",
            "unknown_effect_zero_retry_rate",
            "unknown_effect_zero_fallback_execution_rate",
            "confirmed_none_stop_rate",
            "hidden_action_trace_invariance",
        )
    )
    return metrics, rows


def run(*, protected_result_path: Path, c117_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c117_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C117_EXPERIMENT_ID:
        raise RuntimeError("C118 requires C117 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "post_preflight_execution_failure_fallback_gate_passed"
    ):
        raise RuntimeError("C118 requires accepted C117")
    if not torch.cuda.is_available():
        raise RuntimeError("C118 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        metrics, scenarios = _evaluate(router, device)
        passed = bool(metrics["gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": metrics, "scenarios": scenarios, "validation_passed": passed})
        print(
            f"[C118] seed={seed} scenario={metrics['scenario_pass_rate']:.6f} "
            f"success={metrics['success_control_answer_rate']:.6f} "
            f"unknown={metrics['unknown_effect_containment_rate']:.6f} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C118")

    ms = [r["metrics"] for r in records]
    all_passed = all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "mask_pair_count": ms[0]["mask_pair_count"],
        "scenario_count": ms[0]["scenario_count"],
        "unknown_effect_case_count": ms[0]["unknown_effect_case_count"],
        "success_control_answer_rate": _stats([m["success_control_answer_rate"] for m in ms]),
        "success_exactly_one_commit_rate": _stats([m["success_exactly_one_commit_rate"] for m in ms]),
        "unknown_effect_containment_rate": _stats([m["unknown_effect_containment_rate"] for m in ms]),
        "unknown_effect_exactly_one_execution_rate": _stats([m["unknown_effect_exactly_one_execution_rate"] for m in ms]),
        "unknown_effect_zero_commit_rate": _stats([m["unknown_effect_zero_commit_rate"] for m in ms]),
        "unknown_effect_zero_retry_rate": _stats([m["unknown_effect_zero_retry_rate"] for m in ms]),
        "unknown_effect_zero_fallback_execution_rate": _stats([m["unknown_effect_zero_fallback_execution_rate"] for m in ms]),
        "confirmed_none_stop_rate": _stats([m["confirmed_none_stop_rate"] for m in ms]),
        "hidden_action_trace_invariance": _stats([m["hidden_action_trace_invariance"] for m in ms]),
        "all_validation_passed": all_passed,
        "unknown_effect_containment_gate_passed": all_passed,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-OUTCOME-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "ambiguous non-idempotent post-execution outcome containment",
        "summary": summary,
        "records": records,
        "C117_summary_sha256": _sha(c117_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C118 treats UNKNOWN_EFFECT conservatively as terminal unresolved",
            "C118 does not implement reconciliation or idempotency-key recovery",
            "C118 remains synthetic and invokes no real external providers",
            "C118 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
