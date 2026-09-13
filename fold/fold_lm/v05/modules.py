"""V5 learned state-update cores with explicit/fixed routing.

``HighPrecisionFixedRoutingCore`` remains the uncompressed V5-B default.
``SharedBasisFixedRoutingCore`` is an opt-in V5-C production candidate whose
routed Up/Down banks use a shared low-rank basis and GEMM-native execution.

The shared-basis core intentionally does not add controller routing, FOLD-R
memory, information acquisition, or vision.  It only changes the routed-weight
representation/execution path that was isolated by Gate C.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F


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


def _fit_shared_basis_role(weights: torch.Tensor, rank: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Fit ``W_module ~= W_base + A_module @ B_shared`` for one routed role.

    The helper is deterministic for a fixed PyTorch backend/input and is used
    only when converting an existing high-precision routed bank into the opt-in
    shared-basis parameterization.  Forward execution never materializes the
    effective routed weights.
    """

    if not isinstance(weights, torch.Tensor) or weights.ndim != 3:
        raise ValueError("weights must have shape [modules, output, input]")
    module_count, output_width, input_width = map(int, weights.shape)
    if module_count <= 0 or output_width <= 0 or input_width <= 0:
        raise ValueError("weights dimensions must be positive")
    if type(rank) is not int or rank <= 0:
        raise ValueError("rank must be a positive integer")
    max_rank = min(module_count * output_width, input_width)
    if rank > max_rank:
        raise ValueError(f"rank={rank} exceeds role max_rank={max_rank}")

    original_device = weights.device
    original_dtype = weights.dtype
    work = weights.detach().to(device="cpu", dtype=torch.float32)
    base = work.mean(dim=0)
    centered = work - base.unsqueeze(0)
    stacked = centered.reshape(module_count * output_width, input_width)
    _u, _s, vh = torch.linalg.svd(stacked, full_matrices=False)
    basis = vh[:rank].contiguous()
    coefficients = torch.matmul(stacked, basis.transpose(0, 1)).reshape(
        module_count, output_width, rank
    )
    return (
        base.to(device=original_device, dtype=original_dtype),
        basis.to(device=original_device, dtype=original_dtype),
        coefficients.to(device=original_device, dtype=original_dtype),
    )


class SharedBasisFixedRoutingCore(nn.Module):
    """Opt-in production Shared-Basis routed core.

    The routed Up/Down banks are initialized from an existing
    :class:`HighPrecisionFixedRoutingCore` as::

        W_module ~= W_base + A_module @ B_shared

    and are executed without materializing ``W_module``.  Each role stores one
    concatenated projection ``[W_base; B_shared]`` plus module coefficients.
    This is the GEMM-native form validated by Gate-C recurrence experiments.

    The ordinary ``HighPrecisionFixedRoutingCore`` remains the default.  Callers
    must explicitly construct this class to opt in.
    """

    def __init__(self, source: HighPrecisionFixedRoutingCore, rank: int) -> None:
        super().__init__()
        if not isinstance(source, HighPrecisionFixedRoutingCore):
            raise TypeError("source must be HighPrecisionFixedRoutingCore")
        if type(rank) is not int or rank <= 0:
            raise ValueError("rank must be a positive integer")

        self.config: LearnedCoreConfig = source.config
        self.rank = rank
        self.shared = copy.deepcopy(source.shared)
        self.norms = nn.ModuleList([copy.deepcopy(module.norm) for module in source.module_set])
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.up_biases = nn.Parameter(
            torch.stack([module.up.bias.detach().clone() for module in source.module_set], dim=0)
        )
        self.down_biases = nn.Parameter(
            torch.stack([module.down.bias.detach().clone() for module in source.module_set], dim=0)
        )

        up_weights = torch.stack(
            [module.up.weight.detach() for module in source.module_set], dim=0
        )
        down_weights = torch.stack(
            [module.down.weight.detach() for module in source.module_set], dim=0
        )
        up_base, up_basis, up_coeff = _fit_shared_basis_role(up_weights, rank)
        down_base, down_basis, down_coeff = _fit_shared_basis_role(down_weights, rank)

        self.up_projection = nn.Parameter(torch.cat((up_base, up_basis), dim=0).contiguous())
        self.down_projection = nn.Parameter(torch.cat((down_base, down_basis), dim=0).contiguous())
        self.up_coeff = nn.Parameter(up_coeff.contiguous())
        self.down_coeff = nn.Parameter(down_coeff.contiguous())

    @property
    def hidden_width(self) -> int:
        return self.config.width * self.config.hidden_mult

    def factor_parameters(self) -> tuple[nn.Parameter, ...]:
        """Return routed representation parameters for optimizer grouping."""

        return (
            self.up_projection,
            self.up_coeff,
            self.down_projection,
            self.down_coeff,
        )

    def materialized_role_weights(self, route_index: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Materialize effective Up/Down weights for diagnostics/checkpoint tooling.

        Production forward does not call this method.
        """

        self._validate_route_index(route_index)
        hidden = self.hidden_width
        up_base = self.up_projection[:hidden]
        up_basis = self.up_projection[hidden:]
        down_base = self.down_projection[: self.config.width]
        down_basis = self.down_projection[self.config.width :]
        up = up_base + self.up_coeff[route_index] @ up_basis
        down = down_base + self.down_coeff[route_index] @ down_basis
        return up, down

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=self.up_projection.device if device is None else device,
            dtype=self.up_projection.dtype if dtype is None else dtype,
        )

    def _validate_route_index(self, route_index: int) -> None:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index is out of range")

    def _validate_inputs(self, working: torch.Tensor, context: torch.Tensor) -> None:
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

    @staticmethod
    def _role_forward(
        value: torch.Tensor,
        projection: torch.Tensor,
        coeff: torch.Tensor,
        bias: torch.Tensor,
        *,
        output_width: int,
    ) -> torch.Tensor:
        original_shape = tuple(value.shape[:-1])
        flat = value.reshape(-1, value.shape[-1])
        projected = F.linear(flat, projection, None)
        base = projected[:, :output_width]
        latent = projected[:, output_width:]
        output = torch.addmm(base, latent, coeff.transpose(0, 1))
        output = output + bias
        return output.reshape(*original_shape, output_width)

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        self._validate_route_index(route_index)
        self._validate_inputs(working, context)

        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        hidden = self._role_forward(
            normalized,
            self.up_projection,
            self.up_coeff[route_index],
            self.up_biases[route_index],
            output_width=self.hidden_width,
        )
        hidden = F.gelu(hidden)
        routed_delta = self._role_forward(
            hidden,
            self.down_projection,
            self.down_coeff[route_index],
            self.down_biases[route_index],
            output_width=self.config.width,
        )
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("learned state update produced non-finite values")
        return updated
