"""Helpers for C89 adaptive-compute width crossover diagnosis."""
from __future__ import annotations

import statistics
import time

import torch

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05.modules import LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    _allocate_shared,
    _storage_bytes,
)
from fold_lm.v05_benchmarks.gate_d_c87_router_train import (
    ADD1,
    ADD2,
    SUB1,
    SUB2,
    oracle_actions,
)

WIDTHS = (32, 128, 512, 1024, 3072, 5120)
BATCH = 216
EVENTS = 3
SLOTS = 1
MODULES = 2
HIDDEN_MULT = 2
RANK_DENOMINATOR = 16
ROUNDS = 7
MAX_RUNTIME_RATIO = 0.95


def rank_for_width(width: int) -> int:
    if width % RANK_DENOMINATOR:
        raise ValueError("C89 width must be divisible by 16")
    return width // RANK_DENOMINATOR


def _iterations(width: int) -> int:
    if width <= 128:
        return 100
    if width <= 512:
        return 50
    if width <= 1024:
        return 25
    if width <= 3072:
        return 10
    return 5


def _warmup(width: int) -> int:
    return 10 if width <= 1024 else 5


def make_runtime_inputs(width: int, device: torch.device):
    rows = torch.arange(BATCH, device=device, dtype=torch.int64)
    operations = torch.empty(BATCH, EVENTS, device=device, dtype=torch.int64)
    operands = torch.empty_like(operations)
    for event in range(EVENTS):
        operands[:, event] = (rows + event) % 3
        operations[:, event] = ((rows // 3) + event) % 2
    working = torch.zeros(BATCH, SLOTS, width, device=device)
    working[:, 0, 0] = (rows % 7).to(torch.float32) / 16.0
    return working, operations, operands


def build_runtime_objects(width: int, device: torch.device):
    config = LearnedCoreConfig(
        width=width,
        slots=SLOTS,
        modules=MODULES,
        hidden_mult=HIDDEN_MULT,
    )
    core = _allocate_shared(config, rank_for_width(width), device).eval()
    router = SupervisedActionRouter(
        ActionRouterConfig(width=width, operation_vocab_size=2, action_count=5)
    ).to(device).eval()
    return core, router


def _unit_context(width: int, count: int, device: torch.device, dtype: torch.dtype):
    context = torch.zeros(count, 1, width, device=device, dtype=dtype)
    context[:, 0, 1] = 1.0 / 16.0
    context[:, 0, 2] = 1.0
    return context


def _event_context(width: int, operands: torch.Tensor, dtype: torch.dtype):
    context = torch.zeros(
        operands.shape[0], 1, width, device=operands.device, dtype=dtype
    )
    context[:, 0, 1] = operands.to(dtype) / 16.0
    context[:, 0, 2] = 1.0
    return context


def fixed_max_forward(core, initial_working, operations, operands):
    working = initial_working.clone()
    for event in range(EVENTS):
        for unit_step in (1, 2):
            context = _unit_context(
                working.shape[-1], working.shape[0], working.device, working.dtype
            )
            add_state = core(working, context, route_index=0)
            sub_state = core(working, context, route_index=1)
            selected = torch.where(
                operations[:, event].bool().view(-1, 1, 1), sub_state, add_state
            )
            active = (operands[:, event] >= unit_step).view(-1, 1, 1)
            working = torch.where(active, selected, working)
    return working


def _apply_oracle_actions(core, working, actions):
    next_working = working
    for unit_step in (1, 2):
        updated_all = next_working.clone()
        for action_ids, route in (((ADD1, ADD2), 0), ((SUB1, SUB2), 1)):
            if unit_step == 1:
                active = (actions == action_ids[0]) | (actions == action_ids[1])
            else:
                active = actions == action_ids[1]
            index = torch.nonzero(active, as_tuple=False).flatten()
            if index.numel() == 0:
                continue
            subset = next_working.index_select(0, index)
            context = _unit_context(
                subset.shape[-1], subset.shape[0], subset.device, subset.dtype
            )
            updated = core(subset, context, route_index=route)
            updated_all.index_copy_(0, index, updated)
        next_working = updated_all
    return next_working


def oracle_sparse_forward(core, initial_working, operations, operands):
    working = initial_working.clone()
    for event in range(EVENTS):
        actions = oracle_actions(operations[:, event], operands[:, event])
        working = _apply_oracle_actions(core, working, actions)
    return working


def router_plus_oracle_sparse_forward(core, router, initial_working, operations, operands):
    working = initial_working.clone()
    width = working.shape[-1]
    for event in range(EVENTS):
        op = operations[:, event]
        operand = operands[:, event]
        context = _event_context(width, operand, working.dtype)
        # Execute the production controller cost, but keep oracle actions for the
        # runtime-crossover semantic reference so quality cannot confound timing.
        _predicted = router(working, context, op).argmax(dim=-1)
        actions = oracle_actions(op, operand)
        working = _apply_oracle_actions(core, working, actions)
    return working


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


def measure_width(width: int, device: torch.device) -> dict:
    core, router = build_runtime_objects(width, device)
    working, operations, operands = make_runtime_inputs(width, device)
    fixed_fn = lambda: fixed_max_forward(core, working, operations, operands)
    oracle_fn = lambda: oracle_sparse_forward(core, working, operations, operands)
    routed_fn = lambda: router_plus_oracle_sparse_forward(
        core, router, working, operations, operands
    )

    with torch.inference_mode():
        fixed_out = fixed_fn()
        oracle_out = oracle_fn()
        routed_out = routed_fn()
        oracle_allclose = bool(torch.allclose(oracle_out, fixed_out, rtol=5e-4, atol=1e-4))
        routed_allclose = bool(torch.allclose(routed_out, fixed_out, rtol=5e-4, atol=1e-4))
        for _ in range(_warmup(width)):
            fixed_fn(); oracle_fn(); routed_fn()
        torch.cuda.synchronize()

        iterations = _iterations(width)
        samples = {
            name: {"device": [], "wall": []}
            for name in ("fixed", "oracle_sparse", "router_plus_sparse")
        }
        device_ratios = {"oracle_sparse": [], "router_plus_sparse": []}
        wall_ratios = {"oracle_sparse": [], "router_plus_sparse": []}
        for round_index in range(ROUNDS):
            order = (
                ("fixed", "oracle_sparse", "router_plus_sparse")
                if round_index % 2 == 0
                else ("router_plus_sparse", "oracle_sparse", "fixed")
            )
            round_device = {}
            round_wall = {}
            for name in order:
                fn = {
                    "fixed": fixed_fn,
                    "oracle_sparse": oracle_fn,
                    "router_plus_sparse": routed_fn,
                }[name]
                round_device[name] = _event_ms(fn, iterations)
                round_wall[name] = _wall_ms(fn, iterations)
                samples[name]["device"].append(round_device[name])
                samples[name]["wall"].append(round_wall[name])
            for name in ("oracle_sparse", "router_plus_sparse"):
                device_ratios[name].append(round_device[name] / round_device["fixed"])
                wall_ratios[name].append(round_wall[name] / round_wall["fixed"])

    core_bytes = _storage_bytes(core)
    router_bytes = _storage_bytes(router)
    return {
        "width": width,
        "rank": rank_for_width(width),
        "batch": BATCH,
        "logical_compute_reduction_vs_fixed_max": 0.5,
        "oracle_output_allclose": oracle_allclose,
        "router_plus_sparse_output_allclose": routed_allclose,
        "oracle_output_max_abs_gap": float((oracle_out - fixed_out).abs().max().item()),
        "router_plus_sparse_output_max_abs_gap": float((routed_out - fixed_out).abs().max().item()),
        "core_persistent_bytes": core_bytes,
        "router_persistent_bytes": router_bytes,
        "router_over_core_persistent_ratio": router_bytes / core_bytes,
        "fixed_device_ms": _stats(samples["fixed"]["device"]),
        "oracle_sparse_device_ms": _stats(samples["oracle_sparse"]["device"]),
        "router_plus_sparse_device_ms": _stats(samples["router_plus_sparse"]["device"]),
        "oracle_sparse_over_fixed_device": _stats(device_ratios["oracle_sparse"]),
        "router_plus_sparse_over_fixed_device": _stats(device_ratios["router_plus_sparse"]),
        "fixed_wall_ms": _stats(samples["fixed"]["wall"]),
        "oracle_sparse_wall_ms": _stats(samples["oracle_sparse"]["wall"]),
        "router_plus_sparse_wall_ms": _stats(samples["router_plus_sparse"]["wall"]),
        "oracle_sparse_over_fixed_wall": _stats(wall_ratios["oracle_sparse"]),
        "router_plus_sparse_over_fixed_wall": _stats(wall_ratios["router_plus_sparse"]),
    }
