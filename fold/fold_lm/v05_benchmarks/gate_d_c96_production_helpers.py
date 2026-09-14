"""Helpers for C96 production ControlLaneActionRouter validation."""
from __future__ import annotations

import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import _storage_bytes
from fold_lm.v05_benchmarks.gate_d_c87_router_train import ACTION_COUNT, oracle_actions
from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    EVENTS,
    _apply_oracle_actions,
    _event_context,
    fixed_max_forward,
    make_runtime_inputs,
)
from fold_lm.v05_benchmarks.gate_d_c95_control_lane_helpers import build_split_examples

CONTROL_WIDTH = 4
HIDDEN_WIDTH = 4
TRAIN_STEPS = 480
TRAIN_BATCH = 256
LR = 0.01
ROUTER_SEED_OFFSET = 92000
ROUNDS = 7
WARMUP = 5
_ACTION_DEPTH = torch.tensor((0, 1, 2, 1, 2), dtype=torch.int64)


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _evaluate_actions(router, examples):
    states, contexts, op_ids, labels = examples
    router.eval()
    with torch.inference_mode():
        predicted = router(states, contexts, op_ids).argmax(dim=-1)
    correct = int((predicted == labels).sum().item())
    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        recalls.append(float((predicted[mask] == action).float().mean().item()))
    return {
        "action_accuracy": correct / int(labels.numel()),
        "minimum_class_recall": min(recalls),
        "action_flip_count": int(labels.numel()) - correct,
    }


def _train_router(router, train, seed: int):
    states, contexts, op_ids, labels = train
    optimizer = torch.optim.AdamW(router.parameters(), lr=LR, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    loss = None
    for _step in range(TRAIN_STEPS):
        index = torch.randint(states.shape[0], (TRAIN_BATCH,), generator=generator).to(states.device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            op_ids.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError("C96 production router training produced non-finite loss")
        loss.backward()
        optimizer.step()
    del optimizer
    return float(loss.detach().item())


def learned_sparse_forward(core, router, working, operations, operands):
    current = working.clone()
    width = current.shape[-1]
    for event in range(EVENTS):
        op = operations[:, event]
        operand = operands[:, event]
        context = _event_context(width, operand, current.dtype)
        actions = router(current, context, op).argmax(dim=-1)
        current = _apply_oracle_actions(core, current, actions)
    return current


def _runtime_action_metrics(core, router, working, operations, operands):
    current = working.clone()
    width = current.shape[-1]
    predicted_parts = []
    oracle_parts = []
    with torch.inference_mode():
        for event in range(EVENTS):
            op = operations[:, event]
            operand = operands[:, event]
            context = _event_context(width, operand, current.dtype)
            predicted = router(current, context, op).argmax(dim=-1)
            oracle = oracle_actions(op, operand)
            predicted_parts.append(predicted)
            oracle_parts.append(oracle)
            current = _apply_oracle_actions(core, current, predicted)
    predicted = torch.cat(predicted_parts)
    oracle = torch.cat(oracle_parts)
    correct = int((predicted == oracle).sum().item())
    recalls = []
    for action in range(ACTION_COUNT):
        mask = oracle == action
        recalls.append(float((predicted[mask] == action).float().mean().item()))
    depth = _ACTION_DEPTH.to(predicted.device).index_select(0, predicted)
    mean_steps = float(depth.float().mean().item())
    return {
        "action_accuracy": correct / int(oracle.numel()),
        "minimum_class_recall": min(recalls),
        "logical_compute_steps_per_event": mean_steps,
        "logical_compute_reduction_vs_fixed_max": 1.0 - mean_steps / 2.0,
    }


def _iterations(width: int) -> int:
    return 10 if width == 3072 else 5


def _event_ms(fn, iterations: int):
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / iterations


def _wall_ms(fn, iterations: int):
    torch.cuda.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def train_measure(width: int, device: torch.device, seed: int):
    core, train, validation, _train_counts, _validation_counts = build_split_examples(
        width, device, seed
    )
    torch.cuda.synchronize()
    free_before_router, _ = torch.cuda.mem_get_info()
    allocated_before_router = int(torch.cuda.memory_allocated())

    torch.manual_seed(seed + ROUTER_SEED_OFFSET)
    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=width,
            control_width=CONTROL_WIDTH,
            operation_vocab_size=2,
            hidden_width=HIDDEN_WIDTH,
            action_count=ACTION_COUNT,
        )
    ).to(device)
    torch.cuda.synchronize()
    free_after_router, _ = torch.cuda.mem_get_info()
    allocated_after_router = int(torch.cuda.memory_allocated())

    final_loss = _train_router(router, train, seed)
    heldout = _evaluate_actions(router, validation)

    working, operations, operands = make_runtime_inputs(width, device)
    fixed_fn = lambda: fixed_max_forward(core, working, operations, operands)
    learned_fn = lambda: learned_sparse_forward(core, router, working, operations, operands)
    runtime_actions = _runtime_action_metrics(core, router, working, operations, operands)

    with torch.inference_mode():
        fixed_out = fixed_fn()
        learned_out = learned_fn()
        output_allclose = bool(torch.allclose(learned_out, fixed_out, rtol=5e-4, atol=1e-4))
        output_max_abs_gap = float((learned_out - fixed_out).abs().max().item())
        for _ in range(WARMUP):
            fixed_fn(); learned_fn()
        torch.cuda.synchronize()
        iterations = _iterations(width)
        device_ratios = []
        wall_ratios = []
        for round_index in range(ROUNDS):
            order = ("fixed", "learned") if round_index % 2 == 0 else ("learned", "fixed")
            d = {}
            w = {}
            for name in order:
                fn = fixed_fn if name == "fixed" else learned_fn
                d[name] = _event_ms(fn, iterations)
                w[name] = _wall_ms(fn, iterations)
            device_ratios.append(d["learned"] / d["fixed"])
            wall_ratios.append(w["learned"] / w["fixed"])

    core_bytes = _storage_bytes(core)
    router_bytes = _storage_bytes(router)
    return {
        "width": width,
        "seed": seed,
        "final_router_loss": final_loss,
        "heldout": heldout,
        "runtime_actions": runtime_actions,
        "output_allclose": output_allclose,
        "output_max_abs_gap": output_max_abs_gap,
        "learned_over_fixed_device": _stats(device_ratios),
        "learned_over_fixed_wall": _stats(wall_ratios),
        "core_persistent_bytes": core_bytes,
        "router_persistent_bytes": router_bytes,
        "router_over_core_persistent_ratio": router_bytes / core_bytes,
        "router_device_free_vram_cost_bytes": int(free_before_router - free_after_router),
        "router_allocated_delta_bytes": allocated_after_router - allocated_before_router,
    }
