"""Training helpers for C87 learned variable-step Composition routing."""
from __future__ import annotations

import torch
from torch.nn import functional as F

ANSWER = 0
ADD1 = 1
ADD2 = 2
SUB1 = 3
SUB2 = 4
ACTION_COUNT = 5


def oracle_actions(operations: torch.Tensor, operands: torch.Tensor) -> torch.Tensor:
    if operations.shape != operands.shape:
        raise ValueError("operations/operands shape mismatch")
    labels = torch.zeros_like(operands)
    labels = torch.where((operations == 0) & (operands == 1), torch.full_like(labels, ADD1), labels)
    labels = torch.where((operations == 0) & (operands == 2), torch.full_like(labels, ADD2), labels)
    labels = torch.where((operations == 1) & (operands == 1), torch.full_like(labels, SUB1), labels)
    labels = torch.where((operations == 1) & (operands == 2), torch.full_like(labels, SUB2), labels)
    return labels


def event_context(model, operands: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    context = torch.zeros(
        operands.shape[0], 1, model.config.width,
        device=operands.device, dtype=dtype,
    )
    context[:, 0, 1] = operands.to(dtype) / float(model.config.state_scale)
    context[:, 0, 2] = 1.0
    return context


def apply_actions(model, working: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
    next_working = working
    for unit_step in (1, 2):
        updated_all = next_working.clone()
        for action_ids, route in (
            ((ADD1, ADD2), model.config.add_route),
            ((SUB1, SUB2), model.config.sub_route),
        ):
            if unit_step == 1:
                active = (actions == action_ids[0]) | (actions == action_ids[1])
            else:
                active = actions == action_ids[1]
            index = torch.nonzero(active, as_tuple=False).flatten()
            if index.numel() == 0:
                continue
            subset = next_working.index_select(0, index)
            context = torch.zeros_like(subset)
            context[:, 0, 1] = 1.0 / float(model.config.state_scale)
            context[:, 0, 2] = 1.0
            updated = model.core(subset, context, route_index=route)
            updated_all.index_copy_(0, index, updated)
        next_working = updated_all
    return next_working


def build_router_examples(model, examples, device: torch.device):
    parameter = next(model.parameters())
    initial = examples.initial_values.to(device)
    operations = examples.operations.to(device)
    operands = examples.operands.to(device)
    working = model.core.initial_working_state(
        initial.shape[0], device=device, dtype=parameter.dtype
    ).clone()
    working[:, 0, 0] = initial.to(parameter.dtype) / float(model.config.state_scale)

    states = []
    contexts = []
    op_ids = []
    labels = []
    with torch.inference_mode():
        for event in range(model.config.operation_steps):
            op = operations[:, event]
            operand = operands[:, event]
            action = oracle_actions(op, operand)
            states.append(working.clone())
            contexts.append(event_context(model, operand, parameter.dtype))
            op_ids.append(op.clone())
            labels.append(action.clone())
            working = apply_actions(model, working, action)
    return (
        torch.cat(states, dim=0),
        torch.cat(contexts, dim=0),
        torch.cat(op_ids, dim=0),
        torch.cat(labels, dim=0),
    )


def train_router(router, states, contexts, op_ids, labels, *, seed: int, steps: int = 240):
    optimizer = torch.optim.AdamW(router.parameters(), lr=0.01, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    loss = None
    for step in range(1, steps + 1):
        index = torch.randint(states.shape[0], (256,), generator=generator, device="cpu").to(states.device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            op_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError("C87 router training produced non-finite loss")
        loss.backward()
        optimizer.step()
        if step in (60, 120, 180, 240):
            print(f"[C87] router step={step}/{steps} loss={float(loss.detach()):.8f}", flush=True)
    return float(loss.detach())
