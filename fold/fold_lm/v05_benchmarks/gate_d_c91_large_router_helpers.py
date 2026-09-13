"""Helpers for C91 selected hidden=4 large-width router/runtime validation."""
from __future__ import annotations

import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05_benchmarks.gate_d_c87_router_train import oracle_actions
from fold_lm.v05_benchmarks.gate_d_c89_runtime_crossover_helpers import (
    BATCH,
    EVENTS,
    _apply_oracle_actions,
    _event_context,
    fixed_max_forward,
    make_runtime_inputs,
    rank_for_width,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    _allocate_shared,
    _storage_bytes,
)
from fold_lm.v05.modules import LearnedCoreConfig

WIDTHS = (3072, 5120)
HIDDEN_WIDTH = 4
ACTION_COUNT = 5
ROUNDS = 7
WARMUP = 5
TRAIN_STEPS = 240
TRAIN_BATCH = 256


def build_objects(width: int, device: torch.device):
    config = LearnedCoreConfig(width=width, slots=1, modules=2, hidden_mult=2)
    core = _allocate_shared(config, rank_for_width(width), device).eval()
    router = SupervisedActionRouter(
        ActionRouterConfig(
            width=width,
            operation_vocab_size=2,
            hidden_width=HIDDEN_WIDTH,
            action_count=ACTION_COUNT,
        )
    ).to(device)
    return core, router


def build_router_examples(width: int, device: torch.device):
    working, operations, operands = make_runtime_inputs(width, device)
    states = []
    contexts = []
    ops = []
    labels = []
    current = working.clone()
    for event in range(EVENTS):
        op = operations[:, event]
        operand = operands[:, event]
        context = _event_context(width, operand, current.dtype)
        action = oracle_actions(op, operand)
        states.append(current.clone())
        contexts.append(context)
        ops.append(op.clone())
        labels.append(action.clone())
        current = _apply_oracle_actions(
            # only state evolution semantics are needed here; caller supplies core later
            # placeholder handled by train_and_validate_router
            None, current, action
        )
    raise RuntimeError("build_router_examples requires core-aware wrapper")


def train_and_validate_router(core, router, width: int, device: torch.device, seed: int):
    working, operations, operands = make_runtime_inputs(width, device)
    states = []
    contexts = []
    ops = []
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
            ops.append(op.clone())
            labels.append(action.clone())
            current = _apply_oracle_actions(core, current, action)
    states = torch.cat(states, dim=0)
    contexts = torch.cat(contexts, dim=0)
    ops = torch.cat(ops, dim=0)
    labels = torch.cat(labels, dim=0)

    torch.manual_seed(seed)
    optimizer = torch.optim.AdamW(router.parameters(), lr=0.01, weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    for _ in range(TRAIN_STEPS):
        index = torch.randint(states.shape[0], (TRAIN_BATCH,), generator=generator).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = router(
            states.index_select(0, index),
            contexts.index_select(0, index),
            ops.index_select(0, index),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, index))
        if not torch.isfinite(loss):
            raise RuntimeError("C91 router training produced non-finite loss")
        loss.backward()
        optimizer.step()

    router.eval()
    with torch.inference_mode():
        predicted = router(states, contexts, ops).argmax(dim=-1)
    accuracy = float((predicted == labels).float().mean().item())
    recalls = []
    for action in range(ACTION_COUNT):
        mask = labels == action
        recalls.append(float((predicted[mask] == action).float().mean().item()))
    return accuracy, min(recalls)


def learned_sparse_forward(core, router, working, operations, operands):
    current = working.clone()
    width = current.shape[-1]
    for event in range(EVENTS):
        op = operations[:, event]
        operand = operands[:, event]
        context = _event_context(width, operand, current.dtype)
        action = router(current, context, op).argmax(dim=-1)
        current = _apply_oracle_actions(core, current, action)
    return current


def _iterations(width: int) -> int:
    return 10 if width == 3072 else 5


def _event_ms(fn, iterations: int) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / iterations


def _wall_ms(fn, iterations: int) -> float:
    torch.cuda.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def measure(width: int, device: torch.device, seed: int) -> dict:
    core, router = build_objects(width, device)
    action_accuracy, min_recall = train_and_validate_router(core, router, width, device, seed)
    working, operations, operands = make_runtime_inputs(width, device)
    fixed_fn = lambda: fixed_max_forward(core, working, operations, operands)
    learned_fn = lambda: learned_sparse_forward(core, router, working, operations, operands)

    with torch.inference_mode():
        fixed_out = fixed_fn()
        learned_out = learned_fn()
        allclose = bool(torch.allclose(learned_out, fixed_out, rtol=5e-4, atol=1e-4))
        max_abs = float((learned_out - fixed_out).abs().max().item())
        for _ in range(WARMUP):
            fixed_fn(); learned_fn()
        torch.cuda.synchronize()
        iterations = _iterations(width)
        fixed_device = []
        learned_device = []
        fixed_wall = []
        learned_wall = []
        device_ratio = []
        wall_ratio = []
        for round_index in range(ROUNDS):
            order = ("fixed", "learned") if round_index % 2 == 0 else ("learned", "fixed")
            d = {}
            w = {}
            for name in order:
                fn = fixed_fn if name == "fixed" else learned_fn
                d[name] = _event_ms(fn, iterations)
                w[name] = _wall_ms(fn, iterations)
            fixed_device.append(d["fixed"])
            learned_device.append(d["learned"])
            fixed_wall.append(w["fixed"])
            learned_wall.append(w["learned"])
            device_ratio.append(d["learned"] / d["fixed"])
            wall_ratio.append(w["learned"] / w["fixed"])

    core_bytes = _storage_bytes(core)
    router_bytes = _storage_bytes(router)
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        learned_fn()
    torch.cuda.synchronize()
    return {
        "width": width,
        "rank": rank_for_width(width),
        "batch": BATCH,
        "router_hidden_width": HIDDEN_WIDTH,
        "action_accuracy": action_accuracy,
        "minimum_class_recall": min_recall,
        "output_allclose": allclose,
        "output_max_abs_gap": max_abs,
        "core_persistent_bytes": core_bytes,
        "router_persistent_bytes": router_bytes,
        "router_over_core_persistent_ratio": router_bytes / core_bytes,
        "fixed_device_ms": _stats(fixed_device),
        "learned_device_ms": _stats(learned_device),
        "learned_over_fixed_device": _stats(device_ratio),
        "fixed_wall_ms": _stats(fixed_wall),
        "learned_wall_ms": _stats(learned_wall),
        "learned_over_fixed_wall": _stats(wall_ratio),
        "peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
    }
