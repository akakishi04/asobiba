"""V5-C compact-resident direct runtime reference.

C13 showed that the task-aware compressed representation is smaller on disk and
has a compact resident representation below dense float32, while the original
PyTorch reference runtime expands codes/correction coordinates to int64 and more
than doubles resident tensor bytes.

This module keeps the same direct blockwise computation but stores:

- shared base/codebooks as float32;
- block codes as uint8 (the current V5-C candidate uses <= 256 entries);
- correction coordinates as int32;
- correction values as float32.

Integer widening, when needed by Python indexing, is transient and is not stored
as a persistent buffer.  This stage changes resident representation only; it is
not the later vectorized/GPU performance implementation.
"""
from __future__ import annotations

import copy

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .compressed_runtime import CompressedModuleInitializations
from .compression_init import CompressionInitialization
from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


class CompactDirectCompressedLinearBank(nn.Module):
    """Direct compressed Linear bank with compact persistent integer buffers."""

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__()
        if not isinstance(initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        template = initialization.template
        if template.entries_per_codebook > 256:
            raise ValueError("compact C14 runtime currently requires <= 256 codebook entries")
        if template.output_width > 0x7FFFFFFF or template.input_width > 0x7FFFFFFF:
            raise ValueError("compact C14 runtime coordinates must fit int32")

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
        if np.any(codes < 0) or np.any(codes > 255):
            raise ValueError("codes do not fit uint8 compact storage")
        self.register_buffer("codes", torch.tensor(codes, dtype=torch.uint8))

        for module_index, encoded in enumerate(initialization.encoded_weights):
            indices = np.asarray(encoded.correction_indices, dtype=np.int64)
            if indices.size and (np.any(indices < 0) or np.max(indices) > 0x7FFFFFFF):
                raise ValueError("correction coordinates do not fit int32 compact storage")
            self.register_buffer(
                f"correction_indices_{module_index}",
                torch.tensor(indices, dtype=torch.int32),
            )
            self.register_buffer(
                f"correction_values_{module_index}",
                torch.tensor(encoded.correction_values, dtype=torch.float32),
            )

    @property
    def module_count(self) -> int:
        return int(self.codes.shape[0])

    @property
    def resident_tensor_bytes(self) -> int:
        return sum(int(buffer.numel() * buffer.element_size()) for buffer in self.buffers())

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

        output = output.reshape(*value.shape[:-1], self.output_width)
        if not torch.isfinite(output).all():
            raise ValueError("compact compressed direct matmul produced non-finite values")
        return output

    def materialized_weight(self, module_index: int) -> torch.Tensor:
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
        indices, values = self._correction(module_index)
        for entry in range(values.shape[0]):
            row = int(indices[entry, 0].item())
            col = int(indices[entry, 1].item())
            weight[row, col] = weight[row, col] + values[entry]
        return weight


class _CompactCompressedModuleMLP(nn.Module):
    def __init__(
        self,
        source_module: nn.Module,
        *,
        module_index: int,
        up_bank: CompactDirectCompressedLinearBank,
        down_bank: CompactDirectCompressedLinearBank,
    ) -> None:
        super().__init__()
        self.module_index = module_index
        self.up_bank = up_bank
        self.down_bank = down_bank
        self.norm = copy.deepcopy(source_module.norm)
        self.register_buffer("up_bias", source_module.up.bias.detach().clone())
        self.register_buffer("down_bias", source_module.down.bias.detach().clone())

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        hidden = self.up_bank(self.norm(value), module_index=self.module_index) + self.up_bias
        hidden = F.gelu(hidden)
        return self.down_bank(hidden, module_index=self.module_index) + self.down_bias


class CompactCompressedFixedRoutingCore(nn.Module):
    """V5-B core using compact-resident compressed module Linear banks."""

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
        self.up_bank = CompactDirectCompressedLinearBank(initializations.up)
        self.down_bank = CompactDirectCompressedLinearBank(initializations.down)
        self.module_set = nn.ModuleList(
            [
                _CompactCompressedModuleMLP(
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
            raise ValueError("compact compressed core produced non-finite values")
        return updated
