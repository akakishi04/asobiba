"""Runtime helpers for C88 learned adaptive-compute wall-clock validation."""
from __future__ import annotations

import statistics
import time

import torch

from fold_lm.v05_benchmarks.gate_d_c86_variable_step_helpers import fixed_max_forward
from fold_lm.v05_benchmarks.gate_d_c87_router_train import apply_actions, event_context

WARMUP = 20
ITERATIONS = 100
ROUNDS = 9


def learned_sparse_forward(model, router, initial_values, operations, operands):
    parameter = next(model.parameters())
    working = model.core.initial_working_state(
        initial_values.shape[0], device=initial_values.device, dtype=parameter.dtype
    ).clone()
    working[:, 0, 0] = initial_values.to(parameter.dtype) / float(model.config.state_scale)
    outputs = [working[:, 0, 0].clone()]
    for event in range(model.config.operation_steps):
        op = operations[:, event]
        operand = operands[:, event]
        context = event_context(model, operand, parameter.dtype)
        actions = router(working, context, op).argmax(dim=-1)
        working = apply_actions(model, working, actions)
        outputs.append(working[:, 0, 0].clone())
    return torch.stack(outputs, dim=1)


def _event_ms(fn) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    for _ in range(ITERATIONS):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _wall_ms(fn) -> float:
    torch.cuda.synchronize()
    started = time.perf_counter()
    for _ in range(ITERATIONS):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - started) * 1000.0 / ITERATIONS


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def measure_pair(model, router, initial, operations, operands):
    fixed_fn = lambda: fixed_max_forward(model, initial, operations, operands)
    adaptive_fn = lambda: learned_sparse_forward(model, router, initial, operations, operands)
    with torch.inference_mode():
        for _ in range(WARMUP):
            fixed_fn(); adaptive_fn()
        torch.cuda.synchronize()
        fixed_device = []
        adaptive_device = []
        fixed_wall = []
        adaptive_wall = []
        ratios = []
        wall_ratios = []
        for round_index in range(ROUNDS):
            order = ("fixed", "adaptive") if round_index % 2 == 0 else ("adaptive", "fixed")
            device_values = {}
            wall_values = {}
            for variant in order:
                fn = fixed_fn if variant == "fixed" else adaptive_fn
                device_values[variant] = _event_ms(fn)
                wall_values[variant] = _wall_ms(fn)
            fixed_device.append(device_values["fixed"])
            adaptive_device.append(device_values["adaptive"])
            fixed_wall.append(wall_values["fixed"])
            adaptive_wall.append(wall_values["adaptive"])
            ratios.append(device_values["adaptive"] / device_values["fixed"])
            wall_ratios.append(wall_values["adaptive"] / wall_values["fixed"])
    return {
        "fixed_device_ms": _stats(fixed_device),
        "adaptive_device_ms": _stats(adaptive_device),
        "adaptive_over_fixed_device": _stats(ratios),
        "fixed_wall_ms": _stats(fixed_wall),
        "adaptive_wall_ms": _stats(adaptive_wall),
        "adaptive_over_fixed_wall": _stats(wall_ratios),
    }
