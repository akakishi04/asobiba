"""V5-A differentiable fixed-code reference.

This module exists only to validate continuous gradients while discrete codes are
held fixed.  It is not the V5-C code-assignment trainer.
"""
from __future__ import annotations

import torch


def materialize_fixed_codes(
    base: torch.Tensor,
    codebook: torch.Tensor,
    codes: torch.Tensor,
) -> torch.Tensor:
    """Decode ``base + sum_q codebook[q, codes[q]]`` with fixed integer codes."""
    if base.dtype != torch.float64 or codebook.dtype != torch.float64:
        raise TypeError("base and codebook must use torch.float64")
    if base.ndim != 2 or base.shape[0] != base.shape[1]:
        raise ValueError("base must be a square rank-2 tensor")
    if codebook.ndim != 4 or tuple(codebook.shape[2:]) != tuple(base.shape):
        raise ValueError("codebook matrix shape must match base")
    if codes.ndim != 1 or codes.shape[0] != codebook.shape[0]:
        raise ValueError("codes must contain one index per codebook")
    if codes.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64, torch.uint8):
        raise TypeError("codes must use an integer dtype")
    if not torch.isfinite(base).all() or not torch.isfinite(codebook).all():
        raise ValueError("base and codebook must contain only finite values")
    if torch.any(codes < 0) or torch.any(codes >= codebook.shape[1]):
        raise ValueError("code index out of range")

    decoded = base
    for q in range(codebook.shape[0]):
        decoded = decoded + codebook[q, codes[q].long()]
    return decoded


def fixed_code_loss(
    base: torch.Tensor,
    codebook: torch.Tensor,
    codes: torch.Tensor,
    inputs: torch.Tensor,
    target: torch.Tensor,
) -> torch.Tensor:
    """Small scalar loss used for autograd/finite-difference verification."""
    if inputs.dtype != torch.float64 or target.dtype != torch.float64:
        raise TypeError("inputs and target must use torch.float64")
    if inputs.ndim != 2 or inputs.shape[1] != base.shape[1]:
        raise ValueError("inputs must be rank-2 with decoded-weight width")
    if target.shape != (inputs.shape[0], base.shape[0]):
        raise ValueError("target shape must match decoded output")
    if not torch.isfinite(inputs).all() or not torch.isfinite(target).all():
        raise ValueError("inputs and target must contain only finite values")

    weight = materialize_fixed_codes(base, codebook, codes)
    output = inputs @ weight.T
    error = output - target
    return 0.5 * error.square().sum()
