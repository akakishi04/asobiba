"""V5-A additive-codebook weight reference.

This module is deliberately small and float64-only.  It defines one whole-matrix
block so V5-A can establish the accounting and numerical contract before V5-C
introduces real block layouts, bounded corrections, or optimized kernels.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _readonly_float64(value: np.ndarray, *, name: str, ndim: int) -> np.ndarray:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.ndim != ndim:
        raise ValueError(f"{name} must be rank-{ndim}")
    if any(size <= 0 for size in array.shape):
        raise ValueError(f"{name} dimensions must be non-empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class AdditiveCodebookWeight:
    """Whole-matrix additive codebook reference.

    ``codebook[q, k]`` is one candidate matrix in codebook ``q`` and ``codes[q]``
    selects the matrix used by this encoded weight.  The decoded matrix is::

        W = base + sum_q codebook[q, codes[q]]

    V5-A intentionally uses one matrix as one block.  Later stages may introduce
    blockwise codes, scales, low-bit storage, and bounded corrections, but those
    are outside this reference contract.
    """

    base: np.ndarray
    codebook: np.ndarray
    codes: np.ndarray

    def __post_init__(self) -> None:
        base = _readonly_float64(self.base, name="base", ndim=2)
        if base.shape[0] != base.shape[1]:
            raise ValueError("base must be square")

        codebook = _readonly_float64(self.codebook, name="codebook", ndim=4)
        if codebook.shape[2:] != base.shape:
            raise ValueError("codebook matrix shape must match base")

        codes = np.array(self.codes, copy=True)
        if codes.ndim != 1 or codes.shape != (codebook.shape[0],):
            raise ValueError("codes must contain one index per codebook")
        if not np.issubdtype(codes.dtype, np.integer):
            raise TypeError("codes must use an integer dtype")
        codes = codes.astype(np.int64, copy=False)
        if np.any(codes < 0) or np.any(codes >= codebook.shape[1]):
            raise ValueError("code index out of range")
        codes.setflags(write=False)

        object.__setattr__(self, "base", base)
        object.__setattr__(self, "codebook", codebook)
        object.__setattr__(self, "codes", codes)

    @property
    def width(self) -> int:
        return int(self.base.shape[0])

    @property
    def codebook_count(self) -> int:
        return int(self.codebook.shape[0])

    @property
    def entries_per_codebook(self) -> int:
        return int(self.codebook.shape[1])

    def materialize(self) -> np.ndarray:
        weight = np.array(self.base, dtype=np.float64, copy=True)
        for q, code in enumerate(self.codes):
            weight += self.codebook[q, int(code)]
        if not np.isfinite(weight).all():
            raise ValueError("decoded weight contains non-finite values")
        weight.setflags(write=False)
        return weight

    def direct_matmul_transposed(self, inputs: np.ndarray) -> np.ndarray:
        """Compute ``inputs @ materialize().T`` without materializing the sum."""
        value = np.array(inputs, dtype=np.float64, copy=True)
        if value.ndim != 2 or value.shape[1] != self.width:
            raise ValueError("inputs must be rank-2 with encoded-weight width")
        if not np.isfinite(value).all():
            raise ValueError("inputs must contain only finite values")

        output = value @ self.base.T
        for q, code in enumerate(self.codes):
            output = output + value @ self.codebook[q, int(code)].T
        if not np.isfinite(output).all():
            raise ValueError("direct decoded matmul produced non-finite values")
        return output
