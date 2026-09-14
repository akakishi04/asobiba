"""C105: execute learned acquisition-mechanism selection as a closed loop.

C104 established snapshot selection among:

    ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED

C105 asks one question: can the learned selector execute those choices under
runtime-owned eligibility and mechanism outcomes, falling back to the next
least-burden eligible mechanism after a failed attempt, while committing evidence
only on SUCCESS?

For each required missing-evidence case and eligibility mask, C105 evaluates:
- success at each eligible mechanism position after a prefix of failures;
- exhaustion where all eligible mechanisms fail;
- answerable rows, which must not acquire at all.

The runtime removes a failed mechanism from the eligibility mask. This makes a
retry of the same failed mechanism illegal. The acquisition budget is four, one
attempt per registered mechanism at most.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks.gate_e_acquisition_failure_oracle import (
    DENIED,
    INVALID,
    UNAVAILABLE,
)
from fold_lm.v05_benchmarks.gate_e_acquisition_mechanism_oracle import (
    ANSWER,
    ASK_USER,
    MECHANISMS,
    OBSERVE,
    READ_MEMORY,
    RETRIEVE,
    STOP_UNRESOLVED,
    _oracle_action,
)
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    _direct_answer,
    _visible_signature,
)
from fold_lm.v05_benchmarks.gate_e_supervised_acquisition_mechanism_selector import (
    ACTION_COUNT,
    CONTROL_WIDTH,
    HIDDEN_WIDTH,
    LR,
    PER_CLASS_BATCH,
    TRAIN_BASES,
    TRAIN_STEPS,
    VALIDATION_BASES,
    WIDTH,
    _balanced_indices,
    _leakage_check,
    _rows_for_bases,
    _tensorize,
)

EXPERIMENT_ID = "C105-v5e-learned-acquisition-mechanism-closed-loop"
C104_EXPERIMENT_ID = "C104-v5e-supervised-acquisition-mechanism-selector"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261221, 20261222, 20261223)
ACQUISITION_BUDGET = len(MECHANISMS)

ACTION_TO_BIT = {
    READ_MEMORY: 0,
    RETRIEVE: 1,
    OBSERVE: 2,
    ASK_USER: 3,
}
FAILURE_OUTCOME = {
    READ_MEMORY: UNAVAILABLE,
    RETRIEVE: DENIED,
    OBSERVE: INVALID,
    ASK_USER: UNAVAILABLE,
}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _train_router(seed: int, device: torch.device):
    train_rows = _rows_for_bases(TRAIN_BASES)
    train = _tensorize(train_rows, device)
    _leakage_check(train_rows, train)
    torch.manual_seed(seed)
    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=WIDTH,
            control_width=CONTROL_WIDTH,
            operation_vocab_size=1,
            hidden_width=HIDDEN_WIDTH,
            action_count=ACTION_COUNT,
        )
    ).to(device)
    optimizer = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    working, context, operation_ids, labels = train
    router.train()
    loss = None
    for _step in range(TRAIN_STEPS):
        index = _balanced_indices(labels, generator, device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            working.index_select(0, index),
            context.index_select(0, index),
            operation_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError(f"C105 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()
    router.eval()
    return router, float(loss.detach().item())


def _predict(router, visible, eligible_mask, device: torch.device) -> int:
    working = torch.zeros(1, 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.zeros(1, dtype=torch.int64, device=device)
    base, dependency, evidence_present, observed_hidden = visible
    working[0, 0, 0] = float(base) / 3.0
    working[0, 0, 1] = float(dependency)
    working[0, 0, 2] = float(evidence_present)
    working[0, 0, 3] = float(observed_hidden)
    for bit, eligible in enumerate(eligible_mask):
        context[0, 0, bit] = float(eligible)
    with torch.inference_mode():
        return int(router(working, context, operation_ids).argmax(dim=-1).item())


def _ordered_eligible(mask):
    return [action for (action, _name), eligible in zip(MECHANISMS, mask) if eligible]


def _scenario_names(mask):
    ordered = _ordered_eligible(mask)
    if not ordered:
        return [("none_available", None)]
    scenarios = [(f"success_at_{index}", index) for index in range(len(ordered))]
    scenarios.append(("all_fail", None))
    return scenarios


def _evaluate_scenario(router, row, initial_mask, scenario_name, success_index, device):
    visible = tuple(row["visible"])
    mask = list(initial_mask)
    remaining_budget = ACQUISITION_BUDGET
    action_trace = []
    attempt_trace = []
    evidence_commit_count = 0
    failure_no_commit_count = 0
    ineligible_action_count = 0
    repeated_failed_mechanism_count = 0
    budget_violation_count = 0
    ask_user_before_self_service_exhausted_count = 0
    failed_actions = set()
    final_answer = None
    final_status = "UNSET"

    ordered_initial = _ordered_eligible(initial_mask)
    successful_action = None
    if success_index is not None:
        successful_action = ordered_initial[success_index]

    for _decision in range(ACQUISITION_BUDGET + 2):
        action = _predict(router, visible, tuple(mask), device)
        action_trace.append(action)
        oracle_now = _oracle_action(int(row["dependency"]), int(visible[2]), tuple(mask))

        if action == ANSWER:
            final_answer = _direct_answer(*visible)
            final_status = "ANSWERED"
            break
        if action == STOP_UNRESOLVED:
            final_status = "UNRESOLVED"
            break
        if action not in ACTION_TO_BIT:
            final_status = "INVALID_ACTION"
            break

        bit = ACTION_TO_BIT[action]
        if mask[bit] == 0:
            ineligible_action_count += 1
            final_status = "INELIGIBLE_ACTION"
            break
        if action in failed_actions:
            repeated_failed_mechanism_count += 1
            final_status = "REPEATED_FAILED_MECHANISM"
            break
        if action == ASK_USER and any(mask[:3]):
            ask_user_before_self_service_exhausted_count += 1

        if remaining_budget <= 0:
            budget_violation_count += 1
            final_status = "BUDGET_EXHAUSTED"
            break
        remaining_budget -= 1

        expected_action = oracle_now
        attempt_success = action == successful_action and scenario_name != "all_fail"
        if scenario_name == "none_available":
            attempt_success = False

        if attempt_success:
            evidence_commit_count += 1
            visible = _visible_signature(
                int(row["base"]), int(row["dependency"]), 1, int(row["hidden"])
            )
            attempt_trace.append(
                {
                    "action": action,
                    "expected_action": expected_action,
                    "outcome": "SUCCESS",
                    "evidence_committed": True,
                }
            )
        else:
            failure_no_commit_count += 1
            failed_actions.add(action)
            mask[bit] = 0
            attempt_trace.append(
                {
                    "action": action,
                    "expected_action": expected_action,
                    "outcome": FAILURE_OUTCOME[action],
                    "evidence_committed": False,
                }
            )
    else:
        final_status = "DECISION_LOOP_LIMIT"

    if remaining_budget < 0 or len(attempt_trace) > ACQUISITION_BUDGET:
        budget_violation_count += 1

    expected_success = success_index is not None
    if expected_success:
        expected_terminal_status = "ANSWERED"
        final_correct = final_answer == row["target"]
    elif initial_mask and any(initial_mask):
        expected_terminal_status = "UNRESOLVED"
        final_correct = final_status == "UNRESOLVED"
    else:
        expected_terminal_status = "UNRESOLVED"
        final_correct = final_status == "UNRESOLVED"

    minimum_burden_trace_ok = all(
        attempt["action"] == attempt["expected_action"] for attempt in attempt_trace
    )
    passed = (
        final_status == expected_terminal_status
        and bool(final_correct)
        and ineligible_action_count == 0
        and repeated_failed_mechanism_count == 0
        and budget_violation_count == 0
        and ask_user_before_self_service_exhausted_count == 0
        and minimum_burden_trace_ok
        and evidence_commit_count == (1 if expected_success else 0)
    )
    return {
        "scenario": scenario_name,
        "success_index": success_index,
        "initial_mask": list(initial_mask),
        "action_trace": action_trace,
        "attempt_trace": attempt_trace,
        "evidence_commit_count": evidence_commit_count,
        "failure_no_commit_count": failure_no_commit_count,
        "ineligible_action_count": ineligible_action_count,
        "repeated_failed_mechanism_count": repeated_failed_mechanism_count,
        "budget_violation_count": budget_violation_count,
        "ask_user_before_self_service_exhausted_count": ask_user_before_self_service_exhausted_count,
        "minimum_burden_trace_ok": minimum_burden_trace_ok,
        "final_status": final_status,
        "final_answer": final_answer,
        "target": row["target"],
        "expected_success": expected_success,
        "scenario_passed": passed,
    }


def _evaluate_closed_loop(router, device: torch.device):
    validation_rows = _rows_for_bases(VALIDATION_BASES)
    initial_rows = []
    seen = set()
    for row in validation_rows:
        key = (
            row["base"], row["dependency"], row["hidden"], row["evidence_present"], row["eligible_mask"]
        )
        if key not in seen:
            seen.add(key)
            initial_rows.append(row)

    records = []
    answerable_total = 0
    answerable_answered = 0
    answerable_acquisitions = 0
    required_scenarios = 0
    required_passed = 0
    eventual_success_total = 0
    eventual_success_answered = 0
    eventual_success_correct = 0
    all_fail_total = 0
    all_fail_stopped = 0
    failure_attempt_total = 0
    failure_attempt_no_commit = 0
    ineligible_count = 0
    repeated_count = 0
    budget_violations = 0
    premature_user_questions = 0
    burden_trace_total = 0
    burden_trace_passed = 0

    hidden_trace_groups = {}

    for row in initial_rows:
        answerable = row["dependency"] == 0 or row["evidence_present"] == 1
        mask = tuple(row["eligible_mask"])
        if answerable:
            answerable_total += 1
            action = _predict(router, tuple(row["visible"]), mask, device)
            if action == ANSWER:
                answerable_answered += 1
            if action in ACTION_TO_BIT:
                answerable_acquisitions += 1
            records.append(
                {
                    "base": row["base"],
                    "dependency": row["dependency"],
                    "hidden": row["hidden"],
                    "evidence_present": row["evidence_present"],
                    "initial_mask": list(mask),
                    "scenario": "answerable",
                    "action_trace": [action],
                    "scenario_passed": action == ANSWER,
                }
            )
            continue

        for scenario_name, success_index in _scenario_names(mask):
            result = _evaluate_scenario(
                router, row, mask, scenario_name, success_index, device
            )
            result.update(
                {
                    "base": row["base"],
                    "dependency": row["dependency"],
                    "hidden": row["hidden"],
                    "evidence_present": row["evidence_present"],
                }
            )
            records.append(result)
            required_scenarios += 1
            required_passed += int(result["scenario_passed"])
            ineligible_count += result["ineligible_action_count"]
            repeated_count += result["repeated_failed_mechanism_count"]
            budget_violations += result["budget_violation_count"]
            premature_user_questions += result["ask_user_before_self_service_exhausted_count"]
            burden_trace_total += 1
            burden_trace_passed += int(result["minimum_burden_trace_ok"])
            for attempt in result["attempt_trace"]:
                if attempt["outcome"] != "SUCCESS":
                    failure_attempt_total += 1
                    failure_attempt_no_commit += int(not attempt["evidence_committed"])

            if result["expected_success"]:
                eventual_success_total += 1
                eventual_success_answered += int(result["final_status"] == "ANSWERED")
                eventual_success_correct += int(result["final_answer"] == result["target"])
            else:
                all_fail_total += 1
                all_fail_stopped += int(result["final_status"] == "UNRESOLVED")

            group_key = (mask, scenario_name, success_index)
            hidden_trace_groups.setdefault(group_key, []).append(result["action_trace"])

    hidden_invariance = 1.0
    for traces in hidden_trace_groups.values():
        if len(traces) != 2 or traces[0] != traces[1]:
            hidden_invariance = 0.0
            break

    metrics = {
        "answerable_answer_rate": answerable_answered / answerable_total,
        "answerable_zero_acquisition_rate": (answerable_total - answerable_acquisitions) / answerable_total,
        "required_scenario_pass_rate": required_passed / required_scenarios,
        "per_decision_minimum_burden_rate": burden_trace_passed / burden_trace_total,
        "eventual_success_answer_rate": eventual_success_answered / eventual_success_total,
        "eventual_success_final_accuracy": eventual_success_correct / eventual_success_total,
        "all_fail_stop_unresolved_rate": all_fail_stopped / all_fail_total,
        "failure_no_evidence_commit_rate": failure_attempt_no_commit / failure_attempt_total,
        "ineligible_mechanism_count": ineligible_count,
        "repeat_failed_mechanism_count": repeated_count,
        "budget_violation_count": budget_violations,
        "ask_user_before_self_service_exhausted_count": premature_user_questions,
        "hidden_counterfactual_action_trace_invariance": hidden_invariance,
    }
    metrics["closed_loop_passed"] = (
        metrics["answerable_answer_rate"] == 1.0
        and metrics["answerable_zero_acquisition_rate"] == 1.0
        and metrics["required_scenario_pass_rate"] == 1.0
        and metrics["per_decision_minimum_burden_rate"] == 1.0
        and metrics["eventual_success_answer_rate"] == 1.0
        and metrics["eventual_success_final_accuracy"] == 1.0
        and metrics["all_fail_stop_unresolved_rate"] == 1.0
        and metrics["failure_no_evidence_commit_rate"] == 1.0
        and metrics["ineligible_mechanism_count"] == 0
        and metrics["repeat_failed_mechanism_count"] == 0
        and metrics["budget_violation_count"] == 0
        and metrics["ask_user_before_self_service_exhausted_count"] == 0
        and metrics["hidden_counterfactual_action_trace_invariance"] == 1.0
    )
    return metrics, records


def run(*, protected_result_path: Path, c104_summary_path: Path, output_dir: Path):
    c104 = json.loads(c104_summary_path.read_text(encoding="utf-8"))
    if c104.get("experiment_id") != C104_EXPERIMENT_ID:
        raise RuntimeError("C105 requires C104 summary")
    if c104.get("status") != "PASS" or not bool(
        c104.get("summary", {}).get("supervised_acquisition_mechanism_selector_gate_passed")
    ):
        raise RuntimeError("C105 requires accepted C104 mechanism selector")
    if not torch.cuda.is_available():
        raise RuntimeError("C105 requires CUDA")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, final_loss = _train_router(seed, device)
        metrics, trajectories = _evaluate_closed_loop(router, device)
        row = {
            "seed": seed,
            "final_loss": final_loss,
            **metrics,
            "trajectory_records": trajectories,
        }
        records.append(row)
        print(
            f"[C105] seed={seed} scenario_pass={metrics['required_scenario_pass_rate']:.6f} "
            f"success={metrics['eventual_success_final_accuracy']:.6f} "
            f"all_fail_stop={metrics['all_fail_stop_unresolved_rate']:.6f} "
            f"repeat={metrics['repeat_failed_mechanism_count']} "
            f"pass={metrics['closed_loop_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C105")

    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "validation_is_unseen_base": True,
        "action_space": [
            "ANSWER",
            "READ_MEMORY",
            "RETRIEVE",
            "OBSERVE",
            "ASK_USER",
            "STOP_UNRESOLVED",
        ],
        "acquisition_budget": ACQUISITION_BUDGET,
        "runtime_removes_failed_mechanism_from_eligibility": True,
        "runtime_owns_outcomes_permissions_and_evidence_commit": True,
        "failure_outcome_by_mechanism": {
            "READ_MEMORY": UNAVAILABLE,
            "RETRIEVE": DENIED,
            "OBSERVE": INVALID,
            "ASK_USER": UNAVAILABLE,
        },
        "answerable_answer_rate": _stats([r["answerable_answer_rate"] for r in records]),
        "answerable_zero_acquisition_rate": _stats([r["answerable_zero_acquisition_rate"] for r in records]),
        "required_scenario_pass_rate": _stats([r["required_scenario_pass_rate"] for r in records]),
        "per_decision_minimum_burden_rate": _stats([r["per_decision_minimum_burden_rate"] for r in records]),
        "eventual_success_answer_rate": _stats([r["eventual_success_answer_rate"] for r in records]),
        "eventual_success_final_accuracy": _stats([r["eventual_success_final_accuracy"] for r in records]),
        "all_fail_stop_unresolved_rate": _stats([r["all_fail_stop_unresolved_rate"] for r in records]),
        "failure_no_evidence_commit_rate": _stats([r["failure_no_evidence_commit_rate"] for r in records]),
        "ineligible_mechanism_count": {
            "sum": sum(r["ineligible_mechanism_count"] for r in records),
            "max": max(r["ineligible_mechanism_count"] for r in records),
        },
        "repeat_failed_mechanism_count": {
            "sum": sum(r["repeat_failed_mechanism_count"] for r in records),
            "max": max(r["repeat_failed_mechanism_count"] for r in records),
        },
        "budget_violation_count": {
            "sum": sum(r["budget_violation_count"] for r in records),
            "max": max(r["budget_violation_count"] for r in records),
        },
        "ask_user_before_self_service_exhausted_count": {
            "sum": sum(r["ask_user_before_self_service_exhausted_count"] for r in records),
            "max": max(r["ask_user_before_self_service_exhausted_count"] for r in records),
        },
        "hidden_counterfactual_action_trace_invariance": _stats(
            [r["hidden_counterfactual_action_trace_invariance"] for r in records]
        ),
        "all_closed_loops_passed": all(r["closed_loop_passed"] for r in records),
    }
    summary["learned_acquisition_mechanism_closed_loop_gate_passed"] = bool(
        summary["all_closed_loops_passed"]
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "learned mechanism selection with runtime fallback closed loop",
        "records": records,
        "summary": summary,
        "C104_summary_sha256": _sha256(c104_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C105 uses synthetic mechanism outcomes rather than real memory/tool/user interactions",
            "runtime eligibility is provided rather than predicted by the model",
            "mechanism burden order remains the synthetic C103 contract",
            "C105 does not estimate expected utility or mechanism success probability",
            "C105 does not establish Gate E passage",
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
    parser.add_argument("--c104-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c104_summary_path=args.c104_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C105 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
