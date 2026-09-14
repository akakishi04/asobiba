"""Helpers for C95 prospective fixed control-lane validation."""
from __future__ import annotations

import torch
from torch.nn import functional as F

from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    _allocate_shared,
    _storage_bytes,
)
from fold_lm.v05_benchmarks.gate_d_c87_router_train import ACTION_COUNT, oracle_actions
from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    BATCH,
    EVENTS,
    _apply_oracle_actions,
    _event_context,
    make_runtime_inputs,
    rank_for_width,
)
from fold_lm.v05_benchmarks.gate_d_router_control_lane_diagnosis import _ControlLaneRouter
from fold_lm.v05.modules import LearnedCoreConfig

TRAIN_STEPS = 480
TRAIN_BATCH = 256
LR = 0.01
ROUTER_SEED_OFFSET = 91000
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.99


def _split_rows(device: torch.device):
    rows = torch.arange(BATCH, device=device)
    validation = rows % 5 == 0
    train = ~validation
    return torch.nonzero(train, as_tuple=False).flatten(), torch.nonzero(validation, as_tuple=False).flatten()


def _pack_by_rows(tensor: torch.Tensor, row_index: torch.Tensor) -> torch.Tensor:
    return tensor.index_select(0, row_index)


def build_split_examples(width: int, device: torch.device, seed: int):
    torch.manual_seed(seed + 50000)
    config = LearnedCoreConfig(width=width, slots=1, modules=2, hidden_mult=2)
    core = _allocate_shared(config, rank_for_width(width), device).eval()
    working, operations, operands = make_runtime_inputs(width, device)
    train_rows, validation_rows = _split_rows(device)

    train_parts = [[], [], [], []]
    validation_parts = [[], [], [], []]
    current = working.clone()
    with torch.inference_mode():
        for event in range(EVENTS):
            op = operations[:, event]
            operand = operands[:, event]
            context = _event_context(width, operand, current.dtype)
            labels = oracle_actions(op, operand)
            values = (current.clone(), context, op.clone(), labels.clone())
            for bucket, row_index in (
                (train_parts, train_rows),
                (validation_parts, validation_rows),
            ):
                for index, value in enumerate(values):
                    bucket[index].append(_pack_by_rows(value, row_index))
            current = _apply_oracle_actions(core, current, labels)

    def finish(parts):
        packed = tuple(torch.cat(part, dim=0) for part in parts)
        labels = packed[-1]
        class_counts = [int((labels == action).sum().item()) for action in range(ACTION_COUNT)]
        if min(class_counts) <= 0:
            raise RuntimeError(f"C95 split lost an action class: {class_counts}")
        return packed, class_counts

    train, train_counts = finish(train_parts)
    validation, validation_counts = finish(validation_parts)
    return core, train, validation, train_counts, validation_counts


@torch.inference_mode()
def evaluate_router(router, examples):
    states, contexts, op_ids, labels = examples
    router.eval()
    predicted = router(states, contexts, op_ids).argmax(dim=-1)
    correct = int((predicted == labels).sum().item())
    total = int(labels.numel())
    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        recalls.append(float((predicted[mask] == action).float().mean().item()))
    return {
        "action_accuracy": correct / total,
        "minimum_class_recall": min(recalls),
        "action_flip_count": total - correct,
        "example_count": total,
    }


def train_and_measure(width: int, device: torch.device, seed: int) -> dict:
    _core, train, validation, train_counts, validation_counts = build_split_examples(
        width, device, seed
    )
    torch.manual_seed(seed + ROUTER_SEED_OFFSET)
    router = _ControlLaneRouter().to(device)
    optimizer = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    states, contexts, op_ids, labels = train
    router.train()
    loss = None
    for _step in range(TRAIN_STEPS):
        index = torch.randint(states.shape[0], (TRAIN_BATCH,), generator=generator).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            op_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError(f"C95 non-finite loss width={width} seed={seed}")
        loss.backward()
        optimizer.step()

    train_metrics = evaluate_router(router, train)
    validation_metrics = evaluate_router(router, validation)
    validation_metrics["quality_passed"] = (
        validation_metrics["action_accuracy"] >= MIN_ACTION_ACCURACY
        and validation_metrics["minimum_class_recall"] >= MIN_CLASS_RECALL
    )
    return {
        "width": width,
        "seed": seed,
        "router_persistent_bytes": _storage_bytes(router),
        "train_class_counts": train_counts,
        "validation_class_counts": validation_counts,
        "final_loss": float(loss.detach().item()),
        "train": train_metrics,
        "validation": validation_metrics,
    }
