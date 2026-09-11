"""V5-C initialization from high-precision dense module weights.

This module converts a set of same-role, same-shape V5-B dense weights into the
first V5-C block representation:

    W_module ~= W_base + sum_q codebook[q, code(module, block, q)] + E_module

The initialization is deliberately deterministic and numpy-only.  ``W_base`` is
the mean of the source module weights.  Residual blocks are greedily quantized
with deterministic k-means codebooks, then an optional sparse bounded correction
captures only the largest remaining scalar residuals.

The accounting reported here is an *estimated payload* contract, not a final
serialized file format.  V5-C serialization must later measure real bytes and
metadata separately before Gate C can pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


@dataclass(frozen=True)
class ReconstructionMetrics:
    rmse: float
    max_abs_error: float
    correction_nnz: int
    correction_density: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.rmse) or self.rmse < 0.0:
            raise ValueError("rmse must be finite and nonnegative")
        if not np.isfinite(self.max_abs_error) or self.max_abs_error < 0.0:
            raise ValueError("max_abs_error must be finite and nonnegative")
        if type(self.correction_nnz) is not int or self.correction_nnz < 0:
            raise ValueError("correction_nnz must be a nonnegative integer")
        if (
            not np.isfinite(self.correction_density)
            or self.correction_density < 0.0
            or self.correction_density > 1.0
        ):
            raise ValueError("correction_density must be finite and in [0, 1]")


@dataclass(frozen=True)
class InitializationAccounting:
    dense_float32_bytes: int
    shared_continuous_float32_bytes: int
    discrete_code_bits: int
    discrete_code_bytes: int
    correction_payload_bytes: int
    estimated_encoded_payload_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "dense_float32_bytes",
            "shared_continuous_float32_bytes",
            "discrete_code_bits",
            "discrete_code_bytes",
            "correction_payload_bytes",
            "estimated_encoded_payload_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.estimated_encoded_payload_bytes != (
            self.shared_continuous_float32_bytes
            + self.discrete_code_bytes
            + self.correction_payload_bytes
        ):
            raise ValueError("estimated payload accounting does not sum exactly")

    @property
    def estimated_payload_ratio(self) -> float:
        if self.dense_float32_bytes <= 0:
            raise ValueError("dense_float32_bytes must be positive for a ratio")
        return self.estimated_encoded_payload_bytes / self.dense_float32_bytes


@dataclass(frozen=True)
class CompressionInitialization:
    template: BlockCodebookTemplate
    encoded_weights: tuple[EncodedBlockWeight, ...]
    metrics: tuple[ReconstructionMetrics, ...]
    accounting: InitializationAccounting

    def __post_init__(self) -> None:
        if not isinstance(self.template, BlockCodebookTemplate):
            raise TypeError("template must be BlockCodebookTemplate")
        if not self.encoded_weights:
            raise ValueError("encoded_weights must be non-empty")
        if len(self.encoded_weights) != len(self.metrics):
            raise ValueError("metrics must match encoded_weights")
        for encoded in self.encoded_weights:
            if not isinstance(encoded, EncodedBlockWeight):
                raise TypeError("encoded_weights must contain EncodedBlockWeight values")
            if encoded.template is not self.template:
                raise ValueError("all encoded weights must share the initialization template")
        for metric in self.metrics:
            if not isinstance(metric, ReconstructionMetrics):
                raise TypeError("metrics must contain ReconstructionMetrics values")
        if not isinstance(self.accounting, InitializationAccounting):
            raise TypeError("accounting must be InitializationAccounting")


def _validate_dense_weights(weights: np.ndarray) -> np.ndarray:
    array = np.array(weights, dtype=np.float64, copy=True)
    if array.ndim != 3:
        raise ValueError("weights must have shape [modules, output_width, input_width]")
    if any(size <= 0 for size in array.shape):
        raise ValueError("weights dimensions must be non-empty")
    if not np.isfinite(array).all():
        raise ValueError("weights must contain only finite values")
    return array


def _assign(samples: np.ndarray, centers: np.ndarray) -> np.ndarray:
    distances = ((samples[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return np.argmin(distances, axis=1).astype(np.int64)


def _deterministic_kmeans(
    samples: np.ndarray,
    entries: int,
    *,
    iterations: int,
) -> tuple[np.ndarray, np.ndarray]:
    if samples.ndim != 2 or samples.shape[0] <= 0 or samples.shape[1] <= 0:
        raise ValueError("samples must be a non-empty rank-2 array")
    if type(entries) is not int or entries <= 0 or entries > samples.shape[0]:
        raise ValueError("entries must be in [1, sample_count]")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be a positive integer")

    # Farthest-point deterministic initialization.  Ties are resolved by the
    # first sample index through numpy argmax/argmin stability.
    norms = (samples * samples).sum(axis=1)
    chosen = [int(np.argmax(norms))]
    while len(chosen) < entries:
        current = samples[np.array(chosen, dtype=np.int64)]
        distances = ((samples[:, None, :] - current[None, :, :]) ** 2).sum(axis=2)
        nearest = distances.min(axis=1)
        nearest[np.array(chosen, dtype=np.int64)] = -1.0
        chosen.append(int(np.argmax(nearest)))

    centers = np.array(samples[np.array(chosen, dtype=np.int64)], copy=True)
    assignments = _assign(samples, centers)
    for _ in range(iterations):
        updated = np.array(centers, copy=True)
        for entry in range(entries):
            mask = assignments == entry
            if np.any(mask):
                updated[entry] = samples[mask].mean(axis=0)
        new_assignments = _assign(samples, updated)
        centers = updated
        if np.array_equal(new_assignments, assignments):
            assignments = new_assignments
            break
        assignments = new_assignments
    return centers, assignments


def _block_view(
    weights: np.ndarray,
    *,
    block_rows: int,
    block_cols: int,
) -> np.ndarray:
    modules, output_width, input_width = weights.shape
    grid_rows = output_width // block_rows
    grid_cols = input_width // block_cols
    return (
        weights.reshape(modules, grid_rows, block_rows, grid_cols, block_cols)
        .transpose(0, 1, 3, 2, 4)
        .copy()
    )


def _sparse_bounded_correction(
    residual: np.ndarray,
    *,
    max_entries: int,
    max_abs: float,
) -> tuple[np.ndarray, np.ndarray]:
    if type(max_entries) is not int or max_entries < 0:
        raise ValueError("max_entries must be a nonnegative integer")
    if not isinstance(max_abs, (int, float)) or not np.isfinite(float(max_abs)) or max_abs < 0:
        raise ValueError("max_abs must be finite and nonnegative")
    if max_entries == 0 or float(max_abs) == 0.0:
        return np.empty((0, 2), dtype=np.int64), np.empty((0,), dtype=np.float64)

    flat = residual.reshape(-1)
    indices = np.arange(flat.size, dtype=np.int64)
    order = np.lexsort((indices, -np.abs(flat)))
    selected = order[: min(max_entries, flat.size)]
    values = np.clip(flat[selected], -float(max_abs), float(max_abs))
    nonzero = values != 0.0
    selected = selected[nonzero]
    values = values[nonzero]
    rows, cols = np.unravel_index(selected, residual.shape)
    coordinates = np.stack([rows, cols], axis=1).astype(np.int64, copy=False)
    return coordinates, values.astype(np.float64, copy=False)


def _bits_per_code(entries: int) -> int:
    if entries <= 0:
        raise ValueError("entries must be positive")
    return 0 if entries == 1 else int(math.ceil(math.log2(entries)))


def initialize_from_dense_weights(
    weights: np.ndarray,
    *,
    block_rows: int,
    block_cols: int,
    codebook_count: int = 2,
    entries_per_codebook: int = 4,
    kmeans_iterations: int = 20,
    max_correction_entries: int = 0,
    max_abs_correction: float = 0.0,
) -> CompressionInitialization:
    """Deterministically initialize one shared V5-C representation.

    ``weights`` must contain all same-role module matrices, for example every
    V5-B module ``up.weight``.  The returned payload accounting assumes float32
    shared base/codebooks, bit-packed codes, and sparse corrections encoded as
    ``uint32 row + uint32 col + float32 value`` (12 bytes per entry).  Metadata
    and container overhead are intentionally excluded until a real serializer is
    introduced.
    """

    dense = _validate_dense_weights(weights)
    if type(block_rows) is not int or block_rows <= 0:
        raise ValueError("block_rows must be a positive integer")
    if type(block_cols) is not int or block_cols <= 0:
        raise ValueError("block_cols must be a positive integer")
    if dense.shape[1] % block_rows != 0:
        raise ValueError("output width must be divisible by block_rows")
    if dense.shape[2] % block_cols != 0:
        raise ValueError("input width must be divisible by block_cols")
    if type(codebook_count) is not int or codebook_count <= 0:
        raise ValueError("codebook_count must be a positive integer")
    if type(entries_per_codebook) is not int or entries_per_codebook <= 0:
        raise ValueError("entries_per_codebook must be a positive integer")
    if type(kmeans_iterations) is not int or kmeans_iterations <= 0:
        raise ValueError("kmeans_iterations must be a positive integer")
    if type(max_correction_entries) is not int or max_correction_entries < 0:
        raise ValueError("max_correction_entries must be a nonnegative integer")
    if (
        not isinstance(max_abs_correction, (int, float))
        or not np.isfinite(float(max_abs_correction))
        or float(max_abs_correction) < 0.0
    ):
        raise ValueError("max_abs_correction must be finite and nonnegative")

    module_count, output_width, input_width = dense.shape
    base = dense.mean(axis=0)
    residual_matrices = dense - base[None, :, :]
    residual_blocks = _block_view(
        residual_matrices,
        block_rows=block_rows,
        block_cols=block_cols,
    )
    grid_rows = residual_blocks.shape[1]
    grid_cols = residual_blocks.shape[2]
    block_dim = block_rows * block_cols
    samples = residual_blocks.reshape(-1, block_dim)
    if entries_per_codebook > samples.shape[0]:
        raise ValueError("entries_per_codebook exceeds available residual blocks")

    remaining = np.array(samples, copy=True)
    codebooks: list[np.ndarray] = []
    all_assignments: list[np.ndarray] = []
    for _ in range(codebook_count):
        centers, assignments = _deterministic_kmeans(
            remaining,
            entries_per_codebook,
            iterations=kmeans_iterations,
        )
        codebooks.append(centers.reshape(entries_per_codebook, block_rows, block_cols))
        all_assignments.append(assignments)
        remaining = remaining - centers[assignments]

    template = BlockCodebookTemplate(
        base=base,
        codebooks=np.stack(codebooks, axis=0),
        block_rows=block_rows,
        block_cols=block_cols,
    )

    codes_flat = np.stack(all_assignments, axis=1)
    codes = codes_flat.reshape(module_count, grid_rows, grid_cols, codebook_count)
    residual_after_codes = remaining.reshape(
        module_count, grid_rows, grid_cols, block_rows, block_cols
    ).transpose(0, 1, 3, 2, 4).reshape(module_count, output_width, input_width)

    encoded_weights: list[EncodedBlockWeight] = []
    metrics: list[ReconstructionMetrics] = []
    total_correction_nnz = 0
    for module_index in range(module_count):
        correction_indices, correction_values = _sparse_bounded_correction(
            residual_after_codes[module_index],
            max_entries=max_correction_entries,
            max_abs=float(max_abs_correction),
        )
        encoded = EncodedBlockWeight(
            template=template,
            codes=codes[module_index],
            correction_indices=correction_indices,
            correction_values=correction_values,
            max_correction_entries=max_correction_entries,
            max_abs_correction=float(max_abs_correction),
        )
        reconstructed = encoded.materialize()
        error = dense[module_index] - reconstructed
        rmse = float(np.sqrt(np.mean(error * error)))
        max_error = float(np.max(np.abs(error)))
        metrics.append(
            ReconstructionMetrics(
                rmse=rmse,
                max_abs_error=max_error,
                correction_nnz=encoded.correction_nnz,
                correction_density=encoded.correction_density,
            )
        )
        encoded_weights.append(encoded)
        total_correction_nnz += encoded.correction_nnz

    dense_bytes = int(dense.size * 4)
    shared_bytes = int((template.base.size + template.codebooks.size) * 4)
    code_bits = int(
        module_count
        * grid_rows
        * grid_cols
        * codebook_count
        * _bits_per_code(entries_per_codebook)
    )
    code_bytes = (code_bits + 7) // 8
    correction_bytes = total_correction_nnz * 12
    accounting = InitializationAccounting(
        dense_float32_bytes=dense_bytes,
        shared_continuous_float32_bytes=shared_bytes,
        discrete_code_bits=code_bits,
        discrete_code_bytes=code_bytes,
        correction_payload_bytes=correction_bytes,
        estimated_encoded_payload_bytes=shared_bytes + code_bytes + correction_bytes,
    )

    return CompressionInitialization(
        template=template,
        encoded_weights=tuple(encoded_weights),
        metrics=tuple(metrics),
        accounting=accounting,
    )
