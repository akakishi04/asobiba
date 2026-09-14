"""C106: falsify mask-memorization in V5-E mechanism selection.

C104/C105 trained with all 16 eligibility masks. C106 deliberately withholds
compositional masks from training and asks whether the production Control Lane
learns the priority rule rather than a 16-entry mask lookup.

Training masks: Hamming weight <= 2.
OOD validation masks: Hamming weight >= 3.

The OOD masks are never present in training. A separate unseen-base anchor
validation over the training-mask family preserves all six action classes, so
passing OOD composition cannot hide catastrophic forgetting of the registered
policy.
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
from fold_lm.v05_benchmarks.gate_e_supervised_acquisition_mechanism_selector import (
    ACTION_COUNT,
    CONTROL_WIDTH,
    HIDDEN_WIDTH,
    LR,
    PER_CLASS_BATCH,
    WIDTH,
)

EXPERIMENT_ID = "C106-v5e-unseen-eligibility-mask-generalization"
C105_EXPERIMENT_ID = "C105-v5e-learned-acquisition-mechanism-closed-loop"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261231, 20261232, 20261233)
TRAIN_BASES = (0, 1, 2)
VALIDATION_BASES = (3,)
TRAIN_STEPS = 800

ALL_MASKS = tuple(itertools.product((0, 1), repeat=len(MECHANISMS)))
TRAIN_MASKS = tuple(mask for mask in ALL_MASKS if sum(mask) <= 2)
OOD_MASKS = tuple(mask for mask in ALL_MASKS if sum(mask) >= 3)


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


def _rows(bases, masks):
    rows = []
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
                "visible": tuple(visible),
                "eligible_mask": tuple(mask),
                "target": _target(base, dependency, hidden),
                "oracle_action": _oracle_action(dependency, evidence_present, tuple(mask)),
            }
        )
    return rows


def _tensorize(rows, device):
    working = torch.zeros(len(rows), 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    op_ids = torch.zeros(len(rows), dtype=torch.int64, device=device)
    labels = torch.tensor([r["oracle_action"] for r in rows], dtype=torch.int64, device=device)
    for i, row in enumerate(rows):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        working[i, 0, 0] = float(base) / 3.0
        working[i, 0, 1] = float(dependency)
        working[i, 0, 2] = float(evidence_present)
        working[i, 0, 3] = float(observed_hidden)
        for bit, eligible in enumerate(row["eligible_mask"]):
            context[i, 0, bit] = float(eligible)
    return working, context, op_ids, labels


def _leakage_check(rows, tensors):
    working, context, op_ids, labels = tensors
    groups = {}
    for i, row in enumerate(rows):
        if row["evidence_present"] == 0:
            key = (row["base"], row["dependency"], row["eligible_mask"])
            groups.setdefault(key, []).append(i)
    for key, indices in groups.items():
        if len(indices) != 2:
            raise RuntimeError(f"C106 malformed counterfactual pair: {key}")
        a, b = indices
        if not torch.equal(working[a], working[b]):
            raise RuntimeError("C106 hidden truth leaked through working lane")
        if not torch.equal(context[a], context[b]):
            raise RuntimeError("C106 hidden truth leaked through eligibility context")
        if int(op_ids[a]) != int(op_ids[b]) or int(labels[a]) != int(labels[b]):
            raise RuntimeError("C106 hidden truth leaked through token or target action")


def _balanced_indices(labels, generator, device):
    chunks = []
    cpu = labels.cpu()
    for action in range(ACTION_COUNT):
        pool = torch.nonzero(cpu == action, as_tuple=False).flatten()
        if pool.numel() == 0:
            raise RuntimeError(f"C106 training masks missing action class {action}")
        choice = torch.randint(pool.numel(), (PER_CLASS_BATCH,), generator=generator)
        chunks.append(pool.index_select(0, choice))
    idx = torch.cat(chunks)
    perm = torch.randperm(idx.numel(), generator=generator)
    return idx.index_select(0, perm).to(device)


@torch.inference_mode()
def _evaluate(router, rows, tensors, require_all_classes):
    working, context, op_ids, labels = tensors
    router.eval()
    pred = router(working, context, op_ids).argmax(dim=-1)
    accuracy = float((pred == labels).float().mean().item())
    flips = int((pred != labels).sum().item())

    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        if bool(mask.any()):
            recalls.append(float((pred[mask] == action).float().mean().item()))
        elif require_all_classes:
            raise RuntimeError(f"C106 anchor validation missing action class {action}")
    minimum_recall = min(recalls) if recalls else 0.0

    answerable = [i for i, r in enumerate(rows) if r["dependency"] == 0 or r["evidence_present"] == 1]
    required = [i for i, r in enumerate(rows) if r["dependency"] == 1 and r["evidence_present"] == 0]
    required_available = [i for i in required if any(rows[i]["eligible_mask"])]
    required_none = [i for i in required if not any(rows[i]["eligible_mask"])]

    answer_rate = float((pred[answerable] == ANSWER).float().mean().item()) if answerable else 1.0
    no_direct_answer_rate = float((pred[required] != ANSWER).float().mean().item()) if required else 1.0
    burden_rate = float((pred[required_available] == labels[required_available]).float().mean().item()) if required_available else 1.0
    stop_rate = float((pred[required_none] == STOP_UNRESOLVED).float().mean().item()) if required_none else 1.0

    mechanism_to_bit = {READ_MEMORY: 0, RETRIEVE: 1, OBSERVE: 2, ASK_USER: 3}
    ineligible = 0
    for i in required:
        action = int(pred[i].item())
        if action in mechanism_to_bit and rows[i]["eligible_mask"][mechanism_to_bit[action]] == 0:
            ineligible += 1

    groups = {}
    for i in required:
        row = rows[i]
        key = (row["base"], row["dependency"], row["eligible_mask"])
        groups.setdefault(key, []).append(i)
    hidden_invariance = 1.0
    for indices in groups.values():
        if len(indices) != 2:
            raise RuntimeError("C106 malformed validation counterfactual group")
        if int(pred[indices[0]]) != int(pred[indices[1]]):
            hidden_invariance = 0.0
            break

    return {
        "action_accuracy": accuracy,
        "minimum_present_class_recall": minimum_recall,
        "action_flip_count": flips,
        "answerable_answer_rate": answer_rate,
        "required_no_direct_answer_rate": no_direct_answer_rate,
        "minimum_burden_rate": burden_rate,
        "no_eligible_stop_rate": stop_rate,
        "ineligible_mechanism_count": ineligible,
        "hidden_counterfactual_action_invariance": hidden_invariance,
    }


def _train_seed(seed, device):
    train_rows = _rows(TRAIN_BASES, TRAIN_MASKS)
    anchor_rows = _rows(VALIDATION_BASES, TRAIN_MASKS)
    ood_rows = _rows(VALIDATION_BASES, OOD_MASKS)
    train = _tensorize(train_rows, device)
    anchor = _tensorize(anchor_rows, device)
    ood = _tensorize(ood_rows, device)
    _leakage_check(train_rows, train)
    _leakage_check(anchor_rows, anchor)
    _leakage_check(ood_rows, ood)

    if set(TRAIN_MASKS) & set(OOD_MASKS):
        raise RuntimeError("C106 OOD masks overlap training masks")
    if len(TRAIN_MASKS) + len(OOD_MASKS) != len(ALL_MASKS):
        raise RuntimeError("C106 mask partition is incomplete")

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
    opt = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    gen = torch.Generator(device="cpu").manual_seed(seed + 400)
    working, context, op_ids, labels = train
    router.train()
    loss = None
    for _ in range(TRAIN_STEPS):
        idx = _balanced_indices(labels, gen, device)
        opt.zero_grad(set_to_none=True)
        logits = router(
            working.index_select(0, idx),
            context.index_select(0, idx),
            op_ids.index_select(0, idx),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, idx))
        if not torch.isfinite(loss):
            raise RuntimeError(f"C106 non-finite loss seed={seed}")
        loss.backward()
        opt.step()

    anchor_metrics = _evaluate(router, anchor_rows, anchor, True)
    ood_metrics = _evaluate(router, ood_rows, ood, False)
    passed = (
        anchor_metrics["action_accuracy"] == 1.0
        and anchor_metrics["minimum_present_class_recall"] == 1.0
        and anchor_metrics["action_flip_count"] == 0
        and ood_metrics["action_accuracy"] == 1.0
        and ood_metrics["action_flip_count"] == 0
        and ood_metrics["answerable_answer_rate"] == 1.0
        and ood_metrics["required_no_direct_answer_rate"] == 1.0
        and ood_metrics["minimum_burden_rate"] == 1.0
        and ood_metrics["ineligible_mechanism_count"] == 0
        and ood_metrics["hidden_counterfactual_action_invariance"] == 1.0
    )
    return {
        "seed": seed,
        "final_loss": float(loss.detach().item()),
        "anchor": anchor_metrics,
        "ood": ood_metrics,
        "validation_passed": passed,
    }


def run(*, protected_result_path: Path, c105_summary_path: Path, output_dir: Path):
    c105 = json.loads(c105_summary_path.read_text(encoding="utf-8"))
    if c105.get("experiment_id") != C105_EXPERIMENT_ID:
        raise RuntimeError("C106 requires C105 summary")
    if c105.get("status") != "PASS" or not bool(
        c105.get("summary", {}).get("learned_acquisition_mechanism_closed_loop_gate_passed")
    ):
        raise RuntimeError("C106 requires accepted C105 closed loop")
    if not torch.cuda.is_available():
        raise RuntimeError("C106 requires CUDA")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        row = _train_seed(seed, device)
        records.append(row)
        print(
            f"[C106] seed={seed} anchor={row['anchor']['action_accuracy']:.6f} "
            f"ood={row['ood']['action_accuracy']:.6f} "
            f"ood_burden={row['ood']['minimum_burden_rate']:.6f} "
            f"flips={row['ood']['action_flip_count']} pass={row['validation_passed']}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C106")

    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "train_masks": [list(x) for x in TRAIN_MASKS],
        "ood_masks": [list(x) for x in OOD_MASKS],
        "train_mask_count": len(TRAIN_MASKS),
        "ood_mask_count": len(OOD_MASKS),
        "mask_partition_rule": "train hamming_weight<=2; OOD hamming_weight>=3",
        "ood_masks_never_seen_in_training": True,
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "anchor_action_accuracy": _stats([r["anchor"]["action_accuracy"] for r in records]),
        "anchor_minimum_class_recall": _stats([r["anchor"]["minimum_present_class_recall"] for r in records]),
        "ood_action_accuracy": _stats([r["ood"]["action_accuracy"] for r in records]),
        "ood_minimum_burden_rate": _stats([r["ood"]["minimum_burden_rate"] for r in records]),
        "ood_ineligible_mechanism_count": {
            "sum": sum(r["ood"]["ineligible_mechanism_count"] for r in records),
            "max": max(r["ood"]["ineligible_mechanism_count"] for r in records),
        },
        "ood_action_flip_count": {
            "sum": sum(r["ood"]["action_flip_count"] for r in records),
            "max": max(r["ood"]["action_flip_count"] for r in records),
        },
        "ood_hidden_counterfactual_action_invariance": _stats(
            [r["ood"]["hidden_counterfactual_action_invariance"] for r in records]
        ),
        "all_validation_passed": all(r["validation_passed"] for r in records),
    }
    summary["unseen_mask_generalization_gate_passed"] = bool(summary["all_validation_passed"])

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "falsification of eligibility-mask memorization via unseen compositional masks",
        "records": records,
        "summary": summary,
        "C105_summary_sha256": _sha256(c105_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C106 changes mask composition but keeps the same synthetic feature semantics",
            "the evaluation generator is still from the same code family as training",
            "OOD masks contain only the action classes implied by high-Hamming-weight masks; anchor validation preserves all six classes separately",
            "C106 does not establish real-world acquisition generalization or Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c105-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    report = run(
        protected_result_path=args.protected_result,
        c105_summary_path=args.c105_summary,
        output_dir=args.output_dir,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C106 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
