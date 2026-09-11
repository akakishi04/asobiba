"""V5-B baseline cores for controlled architecture comparisons.

These baselines are intentionally small and expose the same working/context
interface as :class:`HighPrecisionFixedRoutingCore`.

- ``ActiveComputeDenseCore`` matches the V5-B active linear MACs per slot/step:
  the V5-B path executes one shared MLP plus one selected module MLP, while the
  dense baseline executes one route-specific MLP with twice the hidden width.
- ``ParameterMatchedSharedCore`` uses one recurrent/shared MLP plus a small route
  embedding.  Its hidden size is chosen to minimize the difference between its
  independent trainable parameter count and the V5-B reference core.

No compression, adaptive routing, FOLD-R memory, acquisition, or vision logic is
included here.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class _BaselineMLP(nn.Module):
    def __init__(self, width: int, hidden: int) -> None:
        super().__init__()
        if type(hidden) is not int or hidden <= 0:
            raise ValueError("hidden must be a positive integer")
        self.norm = nn.LayerNorm(width)
        self.up = nn.Linear(width, hidden)
        self.down = nn.Linear(hidden, width)
        self.activation = nn.GELU()

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.down(self.activation(self.up(self.norm(value))))


@dataclass(frozen=True)
class BaselineCoreStats:
    trainable_parameters: int
    active_linear_macs_per_slot_step: int
    hidden_size: int

    def __post_init__(self) -> None:
        for name in (
            "trainable_parameters",
            "active_linear_macs_per_slot_step",
            "hidden_size",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


def _validate_inputs(
    config: LearnedCoreConfig,
    working: torch.Tensor,
    context: torch.Tensor,
    route_index: int,
) -> None:
    if type(route_index) is not int or not 0 <= route_index < config.modules:
        raise ValueError("route_index is out of range")
    if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
        raise TypeError("working and context must be torch.Tensor")
    if working.ndim != 3:
        raise ValueError("working must have shape [batch, slots, width]")
    if tuple(working.shape[1:]) != (config.slots, config.width):
        raise ValueError("working shape does not match configured slots/width")
    if context.shape != working.shape:
        raise ValueError("context shape must match working")
    if not working.is_floating_point() or not context.is_floating_point():
        raise TypeError("working and context must use floating dtypes")
    if working.dtype != context.dtype:
        raise TypeError("working and context dtypes must match")
    if working.device != context.device:
        raise ValueError("working and context must be on the same device")
    if not torch.isfinite(working).all() or not torch.isfinite(context).all():
        raise ValueError("working and context must contain only finite values")


def _initial_state(
    module: nn.Module,
    config: LearnedCoreConfig,
    batch_size: int,
    *,
    device: torch.device | str | None = None,
    dtype: torch.dtype | None = None,
) -> torch.Tensor:
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    parameter = next(module.parameters())
    return torch.zeros(
        batch_size,
        config.slots,
        config.width,
        device=parameter.device if device is None else device,
        dtype=parameter.dtype if dtype is None else dtype,
    )


def trainable_parameter_count(module: nn.Module) -> int:
    if not isinstance(module, nn.Module):
        raise TypeError("module must be nn.Module")
    return sum(parameter.numel() for parameter in module.parameters() if parameter.requires_grad)


def reference_core_stats(config: LearnedCoreConfig) -> BaselineCoreStats:
    if not isinstance(config, LearnedCoreConfig):
        raise TypeError("config must be LearnedCoreConfig")
    core = HighPrecisionFixedRoutingCore(config)
    hidden = config.width * config.hidden_mult
    active_macs = 4 * config.width * hidden
    return BaselineCoreStats(
        trainable_parameters=trainable_parameter_count(core),
        active_linear_macs_per_slot_step=active_macs,
        hidden_size=hidden,
    )


class ActiveComputeDenseCore(nn.Module):
    """Route-specific dense baseline matched on active linear MACs.

    One V5-B active update evaluates two width->hidden->width MLPs.  This
    baseline evaluates one width->(2*hidden)->width MLP, giving the same Linear
    multiply-accumulate count per slot and internal step.
    """

    def __init__(self, config: LearnedCoreConfig) -> None:
        super().__init__()
        if not isinstance(config, LearnedCoreConfig):
            raise TypeError("config must be LearnedCoreConfig")
        self.config = config
        hidden = 2 * config.width * config.hidden_mult
        self.hidden_size = hidden
        self.route_set = nn.ModuleList(
            [_BaselineMLP(config.width, hidden) for _ in range(config.modules)]
        )
        self.gate_logits = nn.Parameter(torch.zeros(config.width))

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        return _initial_state(self, self.config, batch_size, device=device, dtype=dtype)

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        _validate_inputs(self.config, working, context, route_index)
        z = working + context
        delta = self.route_set[route_index](z)
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * delta
        if not torch.isfinite(updated).all():
            raise ValueError("dense baseline produced non-finite values")
        return updated

    def stats(self) -> BaselineCoreStats:
        active_macs = 2 * self.config.width * self.hidden_size
        return BaselineCoreStats(
            trainable_parameters=trainable_parameter_count(self),
            active_linear_macs_per_slot_step=active_macs,
            hidden_size=self.hidden_size,
        )


def _parameter_matched_hidden(config: LearnedCoreConfig) -> int:
    target = reference_core_stats(config).trainable_parameters

    # Search a small deterministic range.  Hidden sizes need not be multiples of
    # width; this is a parameter-count baseline rather than a kernel benchmark.
    best_hidden = 1
    best_gap: int | None = None
    for hidden in range(1, config.width * config.hidden_mult * (config.modules + 3) + 1):
        probe = ParameterMatchedSharedCore(config, hidden_size=hidden, _skip_match=True)
        gap = abs(trainable_parameter_count(probe) - target)
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_hidden = hidden
    return best_hidden


class ParameterMatchedSharedCore(nn.Module):
    """Single-weight recurrent baseline matched on independent parameters.

    Route identity is supplied only through a learned route embedding.  The
    transformation weights themselves are shared for every route and recurrence.
    """

    def __init__(
        self,
        config: LearnedCoreConfig,
        *,
        hidden_size: int | None = None,
        _skip_match: bool = False,
    ) -> None:
        super().__init__()
        if not isinstance(config, LearnedCoreConfig):
            raise TypeError("config must be LearnedCoreConfig")
        self.config = config
        if hidden_size is None:
            if _skip_match:
                raise ValueError("hidden_size is required when _skip_match is set")
            hidden_size = _parameter_matched_hidden(config)
        if type(hidden_size) is not int or hidden_size <= 0:
            raise ValueError("hidden_size must be a positive integer")
        self.hidden_size = hidden_size
        self.route_embedding = nn.Embedding(config.modules, config.width)
        self.shared = _BaselineMLP(config.width, hidden_size)
        self.gate_logits = nn.Parameter(torch.zeros(config.width))

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        return _initial_state(self, self.config, batch_size, device=device, dtype=dtype)

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        _validate_inputs(self.config, working, context, route_index)
        route_ids = torch.full(
            (working.shape[0], self.config.slots),
            route_index,
            dtype=torch.int64,
            device=working.device,
        )
        route_context = self.route_embedding(route_ids).to(dtype=working.dtype)
        z = working + context + route_context
        delta = self.shared(z)
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * delta
        if not torch.isfinite(updated).all():
            raise ValueError("shared baseline produced non-finite values")
        return updated

    def stats(self) -> BaselineCoreStats:
        active_macs = 2 * self.config.width * self.hidden_size
        return BaselineCoreStats(
            trainable_parameters=trainable_parameter_count(self),
            active_linear_macs_per_slot_step=active_macs,
            hidden_size=self.hidden_size,
        )
