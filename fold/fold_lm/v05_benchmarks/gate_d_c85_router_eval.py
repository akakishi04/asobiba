"""Evaluation helper for C85 supervised Condition action router."""
from __future__ import annotations

import torch

from fold_lm.v05.controller import ANSWER_ACTION, COMPUTE_ACTION


@torch.inference_mode()
def evaluate(model, router, examples, *, batch_size: int = 1024):
    model.eval()
    router.eval()
    device = next(model.parameters()).device
    oracle_exact = learned_exact = total_examples = 0
    total_events = correct_actions = answer_actions = 0
    hold_total = hold_correct = update_total = update_correct = 0

    for start in range(0, examples.size, batch_size):
        end = min(start + batch_size, examples.size)
        initial = examples.initial_values[start:end].to(device)
        operations = examples.operations[start:end].to(device)
        candidates = examples.candidates[start:end].to(device)
        targets = examples.targets[start:end].to(device)
        oracle = model.state_embedding(initial).unsqueeze(1)
        learned = oracle.clone()
        oracle_logits = [model._decode(oracle)]
        learned_logits = [model._decode(learned)]

        for step in range(model.config.operation_steps):
            op = operations[:, step]
            context = model.event_embedding(candidates[:, step]).unsqueeze(1)

            oracle_update = model.core(oracle, context, route_index=model.config.update_route)
            oracle = torch.where(op.bool().view(-1, 1, 1), oracle_update, oracle)
            oracle_logits.append(model._decode(oracle))

            action = router(learned, context, op).argmax(dim=-1)
            learned_update = model.core(learned, context, route_index=model.config.update_route)
            learned = torch.where(
                (action == COMPUTE_ACTION).view(-1, 1, 1), learned_update, learned
            )
            learned_logits.append(model._decode(learned))

            match = action == op
            correct_actions += int(match.sum().item())
            answer_actions += int((action == ANSWER_ACTION).sum().item())
            total_events += int(action.numel())
            hold = op == 0
            update = op == 1
            hold_total += int(hold.sum().item())
            update_total += int(update.sum().item())
            hold_correct += int((match & hold).sum().item())
            update_correct += int((match & update).sum().item())

        oracle_pred = torch.stack(oracle_logits, dim=1).argmax(dim=-1)
        learned_pred = torch.stack(learned_logits, dim=1).argmax(dim=-1)
        oracle_exact += int((oracle_pred == targets).all(dim=1).sum().item())
        learned_exact += int((learned_pred == targets).all(dim=1).sum().item())
        total_examples += int(targets.shape[0])

    compute_rate = 1.0 - answer_actions / total_events
    return {
        "examples": total_examples,
        "oracle_exact_accuracy": oracle_exact / total_examples,
        "learned_exact_accuracy": learned_exact / total_examples,
        "exact_delta_vs_oracle": (learned_exact - oracle_exact) / total_examples,
        "action_accuracy": correct_actions / total_events,
        "hold_answer_recall": hold_correct / hold_total,
        "update_compute_recall": update_correct / update_total,
        "logical_compute_actions_per_event": compute_rate,
        "logical_answer_rate": 1.0 - compute_rate,
    }
