"""Decoded-workspace diagnostic runtime for V5-C compressed Linear weights.

C29/C30 showed that the remaining runtime gap is dominated by the custom tiled
matmul rather than the additive codebook lookup itself.  This diagnostic runtime
therefore explores a different execution strategy:

1. decode the compact no-E representation into one reusable dense workspace;
2. execute the actual Linear with PyTorch/cuBLAS.

The workspace is intentionally one dense matrix, reused across module selections.
It is *not* a Gate-C compact-resident candidate and must be accounted as resident
scratch.  The experiment exists to bound how much runtime could be recovered by
letting cuBLAS own the GEMM while keeping compact persistent model storage.
"""
from __future__ import annotations

import torch
from torch.nn import functional as F

from .compression_init import CompressionInitialization
from .triton_runtime import (
    TritonCompressedLinearBank,
    triton_runtime_available,
    triton,
    tl,
)


if triton is not None:

    @triton.jit
    def _decode_no_e_weight_kernel(
        base_ptr,
        codebooks_ptr,
        codes_ptr,
        workspace_ptr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
        ENTRIES: tl.constexpr,
        MODULE_INDEX: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
    ):
        pid_m = tl.program_id(0)
        pid_k = tl.program_id(1)
        offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
        offs_k = pid_k * BLOCK_K + tl.arange(0, BLOCK_K)
        mask_m = offs_m < M
        mask_k = offs_k < K
        matrix_mask = mask_m[:, None] & mask_k[None, :]

        weight = tl.load(
            base_ptr + offs_m[:, None] * K + offs_k[None, :],
            mask=matrix_mask,
            other=0.0,
        )

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

        tl.store(
            workspace_ptr + offs_m[:, None] * K + offs_k[None, :],
            weight,
            mask=matrix_mask,
        )


class DecodedWorkspaceNoELinearBank(TritonCompressedLinearBank):
    """Decode one module into reusable dense scratch, then call ``F.linear``.

    Persistent model buffers remain compact, but ``workspace`` is a dense runtime
    allocation of one matrix shape.  It is registered with ``persistent=False``
    so model serialization is not inflated, while runtime accounting must still
    include ``workspace_bytes``.
    """

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__(initialization)
        for module_index in range(self.module_count):
            _indices, values = self._correction(module_index)
            if int(values.numel()) != 0:
                raise ValueError("decoded-workspace no-E runtime requires zero correction entries")
        self.register_buffer(
            "workspace",
            torch.empty((self.output_width, self.input_width), dtype=torch.float32),
            persistent=False,
        )

    @property
    def workspace_bytes(self) -> int:
        return int(self.workspace.numel() * self.workspace.element_size())

    def decode(self, *, module_index: int) -> torch.Tensor:
        if type(module_index) is not int or module_index < 0 or module_index >= self.module_count:
            raise ValueError("module_index out of range")
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")
        if self.base.device.type != "cuda":
            raise RuntimeError("decoded-workspace runtime requires CUDA buffers")
        if self.workspace.device != self.base.device:
            raise ValueError("workspace and compact buffers must share a device")

        block_m = 32
        block_k = 32
        grid = (
            triton.cdiv(self.output_width, block_m),
            triton.cdiv(self.input_width, block_k),
        )
        _decode_no_e_weight_kernel[grid](
            self.base,
            self.codebooks,
            self.codes,
            self.workspace,
            M=self.output_width,
            K=self.input_width,
            GRID_R=self.grid_rows,
            GRID_C=self.grid_cols,
            BR=self.block_rows,
            BC=self.block_cols,
            Q=self.codebook_count,
            ENTRIES=self.entries_per_codebook,
            MODULE_INDEX=module_index,
            BLOCK_M=block_m,
            BLOCK_K=block_k,
            num_warps=4,
        )
        return self.workspace

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if value.device.type != "cuda":
            raise RuntimeError("decoded-workspace Linear requires a CUDA tensor")
        if value.dtype != torch.float32:
            raise TypeError("decoded-workspace Linear currently requires float32")
        weight = self.decode(module_index=module_index)
        return F.linear(value, weight, None)
