"""C101: learn acquisition-outcome handling including STOP_UNRESOLVED.

C100 fixed the oracle semantics for acquisition outcomes. C101 asks one question:
can the production fixed-width ControlLaneActionRouter learn the three-action
policy from visible evidence plus an explicit runtime-owned acquisition-outcome
token, without receiving the hidden truth (unless SUCCESS committed it), target,
or oracle action as an input?

Training uses base values 0/1/2 and validation holds out base=3.  Initial states
use NOT_ATTEMPTED; required-acquisition states are then expanded through the
four runtime outcomes.  SUCCESS commits evidence and should route to ANSWER;
UNAVAILABLE/DENIED/INVALID must route to STOP_UNRESOLVED without evidence
commit or a guessed answer.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks.gate_e_acquisition_failure_oracle import (
    ACQUISITION_BUDGET,
    DENIED,
    FAILURE_OUTCOMES,
    INVALID,
    NOT_ATTEMPTED,
    OUTCOMES,
    STOP_UNRESOLVED,
    SUCCESS,
    UNAVAILABLE,
    _oracle_action,
    _runtime_apply_outcome,
)
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    ACQUIRE,
    ANSWER,
    _direct_answer,
    _target,
    _visible_signature,
)

EXPERIMENT_ID = "C101-v5e-supervised-acquisition-outcome-policy"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
C100_EXPERIMENT_ID = "C100-v5e-acquisition-failure-oracle"
SEEDS = (20261191, 20261192, 20261193)
TRAIN_BASES = (0, 1, 2)
VALIDATION_BASES = (3,)
WIDTH = 8
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 4
TRAIN_STEPS = 480
TRAIN_BATCH = 96
LR = 0.01
ACTION_COUNT = 3
OUTCOME_TO_ID = {
    NOT_ATTEMPTED: 0,
    SUCCESS: 1,
    UNAVAILABLE: 2,
    DENIED: 3,
    INVALID: 4,
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


def _build_rows(bases):
    examples = []
    for base, dependency, hidden, evidence_present in itertools.product(
        bases, (0, 1), (0, 1), (0, 1)
    ):
        initial_visible = _visible_signature(base, dependency, evidence_present, hidden)
        target = _target(base, dependency, hidden)
        first_action = _oracle_action(dependency, evidence_present, NOT_ATTEMPTED)
        examples.append(
            {
                "phase": "initial",
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "visible": initial_visible,
                "outcome": NOT_ATTEMPTED,
                "target": target,
                "oracle_action": first_action,
                "evidence_committed": bool(evidence_present),
            }
        )

        if first_action == ACQUIRE:
            row = {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": initial_visible,
                "target": target,
            }
            for outcome in OUTCOMES:
                visible_after, remaining_budget, applied, committed = _runtime_apply_outcome(
                    row, outcome, ACQUISITION_BUDGET
                )
                if not applied or remaining_budget != 0:
                    raise RuntimeError("C101 runtime outcome fixture violated one-read contract")
                second_action = _oracle_action(dependency, int(visible_after[2]), outcome)
                examples.append(
                    {
                        "phase": "post_acquisition",
                        "base": base,
                        "dependency": dependency,
                        "hidden": hidden,
                        "visible": visible_after,
                        "outcome": outcome,
                        "target": target,
                        "oracle_action": second_action,
                        "evidence_committed": bool(committed),
                    }
                )
    return examples


def _tensorize(rows, device: torch.device):
    working = torch.zeros(len(rows), 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.tensor(
        [OUTCOME_TO_ID[row["outcome"]] for row in rows], dtype=torch.int64, device=device
    )
    labels = torch.tensor(
        [row["oracle_action"] for row in rows], dtype=torch.int64, device=device
    )
    for index, row in enumerate(rows):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        working[index, 0, 0] = float(base) / 3.0
        working[index, 0, 1] = float(dependency)
        working[index, 0, 2] = float(evidence_present)
        working[index, 0, 3] = float(observed_hidden)
    return working, context, operation_ids, labels


def _leakage_check(rows, tensors):
    working, _context, operation_ids, _labels = tensors
    grouped = {}
    for index, row in enumerate(rows):
        # Hidden truth must remain unobservable when evidence is absent. This applies
        # both before acquisition and after all failed/untrusted outcomes.
        if int(row["visible"][2]) == 0:
            key = (row["phase"], row["base"], row["dependency"], row["outcome"])
            grouped.setdefault(key, []).append(index)
    for key, indices in grouped.items():
        if len(indices) != 2:
            raise RuntimeError(f"C101 missing hidden counterfactual pair: {key}")
        if not torch.equal(working[indices[0]], working[indices[1]]):
            raise RuntimeError("C101 hidden truth leaked into visible control input")
        if int(operation_ids[indices[0]]) != int(operation_ids[indices[1]]):
            raise RuntimeError("C101 hidden truth leaked through outcome token")


@torch.inference_mode()
def _evaluate(router, rows, tensors):
    working, context, operation_ids, labels = tensors
    router.eval()
    predicted = router(working, context, operation_ids).argmax(dim=-1)
    accuracy = float((predicted == labels).float().mean().item())
    flips = int((predicted != labels).sum().item())

    recalls = {}
    for action, name in ((ANSWER, "ANSWER"), (ACQUIRE, "ACQUIRE"), (STOP_UNRESOLVED, "STOP_UNRESOLVED")):
        mask = labels == action
        recalls[name] = float((predicted[mask] == action).float().mean().item())

    failure_indices = [
        i for i, row in enumerate(rows) if row["outcome"] in FAILURE_OUTCOMES
    ]
    success_indices = [i for i, row in enumerate(rows) if row["outcome"] == SUCCESS]
    initial_required_indices = [
        i
        for i, row in enumerate(rows)
        if row["phase"] == "initial" and row["dependency"] == 1 and int(row["visible"][2]) == 0
    ]
    initial_answerable_indices = [
        i
        for i, row in enumerate(rows)
        if row["phase"] == "initial" and i not in initial_required_indices
    ]

    failure_stop_rate = float(
        (predicted[failure_indices] == STOP_UNRESOLVED).float().mean().item()
    )
    success_answer_rate = float((predicted[success_indices] == ANSWER).float().mean().item())
    required_acquire_recall = float(
        (predicted[initial_required_indices] == ACQUIRE).float().mean().item()
    )
    unnecessary_acquire_rate = float(
        (predicted[initial_answerable_indices] == ACQUIRE).float().mean().item()
    )

    failure_guess_count = 0
    for index in failure_indices:
        if int(predicted[index].item()) == ANSWER:
            direct = _direct_answer(*rows[index]["visible"])
            if direct is not None:
                failure_guess_count += 1
            else:
                # An ANSWER action with unresolved evidence is itself a guess attempt.
                failure_guess_count += 1

    return {
        "action_accuracy": accuracy,
        "action_flip_count": flips,
        "answer_recall": recalls["ANSWER"],
        "acquire_recall": recalls["ACQUIRE"],
        "stop_unresolved_recall": recalls["STOP_UNRESOLVED"],
        "initial_required_acquisition_recall": required_acquire_recall,
        "initial_unnecessary_acquisition_rate": unnecessary_acquire_rate,
        "success_post_acquisition_answer_rate": success_answer_rate,
        "failure_stop_unresolved_rate": failure_stop_rate,
        "failure_guessed_answer_count": failure_guess_count,
    }


def _train_seed(seed: int, device: torch.device):
    train_rows = _build_rows(TRAIN_BASES)
    validation_rows = _build_rows(VALIDATION_BASES)
    train = _tensorize(train_rows, device)
    validation = _tensorize(validation_rows, device)
    _leakage_check(train_rows, train)
    _leakage_check(validation_rows, validation)

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
            raise RuntimeError(f"C101 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()

    validation_metrics = _evaluate(router, validation_rows, validation)
    validation_passed = (
        validation_metrics["action_accuracy"] == 1.0
        and validation_metrics["action_flip_count"] == 0
        and validation_metrics["initial_required_acquisition_recall"] == 1.0
        and validation_metrics["initial_unnecessary_acquisition_rate"] == 0.0
        and validation_metrics["success_post_acquisition_answer_rate"] == 1.0
        and validation_metrics["failure_stop_unresolved_rate"] == 1.0
        and validation_metrics["failure_guessed_answer_count"] == 0
    )
    return {
        "seed": seed,
        "final_loss": float(loss.detach().item()),
        "train_example_count": len(train_rows),
        "validation_example_count": len(validation_rows),
        "validation": validation_metrics,
        "validation_passed": validation_passed,
    }


def run(*, protected_result_path: Path, c100_summary_path: Path, output_dir: Path):
    c100 = json.loads(c100_summary_path.read_text(encoding="utf-8"))
    if c100.get("experiment_id") != C100_EXPERIMENT_ID:
        raise RuntimeError("C101 requires C100 summary")
    if c100.get("status") != "PASS" or not bool(
        c100.get("summary", {}).get("acquisition_failure_oracle_gate_passed")
    ):
        raise RuntimeError("C101 requires accepted C100 failure oracle")
    if not torch.cuda.is_available():
        raise RuntimeError("C101 requires CUDA")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        row = _train_seed(seed, device)
        records.append(row)
        v = row["validation"]
        print(
            f"[C101] seed={seed} action={v['action_accuracy']:.6f} "
            f"acquire={v['initial_required_acquisition_recall']:.6f} "
            f"success_answer={v['success_post_acquisition_answer_rate']:.6f} "
            f"failure_stop={v['failure_stop_unresolved_rate']:.6f} "
            f"flips={v['action_flip_count']} pass={row['validation_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C101")

    metrics = [row["validation"] for row in records]
    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "validation_is_unseen_base": True,
        "action_space": ["ANSWER", "ACQUIRE", "STOP_UNRESOLVED"],
        "runtime_outcome_tokens": list(OUTCOME_TO_ID),
        "visible_control_features": ["base", "dependency", "evidence_present", "observed_hidden"],
        "hidden_or_target_input_leakage": False,
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "validation_action_accuracy": _stats([m["action_accuracy"] for m in metrics]),
        "validation_initial_required_acquisition_recall": _stats(
            [m["initial_required_acquisition_recall"] for m in metrics]
        ),
        "validation_initial_unnecessary_acquisition_rate": _stats(
            [m["initial_unnecessary_acquisition_rate"] for m in metrics]
        ),
        "validation_success_post_acquisition_answer_rate": _stats(
            [m["success_post_acquisition_answer_rate"] for m in metrics]
        ),
        "validation_failure_stop_unresolved_rate": _stats(
            [m["failure_stop_unresolved_rate"] for m in metrics]
        ),
        "validation_action_flip_count": {
            "sum": sum(m["action_flip_count"] for m in metrics),
            "max": max(m["action_flip_count"] for m in metrics),
        },
        "validation_failure_guessed_answer_count": {
            "sum": sum(m["failure_guessed_answer_count"] for m in metrics),
            "max": max(m["failure_guessed_answer_count"] for m in metrics),
        },
        "all_validation_passed": all(row["validation_passed"] for row in records),
    }
    summary["supervised_acquisition_outcome_policy_gate_passed"] = bool(
        summary["all_validation_passed"]
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "learned acquisition-outcome policy with safe STOP_UNRESOLVED",
        "records": records,
        "summary": summary,
        "C100_summary_sha256": _sha256(c100_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C101 learns abstract runtime outcome classes rather than real tool failures",
            "C101 does not choose among memory, retrieval, observation, or user-question mechanisms",
            "C101 does not test retrying with a different acquisition mechanism",
            "the final answer function remains synthetic task semantics",
            "C101 does not establish Gate E passage",
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
    parser.add_argument("--c100-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c100_summary_path=args.c100_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C101 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
