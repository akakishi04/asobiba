"""Evaluation helpers for C87 learned variable-step Composition routing."""
from __future__ import annotations

import torch

from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import sparse_oracle_forward
from fold_lm.v05_benchmarks.gate_d_c87_router_train import (
    ACTION_COUNT,
    ANSWER,
    ADD2,
    SUB2,
    apply_actions,
    event_context,
    oracle_actions,
)

_ACTION_DEPTH = torch.tensor((0, 1, 2, 1, 2), dtype=torch.int64)


@torch.inference_mode()
def evaluate_router(model, router, examples):
    model.eval()
    router.eval()
    device = next(model.parameters()).device
    parameter = next(model.parameters())
    initial = examples.initial_values.to(device)
    operations = examples.operations.to(device)
    operands = examples.operands.to(device)
    targets = examples.targets.to(device)

    oracle_output, _calls = sparse_oracle_forward(model, initial, operations, operands)

    working = model.core.initial_working_state(
        initial.shape[0], device=device, dtype=parameter.dtype
    ).clone()
    working[:, 0, 0] = initial.to(parameter.dtype) / float(model.config.state_scale)
    outputs = [working[:, 0, 0].clone()]

    correct = 0
    total = 0
    class_correct = [0] * ACTION_COUNT
    class_total = [0] * ACTION_COUNT
    predicted_actions = []

    for event in range(model.config.operation_steps):
        op = operations[:, event]
        operand = operands[:, event]
        context = event_context(model, operand, parameter.dtype)
        predicted = router(working, context, op).argmax(dim=-1)
        oracle = oracle_actions(op, operand)
        correct += int((predicted == oracle).sum().item())
        total += int(predicted.numel())
        for action in range(ACTION_COUNT):
            mask = oracle == action
            class_total[action] += int(mask.sum().item())
            class_correct[action] += int(((predicted == action) & mask).sum().item())
        predicted_actions.append(predicted)
        working = apply_actions(model, working, predicted)
        outputs.append(working[:, 0, 0].clone())

    learned = torch.stack(outputs, dim=1)
    predicted_values = (learned * float(model.config.state_scale)).round().to(torch.int64)
    exact = float((predicted_values == targets).all(dim=1).float().mean().item())
    oracle_values = (oracle_output * float(model.config.state_scale)).round().to(torch.int64)
    oracle_exact = float((oracle_values == targets).all(dim=1).float().mean().item())

    actions = torch.cat(predicted_actions, dim=0)
    depth_table = _ACTION_DEPTH.to(device=actions.device)
    depths = depth_table.index_select(0, actions)
    mean_steps = float(depths.float().mean().item())
    zero_rate = float((actions == ANSWER).float().mean().item())
    two_rate = float(((actions == ADD2) | (actions == SUB2)).float().mean().item())

    recalls = {
        str(action): class_correct[action] / class_total[action]
        for action in range(ACTION_COUNT)
    }
    return {
        "action_accuracy": correct / total,
        "class_recall": recalls,
        "minimum_class_recall": min(recalls.values()),
        "learned_trajectory_exact_accuracy": exact,
        "oracle_trajectory_exact_accuracy": oracle_exact,
        "exact_delta_vs_oracle": exact - oracle_exact,
        "learned_vs_oracle_outputs_allclose": bool(
            torch.allclose(learned, oracle_output, rtol=5e-4, atol=1e-4)
        ),
        "learned_vs_oracle_output_max_abs_gap": float(
            (learned - oracle_output).abs().max().item()
        ),
        "logical_compute_steps_per_event": mean_steps,
        "zero_step_event_rate": zero_rate,
        "two_step_event_rate": two_rate,
        "logical_compute_reduction_vs_fixed_max": 1.0 - mean_steps / 2.0,
    }
