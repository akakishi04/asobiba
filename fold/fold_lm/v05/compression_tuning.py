"""V5-C fixed-code continuous tuning for block-codebook compression.

After deterministic dense-to-codebook initialization, V5-C next adjusts only
continuous values while keeping every discrete choice fixed:

- shared ``W_base`` is trainable;
- shared codebook entries are trainable;
- block codes are immutable buffers;
- sparse correction coordinates are immutable buffers;
- sparse correction values are trainable but hard-bounded through ``tanh``.

This stage optimizes dense-weight reconstruction only.  Task-loss tuning and
code reassignment are later V5-C stages.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .compression_init import (
    CompressionInitialization,
    ReconstructionMetrics,
)
from .compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


class _FixedSparseCorrection(nn.Module):
    def __init__(
        self,
        indices: np.ndarray,
        values: np.ndarray,
        *,
        max_abs: float,
    ) -> None:
        super().__init__()
        if not isinstance(max_abs, (int, float)) or not math.isfinite(float(max_abs)) or max_abs < 0:
            raise ValueError("max_abs must be finite and nonnegative")
        index_tensor = torch.tensor(np.array(indices, dtype=np.int64, copy=True), dtype=torch.int64)
        value_tensor = torch.tensor(np.array(values, dtype=np.float32, copy=True), dtype=torch.float32)
        if index_tensor.ndim != 2 or index_tensor.shape[1:] != (2,):
            raise ValueError("indices must have shape [nnz, 2]")
        if value_tensor.ndim != 1 or value_tensor.shape[0] != index_tensor.shape[0]:
            raise ValueError("values must have shape [nnz]")
        if value_tensor.numel() and not torch.isfinite(value_tensor).all():
            raise ValueError("values must be finite")
        if value_tensor.numel() and float(value_tensor.abs().max()) > float(max_abs) + 1e-7:
            raise ValueError("initial correction exceeds max_abs")

        self.register_buffer("indices", index_tensor)
        self.max_abs = float(max_abs)
        if value_tensor.numel() == 0:
            raw = value_tensor
        elif self.max_abs == 0.0:
            if torch.any(value_tensor != 0):
                raise ValueError("non-zero corrections require positive max_abs")
            raw = torch.zeros_like(value_tensor)
        else:
            ratio = (value_tensor / self.max_abs).clamp(-1.0 + 1e-6, 1.0 - 1e-6)
            raw = torch.atanh(ratio)
        self.raw_values = nn.Parameter(raw)

    @property
    def nnz(self) -> int:
        return int(self.indices.shape[0])

    def values(self) -> torch.Tensor:
        if self.raw_values.numel() == 0 or self.max_abs == 0.0:
            return torch.zeros_like(self.raw_values)
        return torch.tanh(self.raw_values) * self.max_abs


class FixedCodeContinuousCompression(nn.Module):
    """Differentiable compressed weights with fixed codes/correction positions."""

    def __init__(self, initialization: CompressionInitialization) -> None:
        super().__init__()
        if not isinstance(initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        template = initialization.template
        self.block_rows = template.block_rows
        self.block_cols = template.block_cols
        self.output_width = template.output_width
        self.input_width = template.input_width
        self.grid_rows = template.grid_rows
        self.grid_cols = template.grid_cols
        self.codebook_count = template.codebook_count
        self.entries_per_codebook = template.entries_per_codebook
        self.accounting = initialization.accounting

        self.base = nn.Parameter(torch.tensor(template.base, dtype=torch.float32))
        self.codebooks = nn.Parameter(torch.tensor(template.codebooks, dtype=torch.float32))
        codes = np.stack([encoded.codes for encoded in initialization.encoded_weights], axis=0)
        self.register_buffer("codes", torch.tensor(codes, dtype=torch.int64))
        self.corrections = nn.ModuleList(
            [
                _FixedSparseCorrection(
                    encoded.correction_indices,
                    encoded.correction_values,
                    max_abs=encoded.max_abs_correction,
                )
                for encoded in initialization.encoded_weights
            ]
        )
        self.max_correction_entries = tuple(
            encoded.max_correction_entries for encoded in initialization.encoded_weights
        )
        self.max_abs_correction = tuple(
            encoded.max_abs_correction for encoded in initialization.encoded_weights
        )

    @property
    def module_count(self) -> int:
        return int(self.codes.shape[0])

    def materialized_weight(self, module_index: int) -> torch.Tensor:
        if type(module_index) is not int or not 0 <= module_index < self.module_count:
            raise ValueError("module_index out of range")
        rows: list[torch.Tensor] = []
        for row_block in range(self.grid_rows):
            cols: list[torch.Tensor] = []
            row_start = row_block * self.block_rows
            row_stop = row_start + self.block_rows
            for col_block in range(self.grid_cols):
                col_start = col_block * self.block_cols
                col_stop = col_start + self.block_cols
                block = self.base[row_start:row_stop, col_start:col_stop]
                for q in range(self.codebook_count):
                    code = self.codes[module_index, row_block, col_block, q]
                    block = block + self.codebooks[q, code]
                cols.append(block)
            rows.append(torch.cat(cols, dim=1))
        weight = torch.cat(rows, dim=0)

        correction = self.corrections[module_index]
        if correction.nnz:
            dense_e = torch.zeros_like(weight)
            values = correction.values().to(dtype=weight.dtype, device=weight.device)
            indices = correction.indices.to(device=weight.device)
            dense_e = dense_e.index_put(
                (indices[:, 0], indices[:, 1]), values, accumulate=True
            )
            weight = weight + dense_e
        return weight

    def materialized_weights(self) -> torch.Tensor:
        return torch.stack(
            [self.materialized_weight(index) for index in range(self.module_count)],
            dim=0,
        )

    def export(self) -> CompressionInitialization:
        template = BlockCodebookTemplate(
            base=self.base.detach().cpu().numpy().astype(np.float64),
            codebooks=self.codebooks.detach().cpu().numpy().astype(np.float64),
            block_rows=self.block_rows,
            block_cols=self.block_cols,
        )
        encoded_weights: list[EncodedBlockWeight] = []
        for module_index, correction in enumerate(self.corrections):
            encoded_weights.append(
                EncodedBlockWeight(
                    template=template,
                    codes=self.codes[module_index].detach().cpu().numpy(),
                    correction_indices=correction.indices.detach().cpu().numpy(),
                    correction_values=correction.values().detach().cpu().numpy().astype(np.float64),
                    max_correction_entries=self.max_correction_entries[module_index],
                    max_abs_correction=self.max_abs_correction[module_index],
                )
            )
        # Metrics are recomputed by ``fit_fixed_codes_to_dense`` when targets are
        # known.  For a raw export they describe only the representation itself.
        zero_metrics = tuple(
            ReconstructionMetrics(
                rmse=0.0,
                max_abs_error=0.0,
                correction_nnz=encoded.correction_nnz,
                correction_density=encoded.correction_density,
            )
            for encoded in encoded_weights
        )
        return CompressionInitialization(
            template=template,
            encoded_weights=tuple(encoded_weights),
            metrics=zero_metrics,
            accounting=self.accounting,
        )


@dataclass(frozen=True)
class ContinuousTuningResult:
    initialization: CompressionInitialization
    initial_mse: float
    final_mse: float
    steps: int

    def __post_init__(self) -> None:
        if not isinstance(self.initialization, CompressionInitialization):
            raise TypeError("initialization must be CompressionInitialization")
        for name in ("initial_mse", "final_mse"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if type(self.steps) is not int or self.steps <= 0:
            raise ValueError("steps must be a positive integer")


def _target_tensor(weights: np.ndarray, *, device: torch.device) -> torch.Tensor:
    array = np.array(weights, dtype=np.float32, copy=True)
    if array.ndim != 3 or any(size <= 0 for size in array.shape):
        raise ValueError("weights must have shape [modules, output_width, input_width]")
    if not np.isfinite(array).all():
        raise ValueError("weights must contain only finite values")
    return torch.tensor(array, dtype=torch.float32, device=device)


def _reconstruction_metrics(
    targets: np.ndarray,
    initialization: CompressionInitialization,
) -> tuple[ReconstructionMetrics, ...]:
    metrics: list[ReconstructionMetrics] = []
    for target, encoded in zip(targets, initialization.encoded_weights):
        error = np.asarray(target, dtype=np.float64) - encoded.materialize()
        metrics.append(
            ReconstructionMetrics(
                rmse=float(np.sqrt(np.mean(error * error))),
                max_abs_error=float(np.max(np.abs(error))),
                correction_nnz=encoded.correction_nnz,
                correction_density=encoded.correction_density,
            )
        )
    return tuple(metrics)


def fit_fixed_codes_to_dense(
    weights: np.ndarray,
    initialization: CompressionInitialization,
    *,
    steps: int = 100,
    learning_rate: float = 0.01,
    device: str | torch.device = "cpu",
) -> ContinuousTuningResult:
    """Tune continuous compressed values while keeping all discrete choices fixed."""
    if not isinstance(initialization, CompressionInitialization):
        raise TypeError("initialization must be CompressionInitialization")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if (
        not isinstance(learning_rate, (int, float))
        or not math.isfinite(float(learning_rate))
        or learning_rate <= 0
    ):
        raise ValueError("learning_rate must be positive and finite")

    device = torch.device(device)
    targets = _target_tensor(weights, device=device)
    expected = (
        len(initialization.encoded_weights),
        initialization.template.output_width,
        initialization.template.input_width,
    )
    if tuple(targets.shape) != expected:
        raise ValueError("weights shape does not match initialization")

    model = FixedCodeContinuousCompression(initialization).to(device)
    with torch.no_grad():
        initial_mse = float(F.mse_loss(model.materialized_weights(), targets).item())

    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        reconstructed = model.materialized_weights()
        loss = F.mse_loss(reconstructed, targets)
        if not torch.isfinite(loss):
            raise ValueError("continuous compression tuning produced non-finite loss")
        loss.backward()
        optimizer.step()

    with torch.no_grad():
        final_mse = float(F.mse_loss(model.materialized_weights(), targets).item())
    exported = model.export()
    metrics = _reconstruction_metrics(np.asarray(weights), exported)
    exported = CompressionInitialization(
        template=exported.template,
        encoded_weights=exported.encoded_weights,
        metrics=metrics,
        accounting=exported.accounting,
    )
    return ContinuousTuningResult(
        initialization=exported,
        initial_mse=initial_mse,
        final_mse=final_mse,
        steps=steps,
    )
