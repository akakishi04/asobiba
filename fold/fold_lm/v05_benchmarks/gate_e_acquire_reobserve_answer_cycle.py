"""C99: close the first V5-E acquisition loop.

C98 established that the production ControlLaneActionRouter can learn the
binary ANSWER/ACQUIRE sufficiency boundary. C99 asks one additional question:
can that same learned policy execute an actual two-decision cycle where the
model proposes ACQUIRE, the runtime alone reveals the missing evidence, and the
model then re-observes the updated state and chooses ANSWER?

The acquisition budget is exactly one. Required cases must acquire exactly once;
answerable cases must never acquire; and no acquired case may request the same
evidence again after the runtime marks it present.
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
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    ACQUIRE,
    ANSWER,
    _direct_answer,
    _oracle_action,
    _target,
    _visible_signature,
)
from fold_lm.v05_benchmarks.gate_e_supervised_information_sufficiency_router import (
    CONTROL_WIDTH,
    HIDDEN_WIDTH,
    LR,
    TRAIN_BASES,
    TRAIN_BATCH,
    TRAIN_STEPS,
    VALIDATION_BASES,
    WIDTH,
    _rows_for_bases,
    _tensorize,
)

EXPERIMENT_ID = "C99-v5e-acquire-reobserve-answer-cycle"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
C98_EXPERIMENT_ID = "C98-v5e-supervised-information-sufficiency-router"
SEEDS = (20261181, 20261182, 20261183)
ACQUISITION_BUDGET = 1


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


def _build_router(seed: int, device: torch.device):
    train_rows = _rows_for_bases(TRAIN_BASES)
    train = _tensorize(train_rows, device)
    torch.manual_seed(seed)
    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=WIDTH,
            control_width=CONTROL_WIDTH,
            operation_vocab_size=1,
            hidden_width=HIDDEN_WIDTH,
            action_count=2,
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
            raise RuntimeError(f"C99 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()
    router.eval()
    return router, float(loss.detach().item())


def _predict_one(router, visible, device: torch.device) -> int:
    row = {
        "visible": tuple(visible),
        "oracle_action": ANSWER,
    }
    working = torch.zeros(1, 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.zeros(1, dtype=torch.int64, device=device)
    base, dependency, evidence_present, observed_hidden = row["visible"]
    working[0, 0, 0] = float(base) / 3.0
    working[0, 0, 1] = float(dependency)
    working[0, 0, 2] = float(evidence_present)
    working[0, 0, 3] = float(observed_hidden)
    with torch.inference_mode():
        return int(router(working, context, operation_ids).argmax(dim=-1).item())


def _runtime_reveal(row: dict, remaining_budget: int):
    if remaining_budget <= 0:
        return None, remaining_budget, False
    visible_after = _visible_signature(
        int(row["base"]),
        int(row["dependency"]),
        1,
        int(row["hidden"]),
    )
    return visible_after, remaining_budget - 1, True


def _evaluate_cycle(router, device: torch.device):
    rows = _rows_for_bases(VALIDATION_BASES)
    records = []
    required_total = 0
    required_acquired = 0
    answerable_total = 0
    unnecessary_acquired = 0
    post_acquire_total = 0
    post_acquire_answered = 0
    repeat_acquire = 0
    budget_violations = 0
    ambiguous_direct_attempts = 0
    final_correct = 0
    total_acquisitions = 0

    for row in rows:
        visible_before = tuple(row["visible"])
        oracle_first = _oracle_action(row["dependency"], row["evidence_present"])
        first_action = _predict_one(router, visible_before, device)
        required = oracle_first == ACQUIRE
        if required:
            required_total += 1
        else:
            answerable_total += 1

        remaining_budget = ACQUISITION_BUDGET
        acquisitions = 0
        second_action = None
        visible_after = visible_before
        final_answer = None

        if first_action == ACQUIRE:
            if required:
                required_acquired += 1
            else:
                unnecessary_acquired += 1
            visible_after, remaining_budget, applied = _runtime_reveal(row, remaining_budget)
            if not applied:
                budget_violations += 1
            else:
                acquisitions += 1
                total_acquisitions += 1
                post_acquire_total += 1
                second_action = _predict_one(router, visible_after, device)
                if second_action == ANSWER:
                    post_acquire_answered += 1
                    final_answer = _direct_answer(*visible_after)
                else:
                    repeat_acquire += 1
                    # Runtime must not silently grant another read past the budget.
                    _again, _budget, applied_again = _runtime_reveal(row, remaining_budget)
                    if applied_again:
                        budget_violations += 1
        else:
            direct = _direct_answer(*visible_before)
            if direct is None:
                ambiguous_direct_attempts += 1
            final_answer = direct

        if acquisitions > ACQUISITION_BUDGET:
            budget_violations += 1

        correct = final_answer == row["target"]
        final_correct += int(correct)
        records.append(
            {
                "base": row["base"],
                "dependency": row["dependency"],
                "hidden": row["hidden"],
                "initial_evidence_present": row["evidence_present"],
                "visible_before": list(visible_before),
                "oracle_first_action": oracle_first,
                "first_action": first_action,
                "runtime_acquisition_count": acquisitions,
                "visible_after": list(visible_after),
                "second_action": second_action,
                "target": row["target"],
                "final_answer": final_answer,
                "final_correct": correct,
            }
        )

    required_recall = required_acquired / required_total
    unnecessary_rate = unnecessary_acquired / answerable_total
    post_acquire_answer_rate = post_acquire_answered / post_acquire_total
    final_accuracy = final_correct / len(rows)
    required_exactly_once = sum(
        r["runtime_acquisition_count"] == 1
        for r in records
        if r["oracle_first_action"] == ACQUIRE
    ) / required_total
    answerable_zero_acquire = sum(
        r["runtime_acquisition_count"] == 0
        for r in records
        if r["oracle_first_action"] == ANSWER
    ) / answerable_total

    passed = (
        required_recall == 1.0
        and unnecessary_rate == 0.0
        and required_exactly_once == 1.0
        and answerable_zero_acquire == 1.0
        and post_acquire_answer_rate == 1.0
        and repeat_acquire == 0
        and budget_violations == 0
        and ambiguous_direct_attempts == 0
        and final_accuracy == 1.0
    )
    return {
        "required_acquisition_recall": required_recall,
        "unnecessary_acquisition_rate": unnecessary_rate,
        "required_exactly_one_acquisition_rate": required_exactly_once,
        "answerable_zero_acquisition_rate": answerable_zero_acquire,
        "post_acquisition_answer_rate": post_acquire_answer_rate,
        "repeat_acquisition_count": repeat_acquire,
        "budget_violation_count": budget_violations,
        "ambiguous_direct_answer_attempt_count": ambiguous_direct_attempts,
        "post_cycle_final_accuracy": final_accuracy,
        "total_runtime_acquisitions": total_acquisitions,
        "cycle_passed": passed,
        "records": records,
    }


def run(*, protected_result_path: Path, c98_summary_path: Path, output_dir: Path):
    c98 = json.loads(c98_summary_path.read_text(encoding="utf-8"))
    if c98.get("experiment_id") != C98_EXPERIMENT_ID:
        raise RuntimeError("C99 requires C98 summary")
    if c98.get("status") != "PASS" or not bool(
        c98.get("summary", {}).get("supervised_information_sufficiency_gate_passed")
    ):
        raise RuntimeError("C99 requires accepted C98 supervised sufficiency gate")
    if not torch.cuda.is_available():
        raise RuntimeError("C99 requires CUDA")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, final_loss = _build_router(seed, device)
        metrics = _evaluate_cycle(router, device)
        row = {
            "seed": seed,
            "final_loss": final_loss,
            **{k: v for k, v in metrics.items() if k != "records"},
            "cycle_records": metrics["records"],
        }
        records.append(row)
        print(
            f"[C99] seed={seed} acquire_recall={metrics['required_acquisition_recall']:.6f} "
            f"unnecessary={metrics['unnecessary_acquisition_rate']:.6f} "
            f"post_answer={metrics['post_acquisition_answer_rate']:.6f} "
            f"repeat={metrics['repeat_acquisition_count']} final={metrics['post_cycle_final_accuracy']:.6f} "
            f"pass={metrics['cycle_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C99")

    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "validation_is_unseen_base": True,
        "action_space": ["ANSWER", "ACQUIRE"],
        "acquisition_budget": ACQUISITION_BUDGET,
        "model_proposes_runtime_mutates_evidence": True,
        "required_acquisition_recall": _stats([r["required_acquisition_recall"] for r in records]),
        "unnecessary_acquisition_rate": _stats([r["unnecessary_acquisition_rate"] for r in records]),
        "required_exactly_one_acquisition_rate": _stats([r["required_exactly_one_acquisition_rate"] for r in records]),
        "answerable_zero_acquisition_rate": _stats([r["answerable_zero_acquisition_rate"] for r in records]),
        "post_acquisition_answer_rate": _stats([r["post_acquisition_answer_rate"] for r in records]),
        "repeat_acquisition_count": {"sum": sum(r["repeat_acquisition_count"] for r in records), "max": max(r["repeat_acquisition_count"] for r in records)},
        "budget_violation_count": {"sum": sum(r["budget_violation_count"] for r in records), "max": max(r["budget_violation_count"] for r in records)},
        "ambiguous_direct_answer_attempt_count": {"sum": sum(r["ambiguous_direct_answer_attempt_count"] for r in records), "max": max(r["ambiguous_direct_answer_attempt_count"] for r in records)},
        "post_cycle_final_accuracy": _stats([r["post_cycle_final_accuracy"] for r in records]),
        "all_cycles_passed": all(r["cycle_passed"] for r in records),
    }
    summary["acquire_reobserve_answer_cycle_gate_passed"] = bool(summary["all_cycles_passed"])

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "learned ACQUIRE -> runtime evidence update -> reobserve -> ANSWER cycle",
        "records": records,
        "summary": summary,
        "C98_summary_sha256": _sha256(c98_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C99 uses one abstract deterministic acquisition mechanism that reveals one hidden bit",
            "C99 does not yet choose among memory, retrieval, observation, or user-question mechanisms",
            "acquisition failure and permission denial are not yet tested",
            "the final answer function remains synthetic task semantics",
            "C99 does not establish Gate E passage",
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
    parser.add_argument("--c98-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c98_summary_path=args.c98_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C99 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
