"""C102: execute the learned V5-E acquisition-outcome policy as a closed loop.

C101 showed that snapshot states can be classified into ANSWER, ACQUIRE, and
STOP_UNRESOLVED. C102 evaluates the actual trajectory on unseen base=3:

    initial state
      -> predicted ANSWER, or predicted ACQUIRE
      -> runtime applies SUCCESS / UNAVAILABLE / DENIED / INVALID
      -> only SUCCESS commits evidence
      -> router re-observes authoritative state + runtime-owned outcome token
      -> predicted ANSWER or STOP_UNRESOLVED

The acquisition budget is one. Failed/untrusted outcomes may not commit evidence,
may not trigger a guessed answer, and may not be retried.
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
    ACQUISITION_BUDGET,
    FAILURE_OUTCOMES,
    NOT_ATTEMPTED,
    OUTCOMES,
    STOP_UNRESOLVED,
    SUCCESS,
    _oracle_action,
    _runtime_apply_outcome,
)
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    ACQUIRE,
    ANSWER,
    _direct_answer,
)
from fold_lm.v05_benchmarks.gate_e_supervised_acquisition_outcome_policy import (
    ACTION_COUNT,
    CONTROL_WIDTH,
    HIDDEN_WIDTH,
    LR,
    OUTCOME_TO_ID,
    TRAIN_BASES,
    TRAIN_BATCH,
    TRAIN_STEPS,
    VALIDATION_BASES,
    WIDTH,
    _build_rows,
    _leakage_check,
    _tensorize,
)

EXPERIMENT_ID = "C102-v5e-learned-acquisition-outcome-closed-loop"
C101_EXPERIMENT_ID = "C101-v5e-supervised-acquisition-outcome-policy"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261201, 20261202, 20261203)


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
    train_rows = _build_rows(TRAIN_BASES)
    train = _tensorize(train_rows, device)
    _leakage_check(train_rows, train)

    torch.manual_seed(seed)
    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=WIDTH,
            control_width=CONTROL_WIDTH,
            operation_vocab_size=len(OUTCOME_TO_ID),
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
        index = torch.randint(len(train_rows), (TRAIN_BATCH,), generator=generator).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            working.index_select(0, index),
            context.index_select(0, index),
            operation_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError(f"C102 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()
    del optimizer
    router.eval()
    return router, float(loss.detach().item())


def _predict(router, visible, outcome: str, device: torch.device) -> int:
    working = torch.zeros(1, 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.tensor(
        [OUTCOME_TO_ID[outcome]], dtype=torch.int64, device=device
    )
    base, dependency, evidence_present, observed_hidden = visible
    working[0, 0, 0] = float(base) / 3.0
    working[0, 0, 1] = float(dependency)
    working[0, 0, 2] = float(evidence_present)
    working[0, 0, 3] = float(observed_hidden)
    with torch.inference_mode():
        return int(router(working, context, operation_ids).argmax(dim=-1).item())


def _initial_validation_rows():
    return [row for row in _build_rows(VALIDATION_BASES) if row["phase"] == "initial"]


def _evaluate_closed_loop(router, device: torch.device):
    initial_rows = _initial_validation_rows()
    records = []

    required_total = 0
    required_acquired = 0
    answerable_total = 0
    answerable_answered = 0
    unnecessary_acquire = 0
    premature_stop = 0

    success_total = 0
    success_committed = 0
    success_answered = 0
    success_correct = 0

    failure_total = 0
    failure_stopped = 0
    failure_no_commit = 0
    failure_no_guess = 0

    repeat_acquire = 0
    budget_violations = 0
    total_acquisitions = 0

    for row in initial_rows:
        visible_before = tuple(row["visible"])
        oracle_first = _oracle_action(
            int(row["dependency"]), int(visible_before[2]), NOT_ATTEMPTED
        )
        required = oracle_first == ACQUIRE
        outcomes = OUTCOMES if required else (None,)

        for outcome in outcomes:
            first_action = _predict(router, visible_before, NOT_ATTEMPTED, device)
            remaining_budget = ACQUISITION_BUDGET
            acquisition_count = 0
            evidence_commit_count = 0
            second_action = None
            final_answer = None
            final_status = "UNSET"
            guessed_after_failure = False

            if required:
                required_total += 1
            else:
                answerable_total += 1

            if first_action == ANSWER:
                if required:
                    direct = _direct_answer(*visible_before)
                    # Required rows have unresolved evidence, so any ANSWER is a guess.
                    final_answer = direct
                    final_status = "GUESSED_OR_AMBIGUOUS"
                else:
                    answerable_answered += 1
                    final_answer = _direct_answer(*visible_before)
                    final_status = "ANSWERED"
            elif first_action == ACQUIRE:
                if not required:
                    unnecessary_acquire += 1
                    final_status = "UNNECESSARY_ACQUIRE"
                else:
                    required_acquired += 1
                    if outcome is None:
                        raise RuntimeError("C102 required acquisition missing outcome")
                    visible_after, remaining_budget, applied, committed = _runtime_apply_outcome(
                        {
                            "base": row["base"],
                            "dependency": row["dependency"],
                            "hidden": row["hidden"],
                            "evidence_present": int(visible_before[2]),
                            "visible": visible_before,
                            "target": row["target"],
                        },
                        outcome,
                        remaining_budget,
                    )
                    if not applied:
                        budget_violations += 1
                        final_status = "ACQUIRE_NOT_APPLIED"
                    else:
                        acquisition_count += 1
                        total_acquisitions += 1
                        evidence_commit_count += int(committed)
                        second_action = _predict(router, visible_after, outcome, device)

                        if outcome == SUCCESS:
                            success_total += 1
                            success_committed += int(committed)
                            if second_action == ANSWER:
                                success_answered += 1
                                final_answer = _direct_answer(*visible_after)
                                final_status = "ANSWERED"
                                success_correct += int(final_answer == row["target"])
                            elif second_action == ACQUIRE:
                                repeat_acquire += 1
                                final_status = "REPEAT_ACQUIRE"
                            else:
                                final_status = "PREMATURE_UNRESOLVED_AFTER_SUCCESS"
                        else:
                            failure_total += 1
                            failure_no_commit += int(not committed)
                            if second_action == STOP_UNRESOLVED:
                                failure_stopped += 1
                                failure_no_guess += 1
                                final_status = "UNRESOLVED"
                            elif second_action == ACQUIRE:
                                repeat_acquire += 1
                                failure_no_guess += 1
                                final_status = "REPEAT_ACQUIRE"
                            else:
                                guessed_after_failure = True
                                final_answer = _direct_answer(*visible_after)
                                final_status = "GUESSED_AFTER_FAILURE"
            elif first_action == STOP_UNRESOLVED:
                premature_stop += 1
                final_status = "PREMATURE_STOP"
            else:
                raise RuntimeError(f"C102 unknown first action {first_action}")

            if acquisition_count > ACQUISITION_BUDGET or remaining_budget < 0:
                budget_violations += 1

            if outcome in FAILURE_OUTCOMES and guessed_after_failure:
                # Explicitly not counted in failure_no_guess.
                pass

            records.append(
                {
                    "base": row["base"],
                    "dependency": row["dependency"],
                    "hidden": row["hidden"],
                    "initial_evidence_present": visible_before[2],
                    "outcome": outcome,
                    "oracle_first_action": oracle_first,
                    "first_action": first_action,
                    "second_action": second_action,
                    "runtime_acquisition_count": acquisition_count,
                    "evidence_commit_count": evidence_commit_count,
                    "remaining_budget": remaining_budget,
                    "final_status": final_status,
                    "final_answer": final_answer,
                    "target": row["target"],
                }
            )

    required_recall = required_acquired / required_total
    answerable_answer_rate = answerable_answered / answerable_total
    unnecessary_rate = unnecessary_acquire / answerable_total
    success_commit_rate = success_committed / success_total
    success_answer_rate = success_answered / success_total
    success_accuracy = success_correct / success_total
    failure_stop_rate = failure_stopped / failure_total
    failure_no_commit_rate = failure_no_commit / failure_total
    failure_no_guess_rate = failure_no_guess / failure_total

    passed = (
        required_recall == 1.0
        and answerable_answer_rate == 1.0
        and unnecessary_rate == 0.0
        and premature_stop == 0
        and success_commit_rate == 1.0
        and success_answer_rate == 1.0
        and success_accuracy == 1.0
        and failure_stop_rate == 1.0
        and failure_no_commit_rate == 1.0
        and failure_no_guess_rate == 1.0
        and repeat_acquire == 0
        and budget_violations == 0
    )

    return {
        "initial_required_acquisition_recall": required_recall,
        "initial_answerable_answer_rate": answerable_answer_rate,
        "initial_unnecessary_acquisition_rate": unnecessary_rate,
        "premature_stop_count": premature_stop,
        "success_evidence_commit_rate": success_commit_rate,
        "success_post_acquisition_answer_rate": success_answer_rate,
        "success_final_accuracy": success_accuracy,
        "failure_stop_unresolved_rate": failure_stop_rate,
        "failure_no_evidence_commit_rate": failure_no_commit_rate,
        "failure_no_guessed_answer_rate": failure_no_guess_rate,
        "repeat_acquisition_count": repeat_acquire,
        "budget_violation_count": budget_violations,
        "total_runtime_acquisitions": total_acquisitions,
        "closed_loop_passed": passed,
        "records": records,
    }


def run(*, protected_result_path: Path, c101_summary_path: Path, output_dir: Path):
    c101 = json.loads(c101_summary_path.read_text(encoding="utf-8"))
    if c101.get("experiment_id") != C101_EXPERIMENT_ID:
        raise RuntimeError("C102 requires C101 summary")
    if c101.get("status") != "PASS" or not bool(
        c101.get("summary", {}).get("supervised_acquisition_outcome_policy_gate_passed")
    ):
        raise RuntimeError("C102 requires accepted C101 learned outcome policy")
    if not torch.cuda.is_available():
        raise RuntimeError("C102 requires CUDA")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, final_loss = _train_router(seed, device)
        metrics = _evaluate_closed_loop(router, device)
        row = {
            "seed": seed,
            "final_loss": final_loss,
            **{k: v for k, v in metrics.items() if k != "records"},
            "cycle_records": metrics["records"],
        }
        records.append(row)
        print(
            f"[C102] seed={seed} acquire={metrics['initial_required_acquisition_recall']:.6f} "
            f"success_answer={metrics['success_post_acquisition_answer_rate']:.6f} "
            f"failure_stop={metrics['failure_stop_unresolved_rate']:.6f} "
            f"repeat={metrics['repeat_acquisition_count']} "
            f"pass={metrics['closed_loop_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C102")

    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "validation_is_unseen_base": True,
        "action_space": ["ANSWER", "ACQUIRE", "STOP_UNRESOLVED"],
        "acquisition_outcomes": list(OUTCOMES),
        "acquisition_budget": ACQUISITION_BUDGET,
        "model_proposes_runtime_owns_outcome_and_evidence_mutation": True,
        "initial_required_acquisition_recall": _stats(
            [r["initial_required_acquisition_recall"] for r in records]
        ),
        "initial_answerable_answer_rate": _stats(
            [r["initial_answerable_answer_rate"] for r in records]
        ),
        "initial_unnecessary_acquisition_rate": _stats(
            [r["initial_unnecessary_acquisition_rate"] for r in records]
        ),
        "success_evidence_commit_rate": _stats(
            [r["success_evidence_commit_rate"] for r in records]
        ),
        "success_post_acquisition_answer_rate": _stats(
            [r["success_post_acquisition_answer_rate"] for r in records]
        ),
        "success_final_accuracy": _stats([r["success_final_accuracy"] for r in records]),
        "failure_stop_unresolved_rate": _stats(
            [r["failure_stop_unresolved_rate"] for r in records]
        ),
        "failure_no_evidence_commit_rate": _stats(
            [r["failure_no_evidence_commit_rate"] for r in records]
        ),
        "failure_no_guessed_answer_rate": _stats(
            [r["failure_no_guessed_answer_rate"] for r in records]
        ),
        "premature_stop_count": {
            "sum": sum(r["premature_stop_count"] for r in records),
            "max": max(r["premature_stop_count"] for r in records),
        },
        "repeat_acquisition_count": {
            "sum": sum(r["repeat_acquisition_count"] for r in records),
            "max": max(r["repeat_acquisition_count"] for r in records),
        },
        "budget_violation_count": {
            "sum": sum(r["budget_violation_count"] for r in records),
            "max": max(r["budget_violation_count"] for r in records),
        },
        "all_closed_loops_passed": all(r["closed_loop_passed"] for r in records),
    }
    summary["learned_acquisition_outcome_closed_loop_gate_passed"] = bool(
        summary["all_closed_loops_passed"]
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "learned end-to-end acquisition success/failure closed loop",
        "records": records,
        "summary": summary,
        "C101_summary_sha256": _sha256(c101_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C102 still uses abstract synthetic acquisition outcomes",
            "C102 does not choose among memory, retrieval, observation, or user-question mechanisms",
            "C102 does not test retrying through a different acquisition mechanism",
            "the final answer function remains synthetic task semantics",
            "C102 does not establish Gate E passage",
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
    parser.add_argument("--c101-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c101_summary_path=args.c101_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C102 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
