"""V5-C blockwise additive-codebook compression reference.

V5-A established a whole-matrix additive-codebook calculation.  V5-C needs a
representation that can model rectangular learned Linear weights while making
shared storage and module-specific storage explicit:

    W_module = W_base + block_codebook_decode(codes) + E

``BlockCodebookTemplate`` owns the shared base and shared codebooks.
``EncodedBlockWeight`` owns only block codes plus a sparse bounded correction.
The correction cannot silently become another dense matrix: both its non-zero
count and absolute magnitude are hard limits checked at construction time.

This module is a float64 numerical reference.  It does not yet define low-bit
serialization, code assignment/training, or an optimized GPU kernel.
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
class BlockCodebookTemplate:
    """Shared ``W_base`` and block dictionaries for one Linear weight shape.

    ``codebooks[q, k]`` is a candidate block of shape
    ``[block_rows, block_cols]`` from codebook ``q``.  Every encoded module using
    this template shares the same base and codebook storage.
    """

    base: np.ndarray
    codebooks: np.ndarray
    block_rows: int
    block_cols: int

    def __post_init__(self) -> None:
        if type(self.block_rows) is not int or self.block_rows <= 0:
            raise ValueError("block_rows must be a positive integer")
        if type(self.block_cols) is not int or self.block_cols <= 0:
            raise ValueError("block_cols must be a positive integer")

        base = _readonly_float64(self.base, name="base", ndim=2)
        if base.shape[0] % self.block_rows != 0:
            raise ValueError("base output dimension must be divisible by block_rows")
        if base.shape[1] % self.block_cols != 0:
            raise ValueError("base input dimension must be divisible by block_cols")

        codebooks = _readonly_float64(self.codebooks, name="codebooks", ndim=4)
        if codebooks.shape[2:] != (self.block_rows, self.block_cols):
            raise ValueError("codebook block shape does not match configured block size")

        object.__setattr__(self, "base", base)
        object.__setattr__(self, "codebooks", codebooks)

    @property
    def output_width(self) -> int:
        return int(self.base.shape[0])

    @property
    def input_width(self) -> int:
        return int(self.base.shape[1])

    @property
    def grid_rows(self) -> int:
        return self.output_width // self.block_rows

    @property
    def grid_cols(self) -> int:
        return self.input_width // self.block_cols

    @property
    def codebook_count(self) -> int:
        return int(self.codebooks.shape[0])

    @property
    def entries_per_codebook(self) -> int:
        return int(self.codebooks.shape[1])


@dataclass(frozen=True)
class EncodedBlockWeight:
    """Module-specific codes plus sparse bounded correction ``E``.

    ``codes[row_block, col_block, q]`` selects one entry from every shared
    codebook for that matrix block.  Sparse correction entries are exact matrix
    coordinates and values.  They are rejected if either configured bound is
    exceeded.
    """

    template: BlockCodebookTemplate
    codes: np.ndarray
    correction_indices: np.ndarray | None = None
    correction_values: np.ndarray | None = None
    max_correction_entries: int = 0
    max_abs_correction: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.template, BlockCodebookTemplate):
            raise TypeError("template must be BlockCodebookTemplate")
        if type(self.max_correction_entries) is not int or self.max_correction_entries < 0:
            raise ValueError("max_correction_entries must be a nonnegative integer")
        if (
            not isinstance(self.max_abs_correction, (int, float))
            or not np.isfinite(float(self.max_abs_correction))
            or float(self.max_abs_correction) < 0.0
        ):
            raise ValueError("max_abs_correction must be finite and nonnegative")

        codes = np.array(self.codes, copy=True)
        expected_codes = (
            self.template.grid_rows,
            self.template.grid_cols,
            self.template.codebook_count,
        )
        if codes.shape != expected_codes:
            raise ValueError("codes shape must match block grid and codebook count")
        if not np.issubdtype(codes.dtype, np.integer):
            raise TypeError("codes must use an integer dtype")
        codes = codes.astype(np.int64, copy=False)
        if np.any(codes < 0) or np.any(codes >= self.template.entries_per_codebook):
            raise ValueError("code index out of range")
        codes.setflags(write=False)

        if (self.correction_indices is None) != (self.correction_values is None):
            raise ValueError("correction_indices and correction_values must be supplied together")
        if self.correction_indices is None:
            indices = np.empty((0, 2), dtype=np.int64)
            values = np.empty((0,), dtype=np.float64)
        else:
            indices = np.array(self.correction_indices, copy=True)
            if indices.ndim != 2 or indices.shape[1:] != (2,):
                raise ValueError("correction_indices must have shape [nnz, 2]")
            if not np.issubdtype(indices.dtype, np.integer):
                raise TypeError("correction_indices must use an integer dtype")
            indices = indices.astype(np.int64, copy=False)

            values = np.array(self.correction_values, dtype=np.float64, copy=True)
            if values.ndim != 1 or values.shape[0] != indices.shape[0]:
                raise ValueError("correction_values must have shape [nnz]")
            if not np.isfinite(values).all():
                raise ValueError("correction_values must contain only finite values")

        if indices.shape[0] > self.max_correction_entries:
            raise ValueError("correction non-zero count exceeds max_correction_entries")
        if values.size and np.max(np.abs(values)) > float(self.max_abs_correction):
            raise ValueError("correction magnitude exceeds max_abs_correction")

        if indices.size:
            rows = indices[:, 0]
            cols = indices[:, 1]
            if np.any(rows < 0) or np.any(rows >= self.template.output_width):
                raise ValueError("correction row index out of range")
            if np.any(cols < 0) or np.any(cols >= self.template.input_width):
                raise ValueError("correction column index out of range")
            coordinates = {(int(row), int(col)) for row, col in indices}
            if len(coordinates) != indices.shape[0]:
                raise ValueError("correction coordinates must be unique")

        indices.setflags(write=False)
        values.setflags(write=False)
        object.__setattr__(self, "codes", codes)
        object.__setattr__(self, "correction_indices", indices)
        object.__setattr__(self, "correction_values", values)
        object.__setattr__(self, "max_abs_correction", float(self.max_abs_correction))

    @property
    def correction_nnz(self) -> int:
        return int(self.correction_values.shape[0])

    @property
    def correction_density(self) -> float:
        total = self.template.output_width * self.template.input_width
        return self.correction_nnz / total

    def materialize(self) -> np.ndarray:
        weight = np.array(self.template.base, dtype=np.float64, copy=True)
        br = self.template.block_rows
        bc = self.template.block_cols
        for row_block in range(self.template.grid_rows):
            row_slice = slice(row_block * br, (row_block + 1) * br)
            for col_block in range(self.template.grid_cols):
                col_slice = slice(col_block * bc, (col_block + 1) * bc)
                for q in range(self.template.codebook_count):
                    code = int(self.codes[row_block, col_block, q])
                    weight[row_slice, col_slice] += self.template.codebooks[q, code]

        for (row, col), value in zip(self.correction_indices, self.correction_values):
            weight[int(row), int(col)] += float(value)

        if not np.isfinite(weight).all():
            raise ValueError("decoded V5-C weight contains non-finite values")
        weight.setflags(write=False)
        return weight

    def direct_matmul_transposed(self, inputs: np.ndarray) -> np.ndarray:
        """Compute ``inputs @ materialize().T`` without materializing the weight."""
        value = np.array(inputs, dtype=np.float64, copy=True)
        if value.ndim != 2 or value.shape[1] != self.template.input_width:
            raise ValueError("inputs must be rank-2 with template input width")
        if not np.isfinite(value).all():
            raise ValueError("inputs must contain only finite values")

        output = value @ self.template.base.T
        br = self.template.block_rows
        bc = self.template.block_cols
        for row_block in range(self.template.grid_rows):
            row_slice = slice(row_block * br, (row_block + 1) * br)
            for col_block in range(self.template.grid_cols):
                col_slice = slice(col_block * bc, (col_block + 1) * bc)
                input_block = value[:, col_slice]
                for q in range(self.template.codebook_count):
                    code = int(self.codes[row_block, col_block, q])
                    block = self.template.codebooks[q, code]
                    output[:, row_slice] += input_block @ block.T

        for (row, col), correction in zip(
            self.correction_indices, self.correction_values
        ):
            output[:, int(row)] += value[:, int(col)] * float(correction)

        if not np.isfinite(output).all():
            raise ValueError("direct V5-C decoded matmul produced non-finite values")
        return output
