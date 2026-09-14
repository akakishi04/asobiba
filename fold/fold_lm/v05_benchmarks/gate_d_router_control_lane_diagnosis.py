"""C93: diagnose whether width-coupled router features cause C91/C92 failure.

C92 showed that merely training longer does not reliably recover the current
full-width router at width 3072/5120.  C93 keeps the same failure seeds and
optimizer schedule, but compares the current hidden=4 router against a
diagnostic fixed-width control-lane router.  The control-lane variant reads
only the first four working/context channels plus a four-dimensional operation
embedding, so its input/parameter shape does not grow with core width.

This is a mechanism diagnosis only.  The diagnostic router is not production
code and the reused seeds are not prospective generalization evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05.modules import LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    _allocate_shared,
    _storage_bytes,
)
from fold_lm.v05_benchmarks.gate_d_c87_router_train import ACTION_COUNT, oracle_actions
from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    EVENTS,
    _apply_oracle_actions,
    _event_context,
    make_runtime_inputs,
    rank_for_width,
)

EXPERIMENT_ID = "C93-v5d-router-control-lane-diagnosis"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261141, 20261142, 20261143)
WIDTHS = (3072, 5120)
HIDDEN_WIDTH = 4
CONTROL_WIDTH = 4
TRAIN_STEPS = 240
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


class _ControlLaneRouter(nn.Module):
    """Diagnostic width-independent router using a four-channel control lane."""

    def __init__(self) -> None:
        super().__init__()
        self.operation_embedding = nn.Embedding(2, CONTROL_WIDTH)
        self.norm = nn.LayerNorm(CONTROL_WIDTH * 3)
        self.hidden = nn.Linear(CONTROL_WIDTH * 3, HIDDEN_WIDTH)
        self.activation = nn.GELU()
        self.action_head = nn.Linear(HIDDEN_WIDTH, ACTION_COUNT)

    def forward(self, working, context, operation_ids):
        state = working[:, :, :CONTROL_WIDTH].mean(dim=1)
        event = context[:, :, :CONTROL_WIDTH].mean(dim=1)
        operation = self.operation_embedding(operation_ids)
        feature = torch.cat((state, event, operation), dim=-1)
        return self.action_head(self.activation(self.hidden(self.norm(feature))))


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
        for event_index in range(EVENTS):
            op = operations[:, event_index]
            operand = operands[:, event_index]
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
        "quality_passed": (
            accuracy >= MIN_ACTION_ACCURACY and minimum_recall >= MIN_CLASS_RECALL
        ),
    }


def _train_variant(width: int, seed: int, variant: str, device: torch.device):
    states, contexts, op_ids, labels = _build_examples(width, device, seed)
    if variant == "full_width":
        torch.manual_seed(seed)
        router = SupervisedActionRouter(
            ActionRouterConfig(
                width=width,
                operation_vocab_size=2,
                hidden_width=HIDDEN_WIDTH,
                action_count=ACTION_COUNT,
            )
        ).to(device)
    elif variant == "control_lane":
        torch.manual_seed(seed)
        router = _ControlLaneRouter().to(device)
    else:
        raise ValueError(f"unknown C93 variant: {variant}")

    optimizer = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    loss = None
    for _step in range(1, TRAIN_STEPS + 1):
        index = torch.randint(
            states.shape[0], (TRAIN_BATCH,), generator=generator
        ).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            op_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C93 non-finite loss width={width} seed={seed} variant={variant}"
            )
        loss.backward()
        optimizer.step()

    metrics = _evaluate(router, states, contexts, op_ids, labels)
    metrics.update(
        {
            "width": width,
            "seed": seed,
            "variant": variant,
            "hidden_width": HIDDEN_WIDTH,
            "control_width": None if variant == "full_width" else CONTROL_WIDTH,
            "router_persistent_bytes": _storage_bytes(router),
            "final_loss": float(loss.detach().item()),
        }
    )
    return metrics


def run(*, protected_result_path: Path, c92_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C93 requires CUDA")
    c92 = json.loads(c92_summary_path.read_text(encoding="utf-8"))
    if c92.get("experiment_id") != "C92-v5d-router-large-width-convergence-diagnosis":
        raise RuntimeError("C93 requires C92 summary")
    if c92.get("status") != "PASS" or not bool(
        c92.get("summary", {}).get("shared_large_width_optimization_problem_supported")
    ):
        raise RuntimeError("C93 requires accepted C92 large-width optimization diagnosis")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for width in WIDTHS:
        for seed in SEEDS:
            for variant in ("full_width", "control_lane"):
                row = _train_variant(width, seed, variant, device)
                records.append(row)
                print(
                    f"[C93] width={width} seed={seed} variant={variant} "
                    f"action={row['action_accuracy']:.6f} "
                    f"class_min={row['minimum_class_recall']:.6f} "
                    f"bytes={row['router_persistent_bytes']} "
                    f"pass={row['quality_passed']}",
                    flush=True,
                )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C93")

    full = [row for row in records if row["variant"] == "full_width"]
    lane = [row for row in records if row["variant"] == "control_lane"]
    full_all_pass = all(bool(row["quality_passed"]) for row in full)
    lane_all_pass = all(bool(row["quality_passed"]) for row in lane)
    full_bytes = [float(row["router_persistent_bytes"]) for row in full]
    lane_bytes = [float(row["router_persistent_bytes"]) for row in lane]
    paired_byte_ratios = [
        lane_row["router_persistent_bytes"] / full_row["router_persistent_bytes"]
        for full_row, lane_row in zip(full, lane)
    ]
    summary = {
        "widths": list(WIDTHS),
        "seeds": list(SEEDS),
        "reuses_c92_failure_seeds_for_mechanism_diagnosis": True,
        "hidden_width": HIDDEN_WIDTH,
        "control_width": CONTROL_WIDTH,
        "training_steps": TRAIN_STEPS,
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "full_width_all_pass": full_all_pass,
        "control_lane_all_pass": lane_all_pass,
        "full_width_action_accuracy": _stats(
            [float(row["action_accuracy"]) for row in full]
        ),
        "control_lane_action_accuracy": _stats(
            [float(row["action_accuracy"]) for row in lane]
        ),
        "full_width_minimum_class_recall": _stats(
            [float(row["minimum_class_recall"]) for row in full]
        ),
        "control_lane_minimum_class_recall": _stats(
            [float(row["minimum_class_recall"]) for row in lane]
        ),
        "full_width_router_persistent_bytes": _stats(full_bytes),
        "control_lane_router_persistent_bytes": _stats(lane_bytes),
        "control_lane_over_full_width_bytes": _stats(paired_byte_ratios),
        "width_coupled_representation_problem_supported": (
            lane_all_pass and not full_all_pass
        ),
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "mechanism diagnosis of width-coupled router representation",
        "records": records,
        "summary": summary,
        "C92_summary_sha256": _sha256(c92_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C93 reuses C92 failure seeds because it is a mechanism diagnosis",
            "the control-lane router is diagnostic benchmark code, not production code",
            "the current Composition runtime encoding places routing-relevant values in the first control channels",
            "C93 does not establish Gate D passage",
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
    parser.add_argument("--c92-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c92_summary_path=args.c92_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C93 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
