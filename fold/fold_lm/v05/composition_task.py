"""V5-B multi-step synthetic composition task.

A bounded scalar state is initialized once and then transformed by a sequence of
teacher-routed ADD / SUB operations.  Each operation supplies only its operand;
the authoritative intermediate and final values are never fed back as input.
Trajectory supervision verifies that the uncompressed shared core can compose
multiple state transitions rather than merely solve a one-step target.

Feature 0 of the working state is the explicit scalar state channel.  Reading
that channel directly avoids adding a separate learned readout that could hide
whether recurrent state updates themselves are accurate.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import math

import torch
from torch import nn
from torch.nn import functional as F

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


ADD = 0
SUB = 1


@dataclass(frozen=True)
class CompositionTaskConfig:
    max_initial: int = 4
    max_operand: int = 2
    operation_steps: int = 3
    width: int = 32
    modules: int = 2
    hidden_mult: int = 2
    add_route: int = 0
    sub_route: int = 1

    def __post_init__(self) -> None:
        for name in (
            "max_initial",
            "max_operand",
            "operation_steps",
            "width",
            "modules",
            "hidden_mult",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.width < 3:
            raise ValueError("width must be at least 3")
        for name in ("add_route", "sub_route"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < self.modules:
                raise ValueError(f"{name} is out of range")
        if self.add_route == self.sub_route:
            raise ValueError("add_route and sub_route must be distinct")

    @property
    def state_scale(self) -> int:
        return self.max_initial + self.operation_steps * self.max_operand


@dataclass(frozen=True)
class CompositionExamples:
    initial_values: torch.Tensor
    operations: torch.Tensor
    operands: torch.Tensor
    targets: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.initial_values.shape[0])


class CompositionModel(nn.Module):
    """Compose a sequence of ADD / SUB state transitions."""

    def __init__(self, config: CompositionTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, CompositionTaskConfig):
            raise TypeError("config must be CompositionTaskConfig")
        self.config = config
        self.core = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(
                width=config.width,
                slots=1,
                modules=config.modules,
                hidden_mult=config.hidden_mult,
            )
        )

    def _validate(
        self,
        initial_values: torch.Tensor,
        operations: torch.Tensor,
        operands: torch.Tensor,
    ) -> None:
        for name, value in (
            ("initial_values", initial_values),
            ("operations", operations),
            ("operands", operands),
        ):
            if not isinstance(value, torch.Tensor):
                raise TypeError(f"{name} must be torch.Tensor")
            if value.dtype != torch.int64:
                raise TypeError(f"{name} must use torch.int64")
        if initial_values.ndim != 1 or initial_values.shape[0] <= 0:
            raise ValueError("initial_values must have shape [batch]")
        expected = (initial_values.shape[0], self.config.operation_steps)
        if tuple(operations.shape) != expected or tuple(operands.shape) != expected:
            raise ValueError("operations and operands must have shape [batch, operation_steps]")
        if initial_values.device != operations.device or initial_values.device != operands.device:
            raise ValueError("all inputs must be on the same device")
        if torch.any(initial_values < 0) or torch.any(initial_values > self.config.max_initial):
            raise ValueError("initial value out of range")
        if torch.any(operands < 0) or torch.any(operands > self.config.max_operand):
            raise ValueError("operand out of range")
        if torch.any((operations != ADD) & (operations != SUB)):
            raise ValueError("operations must be ADD(0) or SUB(1)")

    def _read_state(self, working: torch.Tensor) -> torch.Tensor:
        return working[:, 0, 0]

    def forward(
        self,
        initial_values: torch.Tensor,
        operations: torch.Tensor,
        operands: torch.Tensor,
    ) -> torch.Tensor:
        self._validate(initial_values, operations, operands)
        parameter = next(self.parameters())
        batch = initial_values.shape[0]
        working = self.core.initial_working_state(
            batch, device=initial_values.device, dtype=parameter.dtype
        )
        # Feature 0 is the authoritative learned state channel.  Operation
        # operands arrive on feature 1, so H + C does not alias state and input.
        working = working.clone()
        working[:, 0, 0] = initial_values.to(dtype=parameter.dtype) / float(self.config.state_scale)

        outputs = [self._read_state(working)]
        for step in range(self.config.operation_steps):
            context = torch.zeros_like(working)
            context[:, 0, 1] = operands[:, step].to(dtype=parameter.dtype) / float(self.config.state_scale)
            context[:, 0, 2] = 1.0
            add_state = self.core(working, context, route_index=self.config.add_route)
            sub_state = self.core(working, context, route_index=self.config.sub_route)
            sub_mask = operations[:, step].bool().view(-1, 1, 1)
            working = torch.where(sub_mask, sub_state, add_state)
            outputs.append(self._read_state(working))
        return torch.stack(outputs, dim=1)


def authoritative_trajectory(
    initial_values: torch.Tensor,
    operations: torch.Tensor,
    operands: torch.Tensor,
) -> torch.Tensor:
    if not isinstance(initial_values, torch.Tensor) or not isinstance(operations, torch.Tensor) or not isinstance(operands, torch.Tensor):
        raise TypeError("composition inputs must be torch.Tensor")
    if initial_values.dtype != torch.int64 or operations.dtype != torch.int64 or operands.dtype != torch.int64:
        raise TypeError("composition inputs must use torch.int64")
    if initial_values.ndim != 1 or operations.ndim != 2 or operands.shape != operations.shape:
        raise ValueError("invalid composition input shapes")
    if operations.shape[0] != initial_values.shape[0]:
        raise ValueError("batch dimensions must match")
    if torch.any((operations != ADD) & (operations != SUB)):
        raise ValueError("operations must be ADD(0) or SUB(1)")

    current = initial_values.clone()
    trajectory = [current.clone()]
    for step in range(operations.shape[1]):
        signed = torch.where(operations[:, step] == ADD, operands[:, step], -operands[:, step])
        current = current + signed
        trajectory.append(current.clone())
    return torch.stack(trajectory, dim=1)


def make_composition_splits(
    config: CompositionTaskConfig,
) -> tuple[CompositionExamples, CompositionExamples]:
    """Exhaustively enumerate trajectories and split them deterministically."""
    if not isinstance(config, CompositionTaskConfig):
        raise TypeError("config must be CompositionTaskConfig")

    train_rows: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    validation_rows: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    op_space = list(itertools.product((ADD, SUB), repeat=config.operation_steps))
    operand_space = list(
        itertools.product(range(config.max_operand + 1), repeat=config.operation_steps)
    )
    for initial in range(config.max_initial + 1):
        for operations in op_space:
            for operands in operand_space:
                checksum = initial + sum(
                    (index + 1) * (op + 2 * operand)
                    for index, (op, operand) in enumerate(zip(operations, operands))
                )
                row = (initial, operations, operands)
                if checksum % 5 == 0:
                    validation_rows.append(row)
                else:
                    train_rows.append(row)
    if not train_rows or not validation_rows:
        raise ValueError("composition split must contain train and validation rows")

    def build(rows: list[tuple[int, tuple[int, ...], tuple[int, ...]]]) -> CompositionExamples:
        initial = torch.tensor([row[0] for row in rows], dtype=torch.int64)
        operations = torch.tensor([row[1] for row in rows], dtype=torch.int64)
        operands = torch.tensor([row[2] for row in rows], dtype=torch.int64)
        targets = authoritative_trajectory(initial, operations, operands)
        return CompositionExamples(
            initial_values=initial,
            operations=operations,
            operands=operands,
            targets=targets,
        )

    return build(train_rows), build(validation_rows)


@torch.inference_mode()
def evaluate_composition(model: CompositionModel, examples: CompositionExamples) -> dict[str, float]:
    if not isinstance(model, CompositionModel):
        raise TypeError("model must be CompositionModel")
    if not isinstance(examples, CompositionExamples):
        raise TypeError("examples must be CompositionExamples")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        initial = examples.initial_values.to(parameter.device)
        operations = examples.operations.to(parameter.device)
        operands = examples.operands.to(parameter.device)
        targets = examples.targets.to(parameter.device)
        predicted_normalized = model(initial, operations, operands)
        target_normalized = targets.to(dtype=parameter.dtype) / float(model.config.state_scale)
        mse = float(F.mse_loss(predicted_normalized, target_normalized).item())
        predicted_values = predicted_normalized * float(model.config.state_scale)
        rounded = predicted_values.round().to(torch.int64)
        point_accuracy = float((rounded == targets).float().mean().item())
        trajectory_exact_accuracy = float((rounded == targets).all(dim=1).float().mean().item())
        final_accuracy = float((rounded[:, -1] == targets[:, -1]).float().mean().item())
        mae = float((predicted_values - targets.to(dtype=predicted_values.dtype)).abs().mean().item())
        max_abs_error = float(
            (predicted_values - targets.to(dtype=predicted_values.dtype)).abs().max().item()
        )
    finally:
        model.train(training)
    return {
        "mse": mse,
        "mae": mae,
        "max_abs_error": max_abs_error,
        "point_accuracy": point_accuracy,
        "trajectory_exact_accuracy": trajectory_exact_accuracy,
        "final_accuracy": final_accuracy,
    }


def train_composition_task(
    *,
    config: CompositionTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 300,
    learning_rate: float = 0.005,
    batch_size: int = 64,
    device: str | torch.device = "cpu",
) -> dict:
    """Train one deterministic held-out multi-step composition experiment."""
    config = config or CompositionTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train, validation = make_composition_splits(config)
    device = torch.device(device)
    model = CompositionModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial_metrics = evaluate_composition(model, validation)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        initial = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(config.state_scale)

        optimizer.zero_grad(set_to_none=True)
        predicted = model(initial, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise ValueError("composition training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final_metrics = evaluate_composition(model, validation)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train.size,
        "validation_examples": validation.size,
        "initial": initial_metrics,
        "final": final_metrics,
    }
