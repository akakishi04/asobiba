"""C104: learn the C103 acquisition-mechanism selection semantics.

C103 fixed an oracle action family:

    ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED

C104 asks one question only: can the production fixed-width
ControlLaneActionRouter learn that policy from visible evidence plus a
runtime-owned eligibility mask, while generalizing to unseen base=3?

The four eligibility bits are supplied through the context control lane rather
than encoded as a categorical mask ID. Hidden truth and target are never router
inputs when evidence is missing.
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
    _target,
    _visible_signature,
)

EXPERIMENT_ID = "C104-v5e-supervised-acquisition-mechanism-selector"
C103_EXPERIMENT_ID = "C103-v5e-acquisition-mechanism-oracle"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261211, 20261212, 20261213)
TRAIN_BASES = (0, 1, 2)
VALIDATION_BASES = (3,)
WIDTH = 8
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 8
TRAIN_STEPS = 640
PER_CLASS_BATCH = 16
LR = 0.01
ACTION_COUNT = 6


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
    masks = tuple(itertools.product((0, 1), repeat=len(MECHANISMS)))
    for base, dependency, hidden, evidence_present, mask in itertools.product(
        bases, (0, 1), (0, 1), (0, 1), masks
    ):
        visible = _visible_signature(base, dependency, evidence_present, hidden)
        rows.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": visible,
                "eligible_mask": tuple(mask),
                "target": _target(base, dependency, hidden),
                "oracle_action": _oracle_action(dependency, evidence_present, tuple(mask)),
            }
        )
    return rows


def _tensorize(rows, device: torch.device):
    working = torch.zeros(len(rows), 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    operation_ids = torch.zeros(len(rows), dtype=torch.int64, device=device)
    labels = torch.tensor(
        [row["oracle_action"] for row in rows], dtype=torch.int64, device=device
    )
    for index, row in enumerate(rows):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        working[index, 0, 0] = float(base) / 3.0
        working[index, 0, 1] = float(dependency)
        working[index, 0, 2] = float(evidence_present)
        working[index, 0, 3] = float(observed_hidden)
        for bit, eligible in enumerate(row["eligible_mask"]):
            context[index, 0, bit] = float(eligible)
    return working, context, operation_ids, labels


def _leakage_check(rows, tensors):
    working, context, operation_ids, labels = tensors
    grouped = {}
    for index, row in enumerate(rows):
        if row["evidence_present"] == 0:
            key = (row["base"], row["dependency"], row["eligible_mask"])
            grouped.setdefault(key, []).append(index)
    for key, indices in grouped.items():
        if len(indices) != 2:
            raise RuntimeError(f"C104 malformed hidden counterfactual pair: {key}")
        a, b = indices
        if not torch.equal(working[a], working[b]):
            raise RuntimeError("C104 hidden truth leaked through working control lane")
        if not torch.equal(context[a], context[b]):
            raise RuntimeError("C104 hidden truth leaked through eligibility context")
        if int(operation_ids[a]) != int(operation_ids[b]):
            raise RuntimeError("C104 hidden truth leaked through operation token")
        if int(labels[a]) != int(labels[b]):
            raise RuntimeError("C104 oracle mechanism action depends on hidden truth")


def _balanced_indices(labels: torch.Tensor, generator: torch.Generator, device: torch.device):
    chunks = []
    for action in range(ACTION_COUNT):
        pool = torch.nonzero(labels.cpu() == action, as_tuple=False).flatten()
        if pool.numel() == 0:
            raise RuntimeError(f"C104 training set missing action class {action}")
        choice = torch.randint(pool.numel(), (PER_CLASS_BATCH,), generator=generator)
        chunks.append(pool.index_select(0, choice))
    index = torch.cat(chunks, dim=0)
    perm = torch.randperm(index.numel(), generator=generator)
    return index.index_select(0, perm).to(device)


@torch.inference_mode()
def _evaluate(router, rows, tensors):
    working, context, operation_ids, labels = tensors
    router.eval()
    predicted = router(working, context, operation_ids).argmax(dim=-1)
    accuracy = float((predicted == labels).float().mean().item())
    flips = int((predicted != labels).sum().item())

    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        if not bool(mask.any()):
            raise RuntimeError(f"C104 validation set missing action class {action}")
        recalls.append(float((predicted[mask] == action).float().mean().item()))

    answerable_indices = [
        i for i, row in enumerate(rows)
        if row["dependency"] == 0 or row["evidence_present"] == 1
    ]
    required_indices = [
        i for i, row in enumerate(rows)
        if row["dependency"] == 1 and row["evidence_present"] == 0
    ]
    required_available = [i for i in required_indices if any(rows[i]["eligible_mask"])]
    required_none = [i for i in required_indices if not any(rows[i]["eligible_mask"])]
    ask_and_self_service = [
        i
        for i in required_available
        if rows[i]["eligible_mask"][3] == 1 and any(rows[i]["eligible_mask"][:3])
    ]

    answerable_answer_rate = float(
        (predicted[answerable_indices] == ANSWER).float().mean().item()
    )
    required_no_direct_answer_rate = float(
        (predicted[required_indices] != ANSWER).float().mean().item()
    )
    minimum_burden_rate = float(
        (predicted[required_available] == labels[required_available]).float().mean().item()
    )
    unavailable_stop_rate = float(
        (predicted[required_none] == STOP_UNRESOLVED).float().mean().item()
    )
    ask_user_avoided_rate = float(
        (predicted[ask_and_self_service] != ASK_USER).float().mean().item()
    )

    ineligible_mechanism_count = 0
    mechanism_to_bit = {
        READ_MEMORY: 0,
        RETRIEVE: 1,
        OBSERVE: 2,
        ASK_USER: 3,
    }
    for i in required_indices:
        action = int(predicted[i].item())
        if action in mechanism_to_bit:
            if rows[i]["eligible_mask"][mechanism_to_bit[action]] == 0:
                ineligible_mechanism_count += 1

    grouped = {}
    for i in required_indices:
        row = rows[i]
        key = (row["base"], row["dependency"], row["eligible_mask"])
        grouped.setdefault(key, []).append(i)
    hidden_invariance = 1.0
    for indices in grouped.values():
        if len(indices) != 2:
            raise RuntimeError("C104 malformed validation counterfactual pair")
        if int(predicted[indices[0]]) != int(predicted[indices[1]]):
            hidden_invariance = 0.0
            break

    return {
        "action_accuracy": accuracy,
        "minimum_class_recall": min(recalls),
        "action_flip_count": flips,
        "answerable_answer_rate": answerable_answer_rate,
        "required_no_direct_answer_rate": required_no_direct_answer_rate,
        "minimum_burden_eligible_mechanism_rate": minimum_burden_rate,
        "no_eligible_mechanism_stop_unresolved_rate": unavailable_stop_rate,
        "ask_user_avoided_when_self_service_eligible_rate": ask_user_avoided_rate,
        "ineligible_mechanism_count": ineligible_mechanism_count,
        "missing_evidence_hidden_counterfactual_action_invariance": hidden_invariance,
    }


def _train_seed(seed: int, device: torch.device):
    train_rows = _rows_for_bases(TRAIN_BASES)
    validation_rows = _rows_for_bases(VALIDATION_BASES)
    train = _tensorize(train_rows, device)
    validation = _tensorize(validation_rows, device)
    _leakage_check(train_rows, train)
    _leakage_check(validation_rows, validation)

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
            raise RuntimeError(f"C104 non-finite loss seed={seed}")
        loss.backward()
        optimizer.step()

    metrics = _evaluate(router, validation_rows, validation)
    passed = (
        metrics["action_accuracy"] == 1.0
        and metrics["minimum_class_recall"] == 1.0
        and metrics["action_flip_count"] == 0
        and metrics["answerable_answer_rate"] == 1.0
        and metrics["required_no_direct_answer_rate"] == 1.0
        and metrics["minimum_burden_eligible_mechanism_rate"] == 1.0
        and metrics["no_eligible_mechanism_stop_unresolved_rate"] == 1.0
        and metrics["ask_user_avoided_when_self_service_eligible_rate"] == 1.0
        and metrics["ineligible_mechanism_count"] == 0
        and metrics["missing_evidence_hidden_counterfactual_action_invariance"] == 1.0
    )
    return {
        "seed": seed,
        "final_loss": float(loss.detach().item()),
        "train_example_count": len(train_rows),
        "validation_example_count": len(validation_rows),
        "validation": metrics,
        "validation_passed": passed,
    }


def run(*, protected_result_path: Path, c103_summary_path: Path, output_dir: Path):
    c103 = json.loads(c103_summary_path.read_text(encoding="utf-8"))
    if c103.get("experiment_id") != C103_EXPERIMENT_ID:
        raise RuntimeError("C104 requires C103 summary")
    if c103.get("status") != "PASS" or not bool(
        c103.get("summary", {}).get("acquisition_mechanism_oracle_gate_passed")
    ):
        raise RuntimeError("C104 requires accepted C103 mechanism oracle")
    if not torch.cuda.is_available():
        raise RuntimeError("C104 requires CUDA")

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
            f"[C104] seed={seed} action={v['action_accuracy']:.6f} "
            f"min_recall={v['minimum_class_recall']:.6f} "
            f"burden={v['minimum_burden_eligible_mechanism_rate']:.6f} "
            f"ineligible={v['ineligible_mechanism_count']} "
            f"flips={v['action_flip_count']} pass={row['validation_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C104")

    metrics = [r["validation"] for r in records]
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
        "fixed_burden_order": ["READ_MEMORY", "RETRIEVE", "OBSERVE", "ASK_USER"],
        "eligibility_representation": "four explicit context-control-lane bits",
        "visible_working_features": ["base", "dependency", "evidence_present", "observed_hidden"],
        "hidden_or_target_input_leakage": False,
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "class_balanced_training": True,
        "validation_action_accuracy": _stats([m["action_accuracy"] for m in metrics]),
        "validation_minimum_class_recall": _stats([m["minimum_class_recall"] for m in metrics]),
        "validation_action_flip_count": {
            "sum": sum(m["action_flip_count"] for m in metrics),
            "max": max(m["action_flip_count"] for m in metrics),
        },
        "validation_answerable_answer_rate": _stats([m["answerable_answer_rate"] for m in metrics]),
        "validation_required_no_direct_answer_rate": _stats([m["required_no_direct_answer_rate"] for m in metrics]),
        "validation_minimum_burden_eligible_mechanism_rate": _stats(
            [m["minimum_burden_eligible_mechanism_rate"] for m in metrics]
        ),
        "validation_no_eligible_mechanism_stop_unresolved_rate": _stats(
            [m["no_eligible_mechanism_stop_unresolved_rate"] for m in metrics]
        ),
        "validation_ask_user_avoided_when_self_service_eligible_rate": _stats(
            [m["ask_user_avoided_when_self_service_eligible_rate"] for m in metrics]
        ),
        "validation_ineligible_mechanism_count": {
            "sum": sum(m["ineligible_mechanism_count"] for m in metrics),
            "max": max(m["ineligible_mechanism_count"] for m in metrics),
        },
        "validation_hidden_counterfactual_action_invariance": _stats(
            [m["missing_evidence_hidden_counterfactual_action_invariance"] for m in metrics]
        ),
        "all_validation_passed": all(r["validation_passed"] for r in records),
    }
    summary["supervised_acquisition_mechanism_selector_gate_passed"] = bool(
        summary["all_validation_passed"]
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "supervised acquisition-mechanism selection on unseen base",
        "records": records,
        "summary": summary,
        "C103_summary_sha256": _sha256(c103_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C104 learns a synthetic fixed burden ordering rather than real expected utility",
            "eligibility is provided by the runtime rather than predicted by the model",
            "C104 does not invoke real memory, retrieval, observation, or user interaction",
            "C104 does not yet execute the selected mechanism as a closed loop",
            "C104 does not establish Gate E passage",
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
    parser.add_argument("--c103-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c103_summary_path=args.c103_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C104 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
