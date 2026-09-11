"""V5-C blockwise discrete-code reassignment with fixed continuous values.

After fixed-code continuous tuning, V5-C alternates the other side of the
representation: keep ``W_base``, codebook values, and sparse correction ``E``
fixed, and update only the discrete block codes.

Reassignment uses deterministic coordinate descent.  For every module/block and
every codebook, it selects the entry minimizing squared reconstruction error
while all other codebooks and the correction are held fixed.  Therefore each
local update is non-worsening for the dense-weight reconstruction objective.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .compression_init import CompressionInitialization, ReconstructionMetrics
from .compression_v5c import EncodedBlockWeight


@dataclass(frozen=True)
class CodeReassignmentResult:
    initialization: CompressionInitialization
    initial_mse: float
    final_mse: float
    changed_code_count: int
    sweeps: int

    def __post_init__(self) -> None:
        if not isinstance(self.initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        for name in ("initial_mse", "final_mse"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if type(self.changed_code_count) is not int or self.changed_code_count < 0:
            raise ValueError("changed_code_count must be a nonnegative integer")
        if type(self.sweeps) is not int or self.sweeps <= 0:
            raise ValueError("sweeps must be a positive integer")


def _validated_targets(
    weights: np.ndarray,
    initialization: CompressionInitialization,
) -> np.ndarray:
    if not isinstance(initialization, CompressionInitialization):
        raise TypeError("initialization must be CompressionInitialization")
    array = np.array(weights, dtype=np.float64, copy=True)
    expected = (
        len(initialization.encoded_weights),
        initialization.template.output_width,
        initialization.template.input_width,
    )
    if array.shape != expected:
        raise ValueError("weights shape does not match initialization")
    if not np.isfinite(array).all():
        raise ValueError("weights must contain only finite values")
    return array


def _dense_correction(encoded: EncodedBlockWeight) -> np.ndarray:
    correction = np.zeros(
        (encoded.template.output_width, encoded.template.input_width),
        dtype=np.float64,
    )
    for (row, col), value in zip(
        encoded.correction_indices, encoded.correction_values
    ):
        correction[int(row), int(col)] = float(value)
    return correction


def _global_mse(
    targets: np.ndarray,
    encoded_weights: tuple[EncodedBlockWeight, ...],
) -> float:
    reconstructed = np.stack([item.materialize() for item in encoded_weights], axis=0)
    error = targets - reconstructed
    return float(np.mean(error * error))


def _metrics(
    targets: np.ndarray,
    encoded_weights: tuple[EncodedBlockWeight, ...],
) -> tuple[ReconstructionMetrics, ...]:
    result: list[ReconstructionMetrics] = []
    for target, encoded in zip(targets, encoded_weights):
        error = target - encoded.materialize()
        result.append(
            ReconstructionMetrics(
                rmse=float(np.sqrt(np.mean(error * error))),
                max_abs_error=float(np.max(np.abs(error))),
                correction_nnz=encoded.correction_nnz,
                correction_density=encoded.correction_density,
            )
        )
    return tuple(result)


def reassign_block_codes(
    weights: np.ndarray,
    initialization: CompressionInitialization,
    *,
    sweeps: int = 1,
) -> CodeReassignmentResult:
    """Reassign only discrete codes by deterministic blockwise coordinate descent.

    Shared continuous values and every sparse correction coordinate/value remain
    unchanged.  Code storage shape is unchanged, so payload accounting remains
    exactly the same as the input initialization.
    """

    if type(sweeps) is not int or sweeps <= 0:
        raise ValueError("sweeps must be a positive integer")
    targets = _validated_targets(weights, initialization)
    template = initialization.template
    original_codes = np.stack(
        [encoded.codes for encoded in initialization.encoded_weights], axis=0
    )
    codes = np.array(original_codes, dtype=np.int64, copy=True)
    corrections = [_dense_correction(encoded) for encoded in initialization.encoded_weights]

    initial_mse = _global_mse(targets, initialization.encoded_weights)
    br = template.block_rows
    bc = template.block_cols

    completed_sweeps = 0
    for _ in range(sweeps):
        any_change = False
        for module_index in range(codes.shape[0]):
            correction = corrections[module_index]
            for row_block in range(template.grid_rows):
                row_slice = slice(row_block * br, (row_block + 1) * br)
                for col_block in range(template.grid_cols):
                    col_slice = slice(col_block * bc, (col_block + 1) * bc)
                    target_block = targets[module_index, row_slice, col_slice]
                    base_and_e = (
                        template.base[row_slice, col_slice]
                        + correction[row_slice, col_slice]
                    )
                    for q in range(template.codebook_count):
                        fixed = np.array(base_and_e, copy=True)
                        for other_q in range(template.codebook_count):
                            if other_q == q:
                                continue
                            fixed += template.codebooks[
                                other_q,
                                int(codes[module_index, row_block, col_block, other_q]),
                            ]

                        desired = target_block - fixed
                        candidates = template.codebooks[q]
                        errors = ((candidates - desired[None, :, :]) ** 2).sum(
                            axis=(1, 2)
                        )
                        best = int(np.argmin(errors))
                        if best != int(codes[module_index, row_block, col_block, q]):
                            codes[module_index, row_block, col_block, q] = best
                            any_change = True
        completed_sweeps += 1
        if not any_change:
            break

    encoded_weights: list[EncodedBlockWeight] = []
    for module_index, before in enumerate(initialization.encoded_weights):
        encoded_weights.append(
            EncodedBlockWeight(
                template=template,
                codes=codes[module_index],
                correction_indices=before.correction_indices,
                correction_values=before.correction_values,
                max_correction_entries=before.max_correction_entries,
                max_abs_correction=before.max_abs_correction,
            )
        )
    encoded_tuple = tuple(encoded_weights)
    final_mse = _global_mse(targets, encoded_tuple)
    if final_mse > initial_mse + 1e-12:
        raise RuntimeError("code reassignment unexpectedly increased reconstruction MSE")

    output = CompressionInitialization(
        template=template,
        encoded_weights=encoded_tuple,
        metrics=_metrics(targets, encoded_tuple),
        accounting=initialization.accounting,
    )
    return CodeReassignmentResult(
        initialization=output,
        initial_mse=initial_mse,
        final_mse=final_mse,
        changed_code_count=int(np.count_nonzero(codes != original_codes)),
        sweeps=completed_sweeps,
    )
