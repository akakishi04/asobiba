"""Training helpers for C85 supervised Condition action router."""
from __future__ import annotations

import torch
from torch.nn import functional as F


@torch.inference_mode()
def build_examples(model, examples, device: torch.device):
    working = model.state_embedding(examples.initial_values.to(device)).unsqueeze(1)
    operations = examples.operations.to(device)
    candidates = examples.candidates.to(device)
    states = []
    contexts = []
    labels = []
    for step in range(model.config.operation_steps):
        context = model.event_embedding(candidates[:, step]).unsqueeze(1)
        operation = operations[:, step]
        states.append(working.detach())
        contexts.append(context.detach())
        labels.append(operation.detach())
        update_state = model.core(working, context, route_index=model.config.update_route)
        working = torch.where(
            operation.bool().view(-1, 1, 1),
            update_state,
            working,
        )
    return torch.cat(states), torch.cat(contexts), torch.cat(labels)


def train_router(router, states, contexts, labels, *, seed: int):
    optimizer = torch.optim.AdamW(router.parameters(), lr=0.01, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 91000)
    router.train()
    loss = None
    for step in range(1, 201):
        index = torch.randint(labels.shape[0], (64,), generator=generator).to(labels.device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(states[index], contexts[index], labels[index])
        loss = F.cross_entropy(logits, labels[index])
        if not torch.isfinite(loss):
            raise RuntimeError("C85 router produced non-finite loss")
        loss.backward()
        optimizer.step()
        if step in (50, 100, 150, 200):
            print(f"[C85] router step={step}/200 loss={float(loss.detach()):.8f}", flush=True)
    return float(loss.detach())
