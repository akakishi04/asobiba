"""C92: diagnose the C91 large-width compact-router quality failure.

C91 was a valid negative result: hidden_width=4 was tiny and fast at width
3072/5120, but its learned actions collapsed to 0.33-0.50 accuracy after the
accepted 240-step router schedule.  C92 does not change production code.  It
reuses the C91 failure seeds and asks whether the failure is primarily delayed
optimization/convergence or a persistent capacity/representation problem.

For widths 3072 and 5120, hidden widths 4 and 32 are trained with the same
AdamW/lr=0.01 rule and evaluated at 240/480/960/1920 steps.  The experiment is
a mechanism diagnosis, not a Gate-D pass attempt.
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

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05.modules import LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import _allocate_shared
from fold_lm.v05_benchmarks.gate_d_c87_router_train import ACTION_COUNT, oracle_actions
from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    EVENTS,
    _apply_oracle_actions,
    _event_context,
    make_runtime_inputs,
    rank_for_width,
)

EXPERIMENT_ID = "C92-v5d-router-large-width-convergence-diagnosis"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261141, 20261142, 20261143)
WIDTHS = (3072, 5120)
HIDDEN_WIDTHS = (4, 32)
CHECKPOINTS = (240, 480, 960, 1920)
TRAIN_BATCH = 256
LR = 0.01
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.99


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


def _build_examples(width: int, device: torch.device, seed: int):
    torch.manual_seed(seed + 50000)
    config = LearnedCoreConfig(width=width, slots=1, modules=2, hidden_mult=2)
    core = _allocate_shared(config, rank_for_width(width), device).eval()
    working, operations, operands = make_runtime_inputs(width, device)

    states = []
    contexts = []
    op_ids = []
    labels = []
    current = working.clone()
    with torch.inference_mode():
        for event in range(EVENTS):
            op = operations[:, event]
            operand = operands[:, event]
            context = _event_context(width, operand, current.dtype)
            action = oracle_actions(op, operand)
            states.append(current.clone())
            contexts.append(context)
            op_ids.append(op.clone())
            labels.append(action.clone())
            current = _apply_oracle_actions(core, current, action)
    return (
        torch.cat(states, dim=0),
        torch.cat(contexts, dim=0),
        torch.cat(op_ids, dim=0),
        torch.cat(labels, dim=0),
    )


@torch.inference_mode()
def _evaluate(router, states, contexts, op_ids, labels):
    router.eval()
    predicted = router(states, contexts, op_ids).argmax(dim=-1)
    accuracy = float((predicted == labels).float().mean().item())
    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        recalls.append(float((predicted[mask] == action).float().mean().item()))
    minimum_recall = min(recalls)
    return {
        "action_accuracy": accuracy,
        "minimum_class_recall": minimum_recall,
        "quality_passed": accuracy >= MIN_ACTION_ACCURACY and minimum_recall >= MIN_CLASS_RECALL,
    }


def _train_one(width: int, hidden: int, seed: int, device: torch.device):
    states, contexts, op_ids, labels = _build_examples(width, device, seed)
    torch.manual_seed(seed)
    router = SupervisedActionRouter(
        ActionRouterConfig(
            width=width,
            operation_vocab_size=2,
            hidden_width=hidden,
            action_count=ACTION_COUNT,
        )
    ).to(device)
    optimizer = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    snapshots = []
    loss = None

    for step in range(1, max(CHECKPOINTS) + 1):
        index = torch.randint(states.shape[0], (TRAIN_BATCH,), generator=generator).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            op_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C92 non-finite loss width={width} hidden={hidden} seed={seed} step={step}"
            )
        loss.backward()
        optimizer.step()

        if step in CHECKPOINTS:
            metrics = _evaluate(router, states, contexts, op_ids, labels)
            metrics.update({"step": step, "loss": float(loss.detach().item())})
            snapshots.append(metrics)
            print(
                f"[C92] width={width} hidden={hidden} seed={seed} step={step} "
                f"action={metrics['action_accuracy']:.6f} "
                f"class_min={metrics['minimum_class_recall']:.6f} "
                f"pass={metrics['quality_passed']}",
                flush=True,
            )
            router.train()

    first_pass = next((row["step"] for row in snapshots if row["quality_passed"]), None)
    return {
        "width": width,
        "hidden_width": hidden,
        "seed": seed,
        "first_passing_checkpoint": first_pass,
        "snapshots": snapshots,
    }


def run(*, protected_result_path: Path, c91_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C92 requires CUDA")
    c91 = json.loads(c91_summary_path.read_text(encoding="utf-8"))
    if c91.get("experiment_id") != "C91-v5d-selected-router-large-width-runtime-vram":
        raise RuntimeError("C92 requires C91 summary")
    if c91.get("status") != "PASS":
        raise RuntimeError("C92 requires valid C91 execution")
    if bool(c91.get("summary", {}).get("selected_router_large_width_gate_passed")):
        raise RuntimeError("C92 is only for the C91 large-width quality failure")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for width in WIDTHS:
        for hidden in HIDDEN_WIDTHS:
            for seed in SEEDS:
                records.append(_train_one(width, hidden, seed, device))

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C92")

    def rows_for(hidden: int):
        return [row for row in records if row["hidden_width"] == hidden]

    hidden4 = rows_for(4)
    hidden32 = rows_for(32)
    h4_first = [row["first_passing_checkpoint"] for row in hidden4]
    h32_first = [row["first_passing_checkpoint"] for row in hidden32]
    h4_all_recover = all(value is not None for value in h4_first)
    h32_all_recover = all(value is not None for value in h32_first)
    h4_all_by_240 = all(value == 240 for value in h4_first)
    h32_all_by_240 = all(value == 240 for value in h32_first)

    final_h4 = [row["snapshots"][-1]["action_accuracy"] for row in hidden4]
    final_h32 = [row["snapshots"][-1]["action_accuracy"] for row in hidden32]
    summary = {
        "widths": list(WIDTHS),
        "hidden_widths": list(HIDDEN_WIDTHS),
        "seeds": list(SEEDS),
        "checkpoints": list(CHECKPOINTS),
        "reuses_c91_failure_seeds_for_mechanism_diagnosis": True,
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "hidden4_first_passing_checkpoints": h4_first,
        "hidden32_first_passing_checkpoints": h32_first,
        "hidden4_all_recover_by_1920": h4_all_recover,
        "hidden32_all_recover_by_1920": h32_all_recover,
        "hidden4_all_pass_by_240": h4_all_by_240,
        "hidden32_all_pass_by_240": h32_all_by_240,
        "hidden4_final_action_accuracy": _stats(final_h4),
        "hidden32_final_action_accuracy": _stats(final_h32),
        "delayed_convergence_supported": h4_all_recover and not h4_all_by_240,
        "compact_capacity_failure_supported": (not h4_all_recover) and h32_all_recover,
        "shared_large_width_optimization_problem_supported": (not h4_all_recover) and (not h32_all_recover),
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "mechanism diagnosis of C91 large-width router quality failure",
        "records": records,
        "summary": summary,
        "C91_summary_sha256": _sha256(c91_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C92 reuses C91 seeds because it is a mechanism diagnosis",
            "C92 evaluates the deterministic synthetic routing table, not broad routing generalization",
            "C92 changes no production controller architecture",
            "C92 does not establish Gate D passage",
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
    parser.add_argument("--c91-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c91_summary_path=args.c91_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C92 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
