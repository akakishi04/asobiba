"""V5-B high-precision learned core with fixed/teacher routing.

This module intentionally contains no compression, FOLD-R memory, controller,
information acquisition, or vision path.  V5-B first asks whether a shared core
plus a small set of independent high-precision modules can learn at all before
later stages introduce harder mechanisms.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class LearnedCoreConfig:
    width: int = 64
    slots: int = 8
    modules: int = 4
    hidden_mult: int = 2

    def __post_init__(self) -> None:
        for name in ("width", "slots", "modules", "hidden_mult"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


class _ResidualMLP(nn.Module):
    def __init__(self, width: int, hidden_mult: int) -> None:
        super().__init__()
        hidden = width * hidden_mult
        self.norm = nn.LayerNorm(width)
        self.up = nn.Linear(width, hidden)
        self.down = nn.Linear(hidden, width)
        self.activation = nn.GELU()

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.down(self.activation(self.up(self.norm(value))))


class HighPrecisionFixedRoutingCore(nn.Module):
    """Uncompressed V5-B learned state-update core.

    ``route_index`` is explicit rather than predicted.  This keeps routing out of
    the learning problem until V5-D and lets V5-B isolate whether the core itself
    is trainable.

    For working slots ``H`` and same-shape context ``C``::

        Z = H + C
        delta = F_shared(Z) + F_route(Z)
        H_next = H + sigmoid(gate) * delta
    """

    def __init__(self, config: LearnedCoreConfig) -> None:
        super().__init__()
        if not isinstance(config, LearnedCoreConfig):
            raise TypeError("config must be LearnedCoreConfig")
        self.config = config
        self.shared = _ResidualMLP(config.width, config.hidden_mult)
        self.module_set = nn.ModuleList(
            [_ResidualMLP(config.width, config.hidden_mult) for _ in range(config.modules)]
        )
        self.gate_logits = nn.Parameter(torch.zeros(config.width))

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        parameter = next(self.parameters())
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=parameter.device if device is None else device,
            dtype=parameter.dtype if dtype is None else dtype,
        )

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index is out of range")
        if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
            raise TypeError("working and context must be torch.Tensor")
        if working.ndim != 3:
            raise ValueError("working must have shape [batch, slots, width]")
        expected_tail = (self.config.slots, self.config.width)
        if tuple(working.shape[1:]) != expected_tail:
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

        z = working + context
        shared_delta = self.shared(z)
        routed_delta = self.module_set[route_index](z)
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("learned state update produced non-finite values")
        return updated
