"""Diagnostic tiled Triton runtimes for decomposing V5-C execution cost.

C28 showed that reusing a decoded weight tile across multiple input rows materially
improves the large-row case, but the tiled compressed kernel remains far slower
than Dense.  This module provides a deliberately narrow base-only tiled kernel
with the same execution geometry as C28 so later benchmarks can separate:

- tiled matrix-multiply / launch / mapping cost; from
- additive codebook decode cost.

It is diagnostic only and is not a production compressed runtime.
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
    def _base_linear_tiled_kernel(
        x_ptr,
        base_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
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
            weight = tl.load(
                base_ptr + offs_m[:, None] * K + offs_k[None, :],
                mask=mask_m[:, None] & mask_k[None, :],
                other=0.0,
            )
            acc += tl.dot(x, tl.trans(weight), input_precision="ieee")

        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


class TiledBaseOnlyLinearBank(TritonCompressedLinearBank):
    """Execute only the shared base matrix using C28's tiled geometry."""

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")
        if value.device.type != "cuda":
            raise RuntimeError("tiled base-only Linear requires a CUDA tensor")
        if value.dtype != torch.float32:
            raise TypeError("tiled base-only Linear currently requires float32")
        if self.base.device != value.device:
            raise ValueError("compressed bank buffers must be on the activation device")

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
        _base_linear_tiled_kernel[grid](
            flat,
            self.base,
            output,
            N=int(flat.shape[0]),
            M=self.output_width,
            K=self.input_width,
            BLOCK_N=block_n,
            BLOCK_M=block_m,
            BLOCK_K=block_k,
            num_warps=4,
        )
        return output.reshape(*value.shape[:-1], self.output_width)
