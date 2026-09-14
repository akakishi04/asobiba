"""C108: falsify dependence on exact numeric Control-Lane encodings.

C107 removed a shared train/eval generator as an explanation. C108 keeps the
same logical policy but changes how boolean semantics are numerically encoded.

Training sees two signed codebooks. Validation uses three held-out signed
codebooks whose scalar values never occur during training. The only invariant
available across codebooks is semantic sign: false < 0 and true > 0.

This is a representation-robustness falsification, not a claim that arbitrary
unknown encodings should be understood without a contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks import gate_e_c107_independent_eval_fixture as fixture

EXPERIMENT_ID = "C108-v5e-feature-reencoding-falsification"
C107_EXPERIMENT_ID = "C107-v5e-independent-evaluator-falsification"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261311, 20261312, 20261313)
TRAIN_BASES = (0, 1, 2)
VALIDATION_BASES = (3,)
WIDTH = 8
CONTROL_WIDTH = 4
HIDDEN_WIDTH = 8
ACTION_COUNT = 6
TRAIN_STEPS = 900
PER_CLASS_BATCH = 16
LR = 0.01

TRAIN_CODEBOOKS = (
    ("train_a", -0.5, 0.75),
    ("train_b", -2.0, 1.25),
)
OOD_CODEBOOKS = (
    ("ood_a", -3.5, 0.20),
    ("ood_b", -0.10, 4.0),
    ("ood_c", -7.0, 9.0),
)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _logical_rows(bases):
    rows = []
    for base in bases:
        for row in fixture.independent_rows(base=base):
            rows.append(row)
    return rows


def _encode_bit(value: int, false_value: float, true_value: float) -> float:
    return true_value if int(value) else false_value


def _tensorize(rows, codebook, device):
    _name, false_value, true_value = codebook
    working = torch.zeros(len(rows), 1, WIDTH, device=device)
    context = torch.zeros_like(working)
    op_ids = torch.zeros(len(rows), dtype=torch.int64, device=device)
    labels = torch.tensor([r["expected_action"] for r in rows], dtype=torch.int64, device=device)
    for i, row in enumerate(rows):
        base, dependency, evidence_present, observed_hidden = row["visible"]
        # Base is intentionally left canonical because it is policy-irrelevant.
        working[i, 0, 0] = float(base) / 3.0
        working[i, 0, 1] = _encode_bit(dependency, false_value, true_value)
        working[i, 0, 2] = _encode_bit(evidence_present, false_value, true_value)
        working[i, 0, 3] = _encode_bit(observed_hidden, false_value, true_value)
        for bit, eligible in enumerate(row["eligible_mask"]):
            context[i, 0, bit] = _encode_bit(eligible, false_value, true_value)
    return working, context, op_ids, labels


def _concat_training(rows, device):
    chunks = [_tensorize(rows, cb, device) for cb in TRAIN_CODEBOOKS]
    return tuple(torch.cat([chunk[i] for chunk in chunks], dim=0) for i in range(4))


def _balanced_indices(labels, generator, device):
    cpu = labels.cpu()
    chunks = []
    for action in range(ACTION_COUNT):
        pool = torch.nonzero(cpu == action, as_tuple=False).flatten()
        if pool.numel() == 0:
            raise RuntimeError(f"C108 training set missing action class {action}")
        choice = torch.randint(pool.numel(), (PER_CLASS_BATCH,), generator=generator)
        chunks.append(pool.index_select(0, choice))
    idx = torch.cat(chunks)
    perm = torch.randperm(idx.numel(), generator=generator)
    return idx.index_select(0, perm).to(device)


def _leakage_check(rows, tensors):
    working, context, op_ids, labels = tensors
    groups = {}
    for i, row in enumerate(rows):
        if row["evidence_present"] == 0:
            key = (row["base"], row["dependency"], row["eligible_mask"])
            groups.setdefault(key, []).append(i)
    for key, indices in groups.items():
        if len(indices) != 2:
            raise RuntimeError(f"C108 malformed hidden pair: {key}")
        a, b = indices
        if not torch.equal(working[a], working[b]):
            raise RuntimeError("C108 hidden truth leaked through working representation")
        if not torch.equal(context[a], context[b]):
            raise RuntimeError("C108 hidden truth leaked through eligibility representation")
        if int(op_ids[a]) != int(op_ids[b]) or int(labels[a]) != int(labels[b]):
            raise RuntimeError("C108 hidden truth leaked through token or action target")


@torch.inference_mode()
def _evaluate(router, rows, tensors):
    working, context, op_ids, labels = tensors
    pred = router(working, context, op_ids).argmax(dim=-1)
    accuracy = float((pred == labels).float().mean().item())
    flips = int((pred != labels).sum().item())

    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        if not bool(mask.any()):
            raise RuntimeError(f"C108 validation missing action class {action}")
        recalls.append(float((pred[mask] == action).float().mean().item()))

    answerable = [i for i, r in enumerate(rows) if r["dependency"] == 0 or r["evidence_present"] == 1]
    required = [i for i, r in enumerate(rows) if r["dependency"] == 1 and r["evidence_present"] == 0]
    available = [i for i in required if any(rows[i]["eligible_mask"])]
    unavailable = [i for i in required if not any(rows[i]["eligible_mask"])]

    bits = {fixture.READ_MEMORY: 0, fixture.RETRIEVE: 1, fixture.OBSERVE: 2, fixture.ASK_USER: 3}
    ineligible = 0
    for i in required:
        action = int(pred[i].item())
        if action in bits and rows[i]["eligible_mask"][bits[action]] == 0:
            ineligible += 1

    groups = {}
    for i in required:
        r = rows[i]
        groups.setdefault((r["base"], r["dependency"], r["eligible_mask"]), []).append(i)
    hidden_invariance = 1.0
    for pair in groups.values():
        if len(pair) != 2 or int(pred[pair[0]]) != int(pred[pair[1]]):
            hidden_invariance = 0.0
            break

    return {
        "action_accuracy": accuracy,
        "minimum_class_recall": min(recalls),
        "action_flip_count": flips,
        "answerable_answer_rate": float((pred[answerable] == fixture.ANSWER).float().mean().item()),
        "required_no_direct_answer_rate": float((pred[required] != fixture.ANSWER).float().mean().item()),
        "minimum_burden_rate": float((pred[available] == labels[available]).float().mean().item()),
        "no_eligible_stop_rate": float((pred[unavailable] == fixture.STOP_UNRESOLVED).float().mean().item()),
        "ineligible_mechanism_count": ineligible,
        "hidden_counterfactual_action_invariance": hidden_invariance,
    }


def _train_seed(seed, device):
    train_rows = _logical_rows(TRAIN_BASES)
    val_rows = _logical_rows(VALIDATION_BASES)
    train = _concat_training(train_rows, device)

    # Check leakage separately in each training encoding and each held-out encoding.
    for cb in TRAIN_CODEBOOKS:
        _leakage_check(train_rows, _tensorize(train_rows, cb, device))
    for cb in OOD_CODEBOOKS:
        _leakage_check(val_rows, _tensorize(val_rows, cb, device))

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
            raise RuntimeError(f"C108 non-finite loss seed={seed}")
        loss.backward()
        opt.step()
    router.eval()

    anchor = _evaluate(router, val_rows, _tensorize(val_rows, TRAIN_CODEBOOKS[0], device))
    ood = {}
    for cb in OOD_CODEBOOKS:
        ood[cb[0]] = _evaluate(router, val_rows, _tensorize(val_rows, cb, device))

    ood_pass = all(
        m["action_accuracy"] == 1.0
        and m["minimum_class_recall"] == 1.0
        and m["action_flip_count"] == 0
        and m["answerable_answer_rate"] == 1.0
        and m["required_no_direct_answer_rate"] == 1.0
        and m["minimum_burden_rate"] == 1.0
        and m["no_eligible_stop_rate"] == 1.0
        and m["ineligible_mechanism_count"] == 0
        and m["hidden_counterfactual_action_invariance"] == 1.0
        for m in ood.values()
    )
    passed = (
        anchor["action_accuracy"] == 1.0
        and anchor["minimum_class_recall"] == 1.0
        and anchor["action_flip_count"] == 0
        and ood_pass
    )
    return {
        "seed": seed,
        "final_loss": float(loss.detach().item()),
        "anchor": anchor,
        "ood": ood,
        "validation_passed": passed,
    }


def run(*, protected_result_path: Path, c107_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c107_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C107_EXPERIMENT_ID:
        raise RuntimeError("C108 requires C107 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get("independent_evaluator_falsification_gate_passed"):
        raise RuntimeError("C108 requires accepted C107 falsification")
    if not torch.cuda.is_available():
        raise RuntimeError("C108 requires CUDA")

    train_values = {v for _n, f, t in TRAIN_CODEBOOKS for v in (f, t)}
    ood_values = {v for _n, f, t in OOD_CODEBOOKS for v in (f, t)}
    scalar_disjoint = train_values.isdisjoint(ood_values)
    sign_contract = all(f < 0 < t for _n, f, t in TRAIN_CODEBOOKS + OOD_CODEBOOKS)
    if not scalar_disjoint or not sign_contract:
        raise RuntimeError("C108 codebook registration invalid")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        row = _train_seed(seed, device)
        records.append(row)
        worst_acc = min(m["action_accuracy"] for m in row["ood"].values())
        worst_recall = min(m["minimum_class_recall"] for m in row["ood"].values())
        print(
            f"[C108] seed={seed} anchor={row['anchor']['action_accuracy']:.6f} "
            f"ood_acc_min={worst_acc:.6f} ood_recall_min={worst_recall:.6f} "
            f"pass={row['validation_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C108")

    ood_metrics = [m for r in records for m in r["ood"].values()]
    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(TRAIN_BASES),
        "validation_bases": list(VALIDATION_BASES),
        "training_codebooks": [list(x) for x in TRAIN_CODEBOOKS],
        "ood_codebooks": [list(x) for x in OOD_CODEBOOKS],
        "ood_scalar_values_absent_from_training": scalar_disjoint,
        "shared_semantic_contract": "false<0<true",
        "control_width": CONTROL_WIDTH,
        "hidden_width": HIDDEN_WIDTH,
        "training_steps": TRAIN_STEPS,
        "anchor_action_accuracy": _stats([r["anchor"]["action_accuracy"] for r in records]),
        "anchor_minimum_class_recall": _stats([r["anchor"]["minimum_class_recall"] for r in records]),
        "ood_action_accuracy": _stats([m["action_accuracy"] for m in ood_metrics]),
        "ood_minimum_class_recall": _stats([m["minimum_class_recall"] for m in ood_metrics]),
        "ood_minimum_burden_rate": _stats([m["minimum_burden_rate"] for m in ood_metrics]),
        "ood_ineligible_mechanism_count": {
            "sum": sum(m["ineligible_mechanism_count"] for m in ood_metrics),
            "max": max(m["ineligible_mechanism_count"] for m in ood_metrics),
        },
        "ood_action_flip_count": {
            "sum": sum(m["action_flip_count"] for m in ood_metrics),
            "max": max(m["action_flip_count"] for m in ood_metrics),
        },
        "ood_hidden_counterfactual_action_invariance": _stats(
            [m["hidden_counterfactual_action_invariance"] for m in ood_metrics]
        ),
        "all_validation_passed": all(r["validation_passed"] for r in records),
    }
    summary["feature_reencoding_falsification_gate_passed"] = bool(summary["all_validation_passed"])

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "held-out signed-codebook feature re-encoding falsification",
        "summary": summary,
        "records": records,
        "C107_summary_sha256": _sha(c107_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C108 preserves a shared sign convention across all codebooks",
            "arbitrary channel permutation or unknown semantic remapping is not a valid invariant and is not tested",
            "runtime metadata is still exact rather than noisy or stale",
            "C108 remains synthetic and does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
