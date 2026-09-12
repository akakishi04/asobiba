"""Fused Triton runtime for V5-C block-codebook Linear weights.

C19 showed that the compact PyTorch reference spends almost all of its routed
Linear time in codebook gather/decode/einsum/sparse-correction work rather than
in the shared base matmul.  This runtime fuses those pieces into one CUDA kernel
per Linear call while preserving the compact persistent representation.

The first implementation is deliberately narrow and auditable:

- CUDA inference only;
- float32 activations/weights;
- compact resident uint8 codes and int32 sparse coordinates;
- one program computes a small block of output channels for one flattened row;
- base + all additive codebooks + sparse correction are accumulated directly;
- no dense decoded module weight is materialized or stored.

It is a Gate-C performance experiment, not yet the final production kernel.
"""
from __future__ import annotations

import copy

import torch
from torch import nn

from .compact_runtime import CompactVectorizedLinearBank
from .compressed_runtime import CompressedModuleInitializations
from .compression_init import CompressionInitialization
from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig

try:
    import triton
    import triton.language as tl
except Exception:  # pragma: no cover - availability is environment dependent.
    triton = None
    tl = None


def triton_runtime_available() -> bool:
    return triton is not None and tl is not None


if triton is not None:

    @triton.jit
    def _compressed_linear_kernel(
        x_ptr,
        base_ptr,
        codebooks_ptr,
        codes_ptr,
        correction_indices_ptr,
        correction_values_ptr,
        out_ptr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
        ENTRIES: tl.constexpr,
        MODULE_INDEX: tl.constexpr,
        CORR_NNZ: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
        BLOCK_C: tl.constexpr,
    ):
        pid = tl.program_id(0)
        blocks_per_row = tl.cdiv(M, BLOCK_M)
        row_index = pid // blocks_per_row
        output_block = pid % blocks_per_row

        offs_m = output_block * BLOCK_M + tl.arange(0, BLOCK_M)
        offs_k = tl.arange(0, BLOCK_K)
        mask_m = offs_m < M
        mask_k = offs_k < K
        matrix_mask = mask_m[:, None] & mask_k[None, :]

        x = tl.load(
            x_ptr + row_index * K + offs_k,
            mask=mask_k,
            other=0.0,
        )
        base = tl.load(
            base_ptr + offs_m[:, None] * K + offs_k[None, :],
            mask=matrix_mask,
            other=0.0,
        )
        weight = base

        row_block = offs_m[:, None] // BR
        col_block = offs_k[None, :] // BC
        inner_row = offs_m[:, None] % BR
        inner_col = offs_k[None, :] % BC

        for q in tl.static_range(0, Q):
            code_offset = (
                (((MODULE_INDEX * GRID_R + row_block) * GRID_C + col_block) * Q)
                + q
            )
            code = tl.load(
                codes_ptr + code_offset,
                mask=matrix_mask,
                other=0,
            ).to(tl.int32)
            codebook_offset = (
                (((q * ENTRIES + code) * BR + inner_row) * BC) + inner_col
            )
            contribution = tl.load(
                codebooks_ptr + codebook_offset,
                mask=matrix_mask,
                other=0.0,
            )
            weight += contribution

        acc = tl.sum(weight * x[None, :], axis=1)

        if CORR_NNZ > 0:
            offs_c = tl.arange(0, BLOCK_C)
            corr_mask = offs_c < CORR_NNZ
            corr_rows = tl.load(
                correction_indices_ptr + offs_c * 2,
                mask=corr_mask,
                other=-1,
            ).to(tl.int32)
            corr_cols = tl.load(
                correction_indices_ptr + offs_c * 2 + 1,
                mask=corr_mask,
                other=0,
            ).to(tl.int32)
            corr_values = tl.load(
                correction_values_ptr + offs_c,
                mask=corr_mask,
                other=0.0,
            )
            corr_x = tl.load(
                x_ptr + row_index * K + corr_cols,
                mask=corr_mask,
                other=0.0,
            )
            matches = (
                mask_m[:, None]
                & corr_mask[None, :]
                & (offs_m[:, None] == corr_rows[None, :])
            )
            correction = tl.sum(
                tl.where(
                    matches,
                    corr_x[None, :] * corr_values[None, :],
                    0.0,
                ),
                axis=1,
            )
            acc += correction

        tl.store(
            out_ptr + row_index * M + offs_m,
            acc,
            mask=mask_m,
        )


class TritonCompressedLinearBank(CompactVectorizedLinearBank):
    """Compact-resident compressed Linear bank executed by one Triton kernel."""

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__(initialization)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if value.device.type != "cuda":
            raise RuntimeError("Triton compressed Linear requires a CUDA tensor")
        if value.dtype != torch.float32:
            raise TypeError("Triton compressed Linear currently requires float32")
        if self.base.device != value.device:
            raise ValueError("compressed bank buffers must be on the activation device")

        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )
        indices, correction_values = self._correction(module_index)
        correction_nnz = int(correction_values.numel())
        block_m = 16 if self.output_width >= 16 else triton.next_power_of_2(self.output_width)
        block_k = triton.next_power_of_2(self.input_width)
        block_c = triton.next_power_of_2(max(1, correction_nnz))
        grid = (
            int(flat.shape[0]) * triton.cdiv(self.output_width, block_m),
        )
        _compressed_linear_kernel[grid](
            flat,
            self.base,
            self.codebooks,
            self.codes,
            indices,
            correction_values,
            output,
            M=self.output_width,
            K=self.input_width,
            GRID_R=self.grid_rows,
            GRID_C=self.grid_cols,
            BR=self.block_rows,
            BC=self.block_cols,
            Q=self.codebook_count,
            ENTRIES=self.entries_per_codebook,
            MODULE_INDEX=module_index,
            CORR_NNZ=correction_nnz,
            BLOCK_M=block_m,
            BLOCK_K=block_k,
            BLOCK_C=block_c,
            num_warps=4,
        )
        return output.reshape(*value.shape[:-1], self.output_width)


class TritonCompressedFixedRoutingCore(nn.Module):
    """V5-B core using fused Triton banks for module-specific Linear weights."""

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
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")

        self.config: LearnedCoreConfig = source.config
        self.shared = copy.deepcopy(source.shared)
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.norms = nn.ModuleList(
            [copy.deepcopy(module.norm) for module in source.module_set]
        )
        self.register_buffer(
            "up_biases",
            torch.stack(
                [module.up.bias.detach().clone() for module in source.module_set],
                dim=0,
            ),
        )
        self.register_buffer(
            "down_biases",
            torch.stack(
                [module.down.bias.detach().clone() for module in source.module_set],
                dim=0,
            ),
        )
        self.up_bank = TritonCompressedLinearBank(initializations.up)
        self.down_bank = TritonCompressedLinearBank(initializations.down)

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

    def _validate(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        route_index: int,
    ) -> None:
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
        hidden = (
            self.up_bank(normalized, module_index=route_index)
            + self.up_biases[route_index]
        )
        hidden = torch.nn.functional.gelu(hidden)
        routed_delta = (
            self.down_bank(hidden, module_index=route_index)
            + self.down_biases[route_index]
        )
        gate = torch.sigmoid(self.gate_logits).to(
            dtype=working.dtype,
            device=working.device,
        )
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("Triton compressed core produced non-finite values")
        return updated
