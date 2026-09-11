"""V5-C compact, vectorized runtime for compressed module Linear weights.

The first direct runtime was intentionally literal: it stored codes/correction
coordinates as int64 and iterated Python-side over every block/codebook entry.
That path was useful for numerical validation but C12 showed that its resident
tensor storage is larger than the dense module weights.

This runtime is the next reference step toward a GPU kernel:

- codes stay resident as uint8 for the current <=256-entry codebooks;
- sparse correction coordinates stay resident as int32;
- base/codebooks/correction values stay float32;
- block contributions are gathered and evaluated with vectorized einsum;
- sparse corrections use one scatter-add per Linear call;
- no persistent dense decoded module weight is stored.

The implementation may create temporary gathered block tensors.  A later fused
GPU kernel can remove that transient decode overhead; C14 only establishes a
compact resident representation and a vectorized execution contract.
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


class CompactVectorizedLinearBank(nn.Module):
    """Compact-resident block-codebook Linear bank with vectorized execution."""

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__()
        if not isinstance(initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        template = initialization.template
        if template.entries_per_codebook > 256:
            raise ValueError("compact C14 runtime currently requires <=256 codebook entries")

        self.output_width = template.output_width
        self.input_width = template.input_width
        self.block_rows = template.block_rows
        self.block_cols = template.block_cols
        self.grid_rows = template.grid_rows
        self.grid_cols = template.grid_cols
        self.codebook_count = template.codebook_count
        self.entries_per_codebook = template.entries_per_codebook

        self.register_buffer("base", torch.tensor(template.base, dtype=torch.float32))
        self.register_buffer("codebooks", torch.tensor(template.codebooks, dtype=torch.float32))
        codes = np.stack([item.codes for item in initialization.encoded_weights], axis=0)
        self.register_buffer("codes", torch.tensor(codes, dtype=torch.uint8))

        for module_index, encoded in enumerate(initialization.encoded_weights):
            self.register_buffer(
                f"correction_indices_{module_index}",
                torch.tensor(encoded.correction_indices, dtype=torch.int32),
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
        return sum(
            int(buffer.numel() * buffer.element_size())
            for _name, buffer in self.named_buffers()
        )

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
        self._validate(value, module_index)
        flat = value.reshape(-1, self.input_width)
        dtype = flat.dtype
        device = flat.device
        base = self.base.to(dtype=dtype, device=device)
        codebooks = self.codebooks.to(dtype=dtype, device=device)
        module_codes = self.codes[module_index].to(device=device)

        output = flat @ base.T
        input_blocks = flat.reshape(-1, self.grid_cols, self.block_cols)
        # One small loop over additive codebooks remains.  All row/column blocks
        # within a codebook are gathered and applied in one tensor expression.
        for q in range(self.codebook_count):
            code_index = module_codes[..., q].to(dtype=torch.int64)
            blocks = codebooks[q][code_index]
            contribution = torch.einsum("nci,rcoi->nro", input_blocks, blocks)
            output = output + contribution.reshape(-1, self.output_width)

        indices, correction_values = self._correction(module_index)
        if correction_values.numel():
            indices = indices.to(device=device)
            values = correction_values.to(dtype=dtype, device=device)
            rows = indices[:, 0].to(dtype=torch.int64)
            cols = indices[:, 1].to(dtype=torch.int64)
            contribution = flat[:, cols] * values.unsqueeze(0)
            output = output.scatter_add(
                1,
                rows.unsqueeze(0).expand(flat.shape[0], -1),
                contribution,
            )

        output = output.reshape(*value.shape[:-1], self.output_width)
        if not torch.isfinite(output).all():
            raise ValueError("compact vectorized matmul produced non-finite values")
        return output


class CompactVectorizedFixedRoutingCore(nn.Module):
    """V5-B core using compact vectorized banks for module up/down weights."""

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
        self.norms = nn.ModuleList([copy.deepcopy(module.norm) for module in source.module_set])
        self.register_buffer(
            "up_biases",
            torch.stack([module.up.bias.detach().clone() for module in source.module_set], dim=0),
        )
        self.register_buffer(
            "down_biases",
            torch.stack([module.down.bias.detach().clone() for module in source.module_set], dim=0),
        )
        self.up_bank = CompactVectorizedLinearBank(initializations.up)
        self.down_bank = CompactVectorizedLinearBank(initializations.down)

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
        expected = (self.config.slots, self.config.width)
        if working.ndim != 3 or tuple(working.shape[1:]) != expected:
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
        normalized = self.norms[route_index](z)
        hidden = self.up_bank(normalized, module_index=route_index) + self.up_biases[route_index]
        hidden = F.gelu(hidden)
        routed_delta = (
            self.down_bank(hidden, module_index=route_index) + self.down_biases[route_index]
        )
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("compact vectorized core produced non-finite values")
        return updated
