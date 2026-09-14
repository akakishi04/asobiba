"""C98: learn the C97 ANSWER/ACQUIRE information-sufficiency policy.

C97 registered the oracle semantics.  C98 asks one question only: can the
production fixed-width ControlLaneActionRouter learn the same policy from
visible evidence without receiving the hidden value (when missing), the target,
or the oracle action as an input?

Training uses base values 0/1/2 and validation holds out base=3.  The action
rule itself must therefore generalize across an unseen visible base value.
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
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    ACQUIRE,
    ANSWER,
    EXPERIMENT_ID as C97_EXPERIMENT_ID,
    _direct_answer,
    _oracle_action,
    _target,
    _visible_signature,
)

EXPERIMENT_ID = "C98-v5e-supervised-information-sufficiency-router"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261171, 20261172, 20261173)
TRAIN_BASES = (0, 1, 2)
VALIDATION_BASES = (3,)
WIDTH = 8
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 4
TRAIN_STEPS = 320
TRAIN_BATCH = 64
LR = 0.01
MIN_ACTION_ACCURACY = 1.0
MIN_REQUIRED_ACQUISITION_RECALL = 1.0
MAX_UNNECESSARY_ACQUISITION_RATE = 0.0


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


def _rows_for_bases(bases):
    rows = []
    for base, dependency, hidden, evidence_present in itertools.product(
        bases, (0, 1), (0, 1), (0, 1)
    ):
        visible = _visible_signature(base, dependency, evidence_present, hidden)
        target = _target(base, dependency, hidden)
        action = _oracle_action(dependency, evidence_present)
        rows.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": visible,
                "target": target,
                "oracle_action": action,
            }
        )
    return rows


def _tensorize(rows, device: torch.device):
    working = torch.zeros(len(rows), 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.zeros(len(rows), dtype=torch.int64, device=device)
    labels = torch.tensor([row["oracle_action"] for row in rows], dtype=torch.int64, device=device)
    for index, row in enumerate(rows):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        working[index, 0, 0] = float(base) / 3.0
        working[index, 0, 1] = float(dependency)
        working[index, 0, 2] = float(evidence_present)
        working[index, 0, 3] = float(observed_hidden)
    return working, context, operation_ids, labels


@torch.inference_mode()
def _evaluate(router, rows, tensors):
    working, context, operation_ids, labels = tensors
    router.eval()
    predicted = router(working, context, operation_ids).argmax(dim=-1)
    action_accuracy = float((predicted == labels).float().mean().item())

    required_mask = torch.tensor(
        [row["dependency"] == 1 and row["evidence_present"] == 0 for row in rows],
        dtype=torch.bool,
        device=labels.device,
    )
    answerable_mask = ~required_mask
    required_recall = float((predicted[required_mask] == ACQUIRE).float().mean().item())
    unnecessary_rate = float((predicted[answerable_mask] == ACQUIRE).float().mean().item())
    action_flips = int((predicted != labels).sum().item())

    final_correct = 0
    ambiguous_direct_attempts = 0
    for row, action in zip(rows, predicted.tolist()):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        if action == ACQUIRE:
            final_answer = row["target"]
        else:
            direct = _direct_answer(base, dependency, evidence_present, observed_hidden)
            if direct is None:
                ambiguous_direct_attempts += 1
            final_answer = direct
        final_correct += int(final_answer == row["target"])

    return {
        "action_accuracy": action_accuracy,
        "required_acquisition_recall": required_recall,
        "unnecessary_acquisition_rate": unnecessary_rate,
        "action_flip_count": action_flips,
        "ambiguous_direct_answer_attempt_count": ambiguous_direct_attempts,
        "post_policy_final_accuracy": final_correct / len(rows),
    }


def _train_seed(seed: int, device: torch.device):
    train_rows = _rows_for_bases(TRAIN_BASES)
    validation_rows = _rows_for_bases(VALIDATION_BASES)
    train = _tensorize(train_rows, device)
    validation = _tensorize(validation_rows, device)

    # Explicit leakage check: missing-evidence counterfactuals must map to exactly
    # the same router input regardless of hidden=0/1.
    for rows, tensors in ((train_rows, train), (validation_rows, validation)):
        working = tensors[0]
        grouped = {}
        for index, row in enumerate(rows):
            if row["evidence_present"] == 0:
                key = (row["base"], row["dependency"])
                grouped.setdefault(key, []).append(index)
        for indices in grouped.values():
            if len(indices) != 2 or not torch.equal(working[indices[0]], working[indices[1]]):
                raise RuntimeError("C98 hidden value leaked into missing-evidence router input")

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
            raise RuntimeError(f"C98 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()

    train_metrics = _evaluate(router, train_rows, train)
    validation_metrics = _evaluate(router, validation_rows, validation)
    validation_pass = (
        validation_metrics["action_accuracy"] >= MIN_ACTION_ACCURACY
        and validation_metrics["required_acquisition_recall"] >= MIN_REQUIRED_ACQUISITION_RECALL
        and validation_metrics["unnecessary_acquisition_rate"] <= MAX_UNNECESSARY_ACQUISITION_RATE
        and validation_metrics["ambiguous_direct_answer_attempt_count"] == 0
        and validation_metrics["post_policy_final_accuracy"] == 1.0
    )
    return {
        "seed": seed,
        "final_loss": float(loss.detach().item()),
        "train": train_metrics,
        "validation": validation_metrics,
        "validation_passed": validation_pass,
    }


def run(*, protected_result_path: Path, c97_summary_path: Path, output_dir: Path):
    c97 = json.loads(c97_summary_path.read_text(encoding="utf-8"))
    if c97.get("experiment_id") != C97_EXPERIMENT_ID:
        raise RuntimeError("C98 requires C97 summary")
    if c97.get("status") != "PASS" or not bool(
        c97.get("summary", {}).get("information_sufficiency_oracle_gate_passed")
    ):
        raise RuntimeError("C98 requires accepted C97 oracle baseline")
    if not torch.cuda.is_available():
        raise RuntimeError("C98 requires CUDA")

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
            f"[C98] seed={seed} action={v['action_accuracy']:.6f} "
            f"acquire_recall={v['required_acquisition_recall']:.6f} "
            f"unnecessary={v['unnecessary_acquisition_rate']:.6f} "
            f"flips={v['action_flip_count']} final={v['post_policy_final_accuracy']:.6f} "
            f"pass={row['validation_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C98")

    accuracies = [r["validation"]["action_accuracy"] for r in records]
    recalls = [r["validation"]["required_acquisition_recall"] for r in records]
    unnecessary = [r["validation"]["unnecessary_acquisition_rate"] for r in records]
    flips = [r["validation"]["action_flip_count"] for r in records]
    final = [r["validation"]["post_policy_final_accuracy"] for r in records]
    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "validation_is_unseen_base": True,
        "visible_features": ["base", "dependency", "evidence_present", "observed_hidden"],
        "hidden_or_target_input_leakage": False,
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "validation_action_accuracy": _stats(accuracies),
        "validation_required_acquisition_recall": _stats(recalls),
        "validation_unnecessary_acquisition_rate": _stats(unnecessary),
        "validation_action_flip_count": {"sum": sum(flips), "max": max(flips)},
        "validation_post_policy_final_accuracy": _stats(final),
        "all_validation_passed": all(r["validation_passed"] for r in records),
    }
    summary["supervised_information_sufficiency_gate_passed"] = bool(
        summary["all_validation_passed"]
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "supervised information-sufficiency routing on unseen visible base",
        "records": records,
        "summary": summary,
        "C97_summary_sha256": _sha256(c97_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C98 learns only the binary ANSWER/ACQUIRE sufficiency decision",
            "the direct answer and acquisition result remain oracle task semantics",
            "ACQUIRE is still abstract and does not select memory/retrieval/observation/user question",
            "C98 is a tiny synthetic task and does not establish broad uncertainty calibration",
            "C98 does not establish Gate E passage",
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
    parser.add_argument("--c97-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c97_summary_path=args.c97_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C98 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
