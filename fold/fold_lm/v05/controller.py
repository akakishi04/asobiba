"""V5-D adaptive-compute controller primitives.

The production-facing controller stays intentionally small.  C85 used the
minimal two-action space::

    ANSWER
    COMPUTE(update, 1)

Later V5-D experiments may register a larger finite action vocabulary through
``ActionRouterConfig.action_count`` while keeping the same observable inputs.
The caller must provide the observable operation token explicitly.  The router
never receives a target value or oracle action as an input.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


ANSWER_ACTION = 0
COMPUTE_ACTION = 1
ACTION_COUNT = 2


@dataclass(frozen=True)
class ActionRouterConfig:
    width: int
    operation_vocab_size: int = 2
    hidden_width: int | None = None
    action_count: int = ACTION_COUNT

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width <= 0:
            raise ValueError("width must be a positive integer")
        if type(self.operation_vocab_size) is not int or self.operation_vocab_size <= 0:
            raise ValueError("operation_vocab_size must be a positive integer")
        if self.hidden_width is not None and (
            type(self.hidden_width) is not int or self.hidden_width <= 0
        ):
            raise ValueError("hidden_width must be a positive integer when provided")
        if type(self.action_count) is not int or self.action_count <= 0:
            raise ValueError("action_count must be a positive integer")


class SupervisedActionRouter(nn.Module):
    """Minimal V5-D router over current state, event context, and operation token."""

    def __init__(self, config: ActionRouterConfig) -> None:
        super().__init__()
        if not isinstance(config, ActionRouterConfig):
            raise TypeError("config must be ActionRouterConfig")
        self.config = config
        hidden = config.width if config.hidden_width is None else config.hidden_width
        self.operation_embedding = nn.Embedding(config.operation_vocab_size, config.width)
        self.norm = nn.LayerNorm(config.width * 3)
        self.hidden = nn.Linear(config.width * 3, hidden)
        self.activation = nn.GELU()
        self.action_head = nn.Linear(hidden, config.action_count)

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        operation_ids: torch.Tensor,
    ) -> torch.Tensor:
        if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
            raise TypeError("working and context must be torch.Tensor")
        if not isinstance(operation_ids, torch.Tensor):
            raise TypeError("operation_ids must be torch.Tensor")
        if working.ndim != 3:
            raise ValueError("working must have shape [batch, slots, width]")
        if context.shape != working.shape:
            raise ValueError("context shape must match working")
        if working.shape[-1] != self.config.width:
            raise ValueError("working width does not match router config")
        if working.dtype != context.dtype or not working.is_floating_point():
            raise TypeError("working/context must use the same floating dtype")
        if working.device != context.device:
            raise ValueError("working and context must be on the same device")
        if operation_ids.dtype != torch.int64 or operation_ids.ndim != 1:
            raise TypeError("operation_ids must be int64 with shape [batch]")
        if operation_ids.shape[0] != working.shape[0]:
            raise ValueError("operation_ids batch must match working")
        if operation_ids.device != working.device:
            raise ValueError("operation_ids must be on the same device as working")
        if torch.any(operation_ids < 0) or torch.any(
            operation_ids >= self.config.operation_vocab_size
        ):
            raise ValueError("operation id out of range")
        if not torch.isfinite(working).all() or not torch.isfinite(context).all():
            raise ValueError("working/context must contain finite values")

        state_feature = working.mean(dim=1)
        context_feature = context.mean(dim=1)
        operation_feature = self.operation_embedding(operation_ids)
        feature = torch.cat((state_feature, context_feature, operation_feature), dim=-1)
        hidden = self.activation(self.hidden(self.norm(feature)))
        return self.action_head(hidden)
