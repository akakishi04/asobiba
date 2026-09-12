"""Configurable base-only Triton tiled runtime for V5-C kernel tuning diagnostics.

C29 showed that the dominant remaining cost is not additive codebook decode: the
base-only C28-style Triton matmul itself is already roughly an order of magnitude
slower than cuBLAS-backed ``F.linear``.  This module keeps the diagnostic narrow
and makes only the tiled matmul geometry / input precision configurable.

It is not a production runtime and it never materializes a module-specific dense
compressed weight.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from .triton_runtime import (
    TritonCompressedLinearBank,
    triton_runtime_available,
    triton,
    tl,
)


@dataclass(frozen=True)
class TiledBaseKernelConfig:
    block_n: int
    block_m: int
    block_k: int
    num_warps: int
    input_precision: str

    def __post_init__(self) -> None:
        for name in ("block_n", "block_m", "block_k", "num_warps"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.block_n & (self.block_n - 1):
            raise ValueError("block_n must be a power of two")
        if self.block_m & (self.block_m - 1):
            raise ValueError("block_m must be a power of two")
        if self.block_k & (self.block_k - 1):
            raise ValueError("block_k must be a power of two")
        if self.input_precision not in {"ieee", "tf32", "tf32x3"}:
            raise ValueError("input_precision must be ieee, tf32, or tf32x3")


if triton is not None:

    @triton.jit
    def _base_linear_tuned_kernel(
        x_ptr,
        base_ptr,
        out_ptr,
        N: tl.constexpr,
        M: tl.constexpr,
        K: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_M: tl.constexpr,
        BLOCK_K: tl.constexpr,
        INPUT_PRECISION: tl.constexpr,
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
            acc += tl.dot(x, tl.trans(weight), input_precision=INPUT_PRECISION)

        tl.store(
            out_ptr + offs_n[:, None] * M + offs_m[None, :],
            acc,
            mask=mask_n[:, None] & mask_m[None, :],
        )


class TunedTiledBaseOnlyLinearBank(TritonCompressedLinearBank):
    """Base-only diagnostic bank with explicit Triton tile/precision controls."""

    def __init__(self, initialization, config: TiledBaseKernelConfig) -> None:
        super().__init__(initialization)
        if not isinstance(config, TiledBaseKernelConfig):
            raise TypeError("config must be TiledBaseKernelConfig")
        self.kernel_config = config

    def forward(self, value: torch.Tensor, *, module_index: int) -> torch.Tensor:
        self._validate(value, module_index)
        if not triton_runtime_available():
            raise RuntimeError("Triton runtime is unavailable")
        if value.device.type != "cuda":
            raise RuntimeError("tuned tiled base-only Linear requires CUDA")
        if value.dtype != torch.float32:
            raise TypeError("tuned tiled base-only Linear requires float32")
        if self.base.device != value.device:
            raise ValueError("compressed bank buffers must be on the activation device")

        flat = value.reshape(-1, self.input_width).contiguous()
        output = torch.empty(
            (flat.shape[0], self.output_width),
            device=value.device,
            dtype=value.dtype,
        )
        cfg = self.kernel_config
        grid = (
            triton.cdiv(int(flat.shape[0]), cfg.block_n),
            triton.cdiv(self.output_width, cfg.block_m),
        )
        _base_linear_tuned_kernel[grid](
            flat,
            self.base,
            output,
            N=int(flat.shape[0]),
            M=self.output_width,
            K=self.input_width,
            BLOCK_N=cfg.block_n,
            BLOCK_M=cfg.block_m,
            BLOCK_K=cfg.block_k,
            INPUT_PRECISION=cfg.input_precision,
            num_warps=cfg.num_warps,
        )
        return output.reshape(*value.shape[:-1], self.output_width)
