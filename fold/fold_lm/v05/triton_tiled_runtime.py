"""Batch-tiled Triton diagnostic runtime for V5-C compressed Linear weights.

C27 showed that the existing fused kernel has two costs: substantial decode cost
for even one row, plus additional scaling loss when many rows repeat the same
base/codebook decode.  This experimental runtime changes only that execution
mapping.  One Triton program owns a tile of input rows and output channels, so a
decoded weight tile is reused by multiple rows before the program exits.

The first version is intentionally diagnostic and narrow:

- CUDA float32 inference only;
- sparse correction E must be absent;
- compact uint8 codes/shared base/shared codebooks stay resident;
- no dense decoded module weight is materialized;
- IEEE float32 dot precision is requested for parity diagnostics.

If this improves the large-row C27 case, the same mapping can later gain a
row-indexed correction path.  Until then it is not a production replacement for
``TritonCompressedLinearBank``.
"""
from __future__ import annotations

import torch

from .triton_runtime import (
    TritonCompressedLinearBank,
    triton_runtime_available,
    triton,
    tl,
)


if triton is not None:

    @triton.jit
    def _compressed_linear_tiled_no_e_kernel(
        x_ptr,
        base_ptr,
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

            x = tl.load(
                x_ptr + offs_n[:, None] * K + offs_k[None, :],
                mask=mask_n[:, None] & mask_k[None, :],
                other=0.0,
            )

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

            acc += tl.dot(x, tl.trans(weight), input_precision="ieee")

        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


class TiledNoECompressedLinearBank(TritonCompressedLinearBank):
    """No-E compressed bank that reuses decoded weight tiles across input rows."""

    def __init__(self, initialization) -> None:
        super().__init__(initialization)
        for module_index in range(self.module_count):
            _indices, values = self._correction(module_index)
            if int(values.numel()) != 0:
                raise ValueError("tiled no-E runtime requires zero correction entries")

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")
        if value.device.type != "cuda":
            raise RuntimeError("tiled compressed Linear requires a CUDA tensor")
        if value.dtype != torch.float32:
            raise TypeError("tiled compressed Linear currently requires float32")
        if self.base.device != value.device:
            raise ValueError("compressed bank buffers must be on the activation device")

        _indices, correction_values = self._correction(module_index)
        if int(correction_values.numel()) != 0:
            raise ValueError("tiled no-E runtime received non-empty correction E")

        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )

        block_n = 16
        block_m = 16
        block_k = 32
        grid = (
            triton.cdiv(int(flat.shape[0]), block_n),
            triton.cdiv(self.output_width, block_m),
        )
        _compressed_linear_tiled_no_e_kernel[grid](
            flat,
            self.base,
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
