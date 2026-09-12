"""Hybrid cuBLAS + Triton diagnostic runtime for V5-C compressed Linear weights.

C29/C30 showed that the dominant remaining cost in the tiled compressed runtime
comes from reimplementing the shared-base GEMM in a custom Triton kernel, not from
the additive codebook decode itself.  This diagnostic runtime therefore delegates
``x @ W_base.T`` to PyTorch/cuBLAS and uses Triton only for the module-specific
additive codebook delta.

The first version is deliberately narrow:

- CUDA float32 inference only;
- sparse correction E must be absent;
- shared base is executed by ``torch.nn.functional.linear``;
- compact uint8 codes/shared codebooks stay resident;
- codebook deltas are decoded on the fly in a batch-tiled Triton kernel;
- no dense decoded module weight or dense module delta is materialized.

If this substantially closes the Dense gap, sparse E can be reintroduced as a
separate row-indexed path later.
"""
from __future__ import annotations

import torch
from torch.nn import functional as F

from .triton_runtime import (
    TritonCompressedLinearBank,
    triton_runtime_available,
    triton,
    tl,
)


if triton is not None:

    @triton.jit
    def _codebook_delta_tiled_accumulate_kernel(
        x_ptr,
        codebooks_ptr,
        codes_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        GRID_R: tl.constexpr,
        GRID_C: tl.constexpr,
        BR: tl.constexpr,
        BC: tl.constexpr,
        Q: tl.constexpr,
        ENTRIES: tl.constexpr,
        MODULE_INDEX: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
    ):
        pid_n = tl.program_id(0)
        pid_m = tl.program_id(1)

        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
        mask_n = offs_n < N
        mask_m = offs_m < M

        acc = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)

        for k_start in tl.static_range(0, K, BLOCK_K):
            offs_k = k_start + tl.arange(0, BLOCK_K)
            mask_k = offs_k < K
            matrix_mask = mask_m[:, None] & mask_k[None, :]

            x = tl.load(
                x_ptr + offs_n[:, None] * K + offs_k[None, :],
                mask=mask_n[:, None] & mask_k[None, :],
                other=0.0,
            )

            delta = tl.zeros((BLOCK_M, BLOCK_K), dtype=tl.float32)
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
                delta += tl.load(
                    codebooks_ptr + codebook_offset,
                    mask=matrix_mask,
                    other=0.0,
                )

            acc += tl.dot(x, tl.trans(delta), input_precision="ieee")

        out_offsets = offs_n[:, None] * M + offs_m[None, :]
        out_mask = mask_n[:, None] & mask_m[None, :]
        base_output = tl.load(out_ptr + out_offsets, mask=out_mask, other=0.0)
        tl.store(out_ptr + out_offsets, base_output + acc, mask=out_mask)


class HybridNoECompressedLinearBank(TritonCompressedLinearBank):
    """cuBLAS shared-base GEMM plus tiled on-the-fly codebook delta."""

    def __init__(self, initialization) -> None:
        super().__init__(initialization)
        for module_index in range(self.module_count):
            _indices, values = self._correction(module_index)
            if int(values.numel()) != 0:
                raise ValueError("hybrid no-E runtime requires zero correction entries")

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")
        if value.device.type != "cuda":
            raise RuntimeError("hybrid compressed Linear requires a CUDA tensor")
        if value.dtype != torch.float32:
            raise TypeError("hybrid compressed Linear currently requires float32")
        if self.base.device != value.device:
            raise ValueError("compressed bank buffers must be on the activation device")

        _indices, correction_values = self._correction(module_index)
        if int(correction_values.numel()) != 0:
            raise ValueError("hybrid no-E runtime received non-empty correction E")

        flat = value.reshape(-1, self.input_width).contiguous()
        # Delegate the dominant shared-base GEMM to cuBLAS.  The output is then
        # updated in place by the compact codebook-delta Triton kernel.
        output = F.linear(flat, self.base, None)

        block_n = 16
        block_m = 16
        block_k = 32
        grid = (
            triton.cdiv(int(flat.shape[0]), block_n),
            triton.cdiv(self.output_width, block_m),
        )
        _codebook_delta_tiled_accumulate_kernel[grid](
            flat,
            self.codebooks,
            self.codes,
            output,
            N=int(flat.shape[0]),
            M=self.output_width,
            K=self.input_width,
            GRID_R=self.grid_rows,
            GRID_C=self.grid_cols,
            BR=self.block_rows,
            BC=self.block_cols,
            Q=self.codebook_count,
            ENTRIES=self.entries_per_codebook,
            MODULE_INDEX=module_index,
            BLOCK_N=block_n,
            BLOCK_M=block_m,
            BLOCK_K=block_k,
            num_warps=4,
        )
        return output.reshape(*value.shape[:-1], self.output_width)
