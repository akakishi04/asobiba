"""Helpers for C86 variable-step oracle composition baseline."""
from __future__ import annotations

import torch
from torch.nn import functional as F


MAX_UNIT_STEPS = 2


def _initial_working(model, initial_values: torch.Tensor) -> torch.Tensor:
    parameter = next(model.parameters())
    working = model.core.initial_working_state(
        initial_values.shape[0],
        device=initial_values.device,
        dtype=parameter.dtype,
    ).clone()
    working[:, 0, 0] = initial_values.to(parameter.dtype) / float(model.config.state_scale)
    return working


def _unit_context(model, batch: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    context = torch.zeros(batch, 1, model.config.width, device=device, dtype=dtype)
    context[:, 0, 1] = 1.0 / float(model.config.state_scale)
    context[:, 0, 2] = 1.0
    return context


def fixed_max_forward(model, initial_values, operations, operands):
    """Two substeps/event for the whole batch, masking inactive results."""
    working = _initial_working(model, initial_values)
    outputs = [working[:, 0, 0]]
    for event in range(model.config.operation_steps):
        for unit_step in range(1, MAX_UNIT_STEPS + 1):
            context = _unit_context(model, working.shape[0], working.device, working.dtype)
            add_state = model.core(working, context, route_index=model.config.add_route)
            sub_state = model.core(working, context, route_index=model.config.sub_route)
            selected = torch.where(
                operations[:, event].bool().view(-1, 1, 1),
                sub_state,
                add_state,
            )
            active = (operands[:, event] >= unit_step).view(-1, 1, 1)
            working = torch.where(active, selected, working)
        outputs.append(working[:, 0, 0])
    return torch.stack(outputs, dim=1)


@torch.inference_mode()
def sparse_oracle_forward(model, initial_values, operations, operands):
    """Gather only active rows and execute exactly operand-count unit steps."""
    working = _initial_working(model, initial_values)
    outputs = [working[:, 0, 0].clone()]
    core_calls = 0
    for event in range(model.config.operation_steps):
        for unit_step in range(1, MAX_UNIT_STEPS + 1):
            active = operands[:, event] >= unit_step
            if not bool(active.any().item()):
                continue
            next_working = working.clone()
            for operation, route in (
                (0, model.config.add_route),
                (1, model.config.sub_route),
            ):
                index = torch.nonzero(active & (operations[:, event] == operation), as_tuple=False).flatten()
                if index.numel() == 0:
                    continue
                subset = working.index_select(0, index)
                context = _unit_context(model, subset.shape[0], subset.device, subset.dtype)
                updated = model.core(subset, context, route_index=route)
                next_working.index_copy_(0, index, updated)
                core_calls += 1
            working = next_working
        outputs.append(working[:, 0, 0].clone())
    return torch.stack(outputs, dim=1), core_calls


def train_unit_step_model(model, train, *, seed: int, steps: int = 300, lr: float = 0.005):
    model.core.set_execution_mode("materialized")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    device = next(model.parameters()).device
    loss = None
    model.train()
    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (64,), generator=sampler)
        initial = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(model.config.state_scale)
        optimizer.zero_grad(set_to_none=True)
        predicted = fixed_max_forward(model, initial, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C86 seed={seed} non-finite loss")
        loss.backward()
        optimizer.step()
        if step in (75, 150, 225, 300):
            print(f"[C86] seed={seed} train step={step}/{steps} loss={float(loss.detach()):.8f}", flush=True)
    model.core.set_execution_mode("gemm_native")
    return float(loss.detach())


@torch.inference_mode()
def evaluate_variable_step(model, examples):
    model.eval()
    device = next(model.parameters()).device
    initial = examples.initial_values.to(device)
    operations = examples.operations.to(device)
    operands = examples.operands.to(device)
    targets = examples.targets.to(device)

    fixed = fixed_max_forward(model, initial, operations, operands)
    sparse, core_calls = sparse_oracle_forward(model, initial, operations, operands)
    target_values = targets.to(dtype=fixed.dtype) / float(model.config.state_scale)

    fixed_values = (fixed * float(model.config.state_scale)).round().to(torch.int64)
    sparse_values = (sparse * float(model.config.state_scale)).round().to(torch.int64)
    fixed_exact = float((fixed_values == targets).all(dim=1).float().mean().item())
    sparse_exact = float((sparse_values == targets).all(dim=1).float().mean().item())

    total_events = int(operands.numel())
    logical_steps = int(operands.sum().item())
    zero_events = int((operands == 0).sum().item())
    two_events = int((operands == 2).sum().item())
    mean_steps = logical_steps / total_events
    return {
        "examples": examples.size,
        "fixed_max_trajectory_exact_accuracy": fixed_exact,
        "sparse_oracle_trajectory_exact_accuracy": sparse_exact,
        "sparse_minus_fixed_exact_delta": sparse_exact - fixed_exact,
        "fixed_max_mse": float(F.mse_loss(fixed, target_values).item()),
        "sparse_mse": float(F.mse_loss(sparse, target_values).item()),
        "outputs_allclose": bool(torch.allclose(sparse, fixed, rtol=5e-4, atol=1e-4)),
        "output_max_abs_gap": float((sparse - fixed).abs().max().item()),
        "logical_compute_steps_per_event": mean_steps,
        "fixed_max_steps_per_event": float(MAX_UNIT_STEPS),
        "logical_compute_reduction_vs_fixed_max": 1.0 - mean_steps / MAX_UNIT_STEPS,
        "zero_step_event_rate": zero_events / total_events,
        "two_step_event_rate": two_events / total_events,
        "sparse_grouped_core_calls": core_calls,
    }
