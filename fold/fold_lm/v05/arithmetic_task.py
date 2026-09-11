"""V5-B held-out addition task for the uncompressed learned core.

Two discrete operands are supplied only as separate normalized scalar features.
No sum, difference, carry flag, target-derived feature, compression, adaptive
routing, FOLD-R memory, acquisition, or language I/O is present.  The model
predicts a normalized scalar sum; evaluation rounds that scalar back to an
integer and measures exact held-out addition accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


@dataclass(frozen=True)
class ArithmeticTaskConfig:
    max_operand: int = 7
    width: int = 24
    modules: int = 2
    hidden_mult: int = 2
    route_index: int = 0
    internal_steps: int = 2

    def __post_init__(self) -> None:
        for name in ("max_operand", "width", "modules", "hidden_mult", "internal_steps"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.route_index) is not int or not 0 <= self.route_index < self.modules:
            raise ValueError("route_index is out of range")
        if self.width < 3:
            raise ValueError("width must be at least 3 for left/right/bias scalar features")


@dataclass(frozen=True)
class ArithmeticExamples:
    left: torch.Tensor
    right: torch.Tensor
    targets: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.left.shape[0])


class AdditionModel(nn.Module):
    """Predict the exact integer sum of two bounded nonnegative operands."""

    def __init__(self, config: ArithmeticTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, ArithmeticTaskConfig):
            raise TypeError("config must be ArithmeticTaskConfig")
        self.config = config
        self.core = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(
                width=config.width,
                slots=1,
                modules=config.modules,
                hidden_mult=config.hidden_mult,
            )
        )
        self.readout_norm = nn.LayerNorm(config.width)
        self.decoder = nn.Linear(config.width, 1)

    def _validate(self, left: torch.Tensor, right: torch.Tensor) -> None:
        for name, value in (("left", left), ("right", right)):
            if not isinstance(value, torch.Tensor):
                raise TypeError(f"{name} must be torch.Tensor")
            if value.dtype != torch.int64:
                raise TypeError(f"{name} must use torch.int64")
            if value.ndim != 1 or value.shape[0] <= 0:
                raise ValueError(f"{name} must have shape [batch]")
        if left.shape != right.shape:
            raise ValueError("left and right shapes must match")
        if left.device != right.device:
            raise ValueError("left and right must be on the same device")
        for name, value in (("left", left), ("right", right)):
            if torch.any(value < 0) or torch.any(value > self.config.max_operand):
                raise ValueError(f"{name} value out of range")

    def forward(self, left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
        self._validate(left, right)
        parameter = next(self.parameters())
        context = torch.zeros(
            left.shape[0],
            1,
            self.config.width,
            device=left.device,
            dtype=parameter.dtype,
        )
        scale = float(self.config.max_operand)
        context[:, 0, 0] = left.to(dtype=parameter.dtype) / scale
        context[:, 0, 1] = right.to(dtype=parameter.dtype) / scale
        context[:, 0, 2] = 1.0

        working = self.core.initial_working_state(
            left.shape[0], device=left.device, dtype=parameter.dtype
        )
        for _ in range(self.config.internal_steps):
            working = self.core(
                working,
                context,
                route_index=self.config.route_index,
            )
        return self.decoder(self.readout_norm(working[:, 0, :])).squeeze(-1)


def authoritative_sum(left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
    if not isinstance(left, torch.Tensor) or not isinstance(right, torch.Tensor):
        raise TypeError("left and right must be torch.Tensor")
    if left.dtype != torch.int64 or right.dtype != torch.int64:
        raise TypeError("addition inputs must use torch.int64")
    if left.ndim != 1 or right.shape != left.shape:
        raise ValueError("addition inputs must have matching shape [batch]")
    return left + right


def make_arithmetic_splits(
    config: ArithmeticTaskConfig,
) -> tuple[ArithmeticExamples, ArithmeticExamples]:
    """Create deterministic disjoint operand-pair splits.

    Validation uses the arithmetic lattice rule ``(left + 3*right) % 5 == 0``;
    training is its complement.  Every operand value appears on both sides of
    the split for the default task, while no ordered pair is shared.
    """
    if not isinstance(config, ArithmeticTaskConfig):
        raise TypeError("config must be ArithmeticTaskConfig")

    train_rows: list[tuple[int, int]] = []
    validation_rows: list[tuple[int, int]] = []
    for left in range(config.max_operand + 1):
        for right in range(config.max_operand + 1):
            row = (left, right)
            if (left + 3 * right) % 5 == 0:
                validation_rows.append(row)
            else:
                train_rows.append(row)
    if not train_rows or not validation_rows:
        raise ValueError("arithmetic split must contain train and validation rows")

    def build(rows: list[tuple[int, int]]) -> ArithmeticExamples:
        left = torch.tensor([row[0] for row in rows], dtype=torch.int64)
        right = torch.tensor([row[1] for row in rows], dtype=torch.int64)
        return ArithmeticExamples(left=left, right=right, targets=authoritative_sum(left, right))

    return build(train_rows), build(validation_rows)


def _normalized_targets(targets: torch.Tensor, config: ArithmeticTaskConfig) -> torch.Tensor:
    return targets.to(dtype=torch.float32) / float(2 * config.max_operand)


@torch.inference_mode()
def evaluate_addition(model: AdditionModel, examples: ArithmeticExamples) -> dict[str, float]:
    if not isinstance(model, AdditionModel):
        raise TypeError("model must be AdditionModel")
    if not isinstance(examples, ArithmeticExamples):
        raise TypeError("examples must be ArithmeticExamples")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        left = examples.left.to(parameter.device)
        right = examples.right.to(parameter.device)
        targets = examples.targets.to(parameter.device)
        normalized_targets = targets.to(dtype=parameter.dtype) / float(2 * model.config.max_operand)
        predicted_normalized = model(left, right)
        mse = float(F.mse_loss(predicted_normalized, normalized_targets).item())
        predicted_sum = predicted_normalized * float(2 * model.config.max_operand)
        rounded = predicted_sum.round().clamp(0, 2 * model.config.max_operand).to(torch.int64)
        exact_accuracy = float((rounded == targets).float().mean().item())
        mae = float((predicted_sum - targets.to(dtype=predicted_sum.dtype)).abs().mean().item())
        max_abs_error = float((predicted_sum - targets.to(dtype=predicted_sum.dtype)).abs().max().item())
    finally:
        model.train(training)
    return {
        "mse": mse,
        "mae": mae,
        "max_abs_error": max_abs_error,
        "exact_accuracy": exact_accuracy,
    }


def train_addition_task(
    *,
    config: ArithmeticTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 300,
    learning_rate: float = 0.005,
    batch_size: int = 32,
    device: str | torch.device = "cpu",
) -> dict:
    """Train one deterministic held-out V5-B exact-addition experiment."""
    config = config or ArithmeticTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train, validation = make_arithmetic_splits(config)
    device = torch.device(device)
    model = AdditionModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial = evaluate_addition(model, validation)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        left = train.left[indices].to(device)
        right = train.right[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(2 * config.max_operand)

        optimizer.zero_grad(set_to_none=True)
        predicted = model(left, right)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise ValueError("addition training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final = evaluate_addition(model, validation)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train.size,
        "validation_examples": validation.size,
        "initial": initial,
        "final": final,
    }
