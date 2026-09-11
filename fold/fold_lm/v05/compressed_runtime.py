"""V5-C runtime bridge from the high-precision V5-B core to compressed modules.

Only module-specific Linear *weights* are compressed at this stage.  The shared
core, module LayerNorm parameters, module biases, and gate remain high precision
so C5 isolates the numerical/runtime effect of block-codebook weights.

The compressed path performs blockwise matmul directly from shared base,
codebooks, module codes, and sparse bounded correction entries.  It never builds
one full dense module weight during forward.  A materialized reference path is
provided only for parity tests.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .compression_init import CompressionInitialization, initialize_from_dense_weights
from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class DirectCompressedLinearBank(nn.Module):
    """Direct blockwise Linear weight bank with one shared compressed template."""

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__()
        if not isinstance(initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        template = initialization.template
        self.output_width = template.output_width
        self.input_width = template.input_width
        self.block_rows = template.block_rows
        self.block_cols = template.block_cols
        self.grid_rows = template.grid_rows
        self.grid_cols = template.grid_cols
        self.codebook_count = template.codebook_count
        self.entries_per_codebook = template.entries_per_codebook
        self.accounting = initialization.accounting

        self.register_buffer("base", torch.tensor(template.base, dtype=torch.float32))
        self.register_buffer("codebooks", torch.tensor(template.codebooks, dtype=torch.float32))
        codes = np.stack([encoded.codes for encoded in initialization.encoded_weights], axis=0)
        self.register_buffer("codes", torch.tensor(codes, dtype=torch.int64))

        for module_index, encoded in enumerate(initialization.encoded_weights):
            self.register_buffer(
                f"correction_indices_{module_index}",
                torch.tensor(encoded.correction_indices, dtype=torch.int64),
            )
            self.register_buffer(
                f"correction_values_{module_index}",
                torch.tensor(encoded.correction_values, dtype=torch.float32),
            )

    @property
    def module_count(self) -> int:
        return int(self.codes.shape[0])

    def _correction(self, module_index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return (
            getattr(self, f"correction_indices_{module_index}"),
            getattr(self, f"correction_values_{module_index}"),
        )

    def _validate(self, value: torch.Tensor, module_index: int) -> None:
        if type(module_index) is not int or not 0 <= module_index < self.module_count:
            raise ValueError("module_index out of range")
        if not isinstance(value, torch.Tensor):
            raise TypeError("value must be torch.Tensor")
        if not value.is_floating_point():
            raise TypeError("value must use a floating dtype")
        if value.ndim < 2 or value.shape[-1] != self.input_width:
            raise ValueError("value must end with compressed input width")
        if not torch.isfinite(value).all():
            raise ValueError("value must contain only finite values")

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        """Compute ``value @ W_module.T`` without materializing ``W_module``."""
        self._validate(value, module_index)
        flat = value.reshape(-1, self.input_width)
        dtype = flat.dtype
        device = flat.device
        base = self.base.to(dtype=dtype, device=device)
        codebooks = self.codebooks.to(dtype=dtype, device=device)
        codes = self.codes[module_index].to(device=device)

        output = flat @ base.T
        br = self.block_rows
        bc = self.block_cols
        for row_block in range(self.grid_rows):
            row_slice = slice(row_block * br, (row_block + 1) * br)
            for col_block in range(self.grid_cols):
                col_slice = slice(col_block * bc, (col_block + 1) * bc)
                input_block = flat[:, col_slice]
                for q in range(self.codebook_count):
                    code = int(codes[row_block, col_block, q].item())
                    output[:, row_slice] = (
                        output[:, row_slice] + input_block @ codebooks[q, code].T
                    )

        indices, correction_values = self._correction(module_index)
        if correction_values.numel():
            indices = indices.to(device=device)
            correction_values = correction_values.to(dtype=dtype, device=device)
            for entry in range(correction_values.shape[0]):
                row = int(indices[entry, 0].item())
                col = int(indices[entry, 1].item())
                output[:, row] = output[:, row] + flat[:, col] * correction_values[entry]

        shape = (*value.shape[:-1], self.output_width)
        output = output.reshape(shape)
        if not torch.isfinite(output).all():
            raise ValueError("compressed direct matmul produced non-finite values")
        return output

    def materialized_weight(self, module_index: int) -> torch.Tensor:
        """Build one dense weight for validation only; forward does not call this."""
        if type(module_index) is not int or not 0 <= module_index < self.module_count:
            raise ValueError("module_index out of range")
        weight = self.base.clone()
        br = self.block_rows
        bc = self.block_cols
        for row_block in range(self.grid_rows):
            row_slice = slice(row_block * br, (row_block + 1) * br)
            for col_block in range(self.grid_cols):
                col_slice = slice(col_block * bc, (col_block + 1) * bc)
                for q in range(self.codebook_count):
                    code = int(self.codes[module_index, row_block, col_block, q].item())
                    weight[row_slice, col_slice] = (
                        weight[row_slice, col_slice] + self.codebooks[q, code]
                    )
        indices, correction_values = self._correction(module_index)
        for entry in range(correction_values.shape[0]):
            row = int(indices[entry, 0].item())
            col = int(indices[entry, 1].item())
            weight[row, col] = weight[row, col] + correction_values[entry]
        return weight


@dataclass(frozen=True)
class ModuleCompressionConfig:
    block_rows: int
    block_cols: int
    codebook_count: int = 2
    entries_per_codebook: int = 4
    max_correction_entries: int = 0
    max_abs_correction: float = 0.0

    def __post_init__(self) -> None:
        for name in ("block_rows", "block_cols", "codebook_count", "entries_per_codebook"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.max_correction_entries) is not int or self.max_correction_entries < 0:
            raise ValueError("max_correction_entries must be nonnegative")
        if not isinstance(self.max_abs_correction, (int, float)) or self.max_abs_correction < 0:
            raise ValueError("max_abs_correction must be nonnegative")


@dataclass(frozen=True)
class CompressedModuleInitializations:
    up: CompressionInitialization
    down: CompressionInitialization

    def __post_init__(self) -> None:
        if not isinstance(self.up, CompressionInitialization):
            raise TypeError("up must be CompressionInitialization")
        if not isinstance(self.down, CompressionInitialization):
            raise TypeError("down must be CompressionInitialization")
        if len(self.up.encoded_weights) != len(self.down.encoded_weights):
            raise ValueError("up/down module counts must match")


def initialize_module_weights_from_core(
    core: HighPrecisionFixedRoutingCore,
    *,
    up_config: ModuleCompressionConfig,
    down_config: ModuleCompressionConfig,
) -> CompressedModuleInitializations:
    if not isinstance(core, HighPrecisionFixedRoutingCore):
        raise TypeError("core must be HighPrecisionFixedRoutingCore")
    if not isinstance(up_config, ModuleCompressionConfig) or not isinstance(
        down_config, ModuleCompressionConfig
    ):
        raise TypeError("compression configs must be ModuleCompressionConfig")

    up_weights = np.stack(
        [module.up.weight.detach().cpu().numpy() for module in core.module_set], axis=0
    )
    down_weights = np.stack(
        [module.down.weight.detach().cpu().numpy() for module in core.module_set], axis=0
    )
    up = initialize_from_dense_weights(
        up_weights,
        block_rows=up_config.block_rows,
        block_cols=up_config.block_cols,
        codebook_count=up_config.codebook_count,
        entries_per_codebook=up_config.entries_per_codebook,
        max_correction_entries=up_config.max_correction_entries,
        max_abs_correction=up_config.max_abs_correction,
    )
    down = initialize_from_dense_weights(
        down_weights,
        block_rows=down_config.block_rows,
        block_cols=down_config.block_cols,
        codebook_count=down_config.codebook_count,
        entries_per_codebook=down_config.entries_per_codebook,
        max_correction_entries=down_config.max_correction_entries,
        max_abs_correction=down_config.max_abs_correction,
    )
    return CompressedModuleInitializations(up=up, down=down)


class _CompressedModuleMLP(nn.Module):
    def __init__(
        self,
        source_module: nn.Module,
        *,
        module_index: int,
        up_bank: DirectCompressedLinearBank,
        down_bank: DirectCompressedLinearBank,
    ) -> None:
        super().__init__()
        self.module_index = module_index
        self.up_bank = up_bank
        self.down_bank = down_bank
        self.norm = copy.deepcopy(source_module.norm)
        self.register_buffer("up_bias", source_module.up.bias.detach().clone())
        self.register_buffer("down_bias", source_module.down.bias.detach().clone())

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        normalized = self.norm(value)
        hidden = self.up_bank(normalized, module_index=self.module_index) + self.up_bias
        hidden = F.gelu(hidden)
        return self.down_bank(hidden, module_index=self.module_index) + self.down_bias

    def materialized_forward(self, value: torch.Tensor) -> torch.Tensor:
        normalized = self.norm(value)
        up_weight = self.up_bank.materialized_weight(self.module_index).to(
            dtype=value.dtype, device=value.device
        )
        down_weight = self.down_bank.materialized_weight(self.module_index).to(
            dtype=value.dtype, device=value.device
        )
        hidden = F.linear(normalized, up_weight, self.up_bias)
        hidden = F.gelu(hidden)
        return F.linear(hidden, down_weight, self.down_bias)


class CompressedFixedRoutingCore(nn.Module):
    """V5-B core with only module-specific MLP Linear weights compressed."""

    def __init__(
        self,
        source: HighPrecisionFixedRoutingCore,
        initializations: CompressedModuleInitializations,
    ) -> None:
        super().__init__()
        if not isinstance(source, HighPrecisionFixedRoutingCore):
            raise TypeError("source must be HighPrecisionFixedRoutingCore")
        if not isinstance(initializations, CompressedModuleInitializations):
            raise TypeError("initializations must be CompressedModuleInitializations")
        if len(initializations.up.encoded_weights) != source.config.modules:
            raise ValueError("compressed module count must match source core")
        self.config: LearnedCoreConfig = source.config
        self.shared = copy.deepcopy(source.shared)
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.up_bank = DirectCompressedLinearBank(initializations.up)
        self.down_bank = DirectCompressedLinearBank(initializations.down)
        self.module_set = nn.ModuleList(
            [
                _CompressedModuleMLP(
                    source.module_set[index],
                    module_index=index,
                    up_bank=self.up_bank,
                    down_bank=self.down_bank,
                )
                for index in range(source.config.modules)
            ]
        )

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

    def _validate(self, working: torch.Tensor, context: torch.Tensor, route_index: int) -> None:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index is out of range")
        if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
            raise TypeError("working and context must be torch.Tensor")
        if working.ndim != 3 or tuple(working.shape[1:]) != (
            self.config.slots,
            self.config.width,
        ):
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

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        self._validate(working, context, route_index)
        z = working + context
        shared_delta = self.shared(z)
        routed_delta = self.module_set[route_index](z)
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("compressed core produced non-finite values")
        return updated

    def materialized_reference(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        self._validate(working, context, route_index)
        z = working + context
        shared_delta = self.shared(z)
        routed_delta = self.module_set[route_index].materialized_forward(z)
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        return working + gate * (shared_delta + routed_delta)
