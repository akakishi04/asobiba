"""V5-B held-out comparison task for the uncompressed learned core.

The task presents two discrete ordered values as two normalized scalar features.
No difference, ordering flag, or target-derived feature is supplied.  A fixed
teacher route processes the pair and predicts LESS / EQUAL / GREATER.

This stage isolates basic relational trainability.  It intentionally contains
no compression, adaptive routing, FOLD-R memory, acquisition, or language I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


LESS = 0
EQUAL = 1
GREATER = 2


@dataclass(frozen=True)
class ComparisonTaskConfig:
    value_vocab_size: int = 16
    width: int = 24
    modules: int = 2
    hidden_mult: int = 2
    route_index: int = 0
    internal_steps: int = 1

    def __post_init__(self) -> None:
        for name in ("value_vocab_size", "width", "modules", "hidden_mult", "internal_steps"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.value_vocab_size < 3:
            raise ValueError("value_vocab_size must be at least 3")
        if type(self.route_index) is not int or not 0 <= self.route_index < self.modules:
            raise ValueError("route_index is out of range")
        if self.width < 2:
            raise ValueError("width must be at least 2 for left/right scalar features")


@dataclass(frozen=True)
class ComparisonExamples:
    left: torch.Tensor
    right: torch.Tensor
    targets: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.left.shape[0])


class ComparisonModel(nn.Module):
    """Predict LESS / EQUAL / GREATER from two ordered discrete values."""

    def __init__(self, config: ComparisonTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, ComparisonTaskConfig):
            raise TypeError("config must be ComparisonTaskConfig")
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
        self.decoder = nn.Linear(config.width, 3)

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
            if torch.any(value < 0) or torch.any(value >= self.config.value_vocab_size):
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
        scale = float(self.config.value_vocab_size - 1)
        context[:, 0, 0] = left.to(dtype=parameter.dtype) / scale
        context[:, 0, 1] = right.to(dtype=parameter.dtype) / scale

        working = self.core.initial_working_state(
            left.shape[0], device=left.device, dtype=parameter.dtype
        )
        for _ in range(self.config.internal_steps):
            working = self.core(
                working,
                context,
                route_index=self.config.route_index,
            )
        return self.decoder(self.readout_norm(working[:, 0, :]))


def authoritative_comparison(left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
    if not isinstance(left, torch.Tensor) or not isinstance(right, torch.Tensor):
        raise TypeError("left and right must be torch.Tensor")
    if left.dtype != torch.int64 or right.dtype != torch.int64:
        raise TypeError("comparison inputs must use torch.int64")
    if left.ndim != 1 or right.shape != left.shape:
        raise ValueError("comparison inputs must have matching shape [batch]")
    return torch.where(
        left < right,
        torch.full_like(left, LESS),
        torch.where(left == right, torch.full_like(left, EQUAL), torch.full_like(left, GREATER)),
    )


def _permuted(rows: list[tuple[int, int, int]], generator: torch.Generator) -> list[tuple[int, int, int]]:
    order = torch.randperm(len(rows), generator=generator).tolist()
    return [rows[index] for index in order]


def make_comparison_splits(
    config: ComparisonTaskConfig,
    *,
    seed: int = 20260911,
    train_less: int = 60,
    train_equal: int = 12,
    train_greater: int = 60,
) -> tuple[ComparisonExamples, ComparisonExamples]:
    """Create deterministic class-stratified disjoint pair splits.

    Validation is the exact complement of the selected training pairs, so no
    ordered pair appears in both splits.
    """
    if not isinstance(config, ComparisonTaskConfig):
        raise TypeError("config must be ComparisonTaskConfig")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    for name, value in (
        ("train_less", train_less),
        ("train_equal", train_equal),
        ("train_greater", train_greater),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    size = config.value_vocab_size
    less = [(left, right, LESS) for left in range(size) for right in range(size) if left < right]
    equal = [(value, value, EQUAL) for value in range(size)]
    greater = [(left, right, GREATER) for left in range(size) for right in range(size) if left > right]
    capacities = {
        "train_less": len(less),
        "train_equal": len(equal),
        "train_greater": len(greater),
    }
    for name, requested in (
        ("train_less", train_less),
        ("train_equal", train_equal),
        ("train_greater", train_greater),
    ):
        if requested >= capacities[name]:
            raise ValueError(f"{name} must leave at least one held-out example")

    generator = torch.Generator(device="cpu").manual_seed(seed)
    less = _permuted(less, generator)
    equal = _permuted(equal, generator)
    greater = _permuted(greater, generator)

    train_rows = _permuted(
        less[:train_less] + equal[:train_equal] + greater[:train_greater], generator
    )
    validation_rows = _permuted(
        less[train_less:] + equal[train_equal:] + greater[train_greater:], generator
    )

    def build(rows: list[tuple[int, int, int]]) -> ComparisonExamples:
        left = torch.tensor([row[0] for row in rows], dtype=torch.int64)
        right = torch.tensor([row[1] for row in rows], dtype=torch.int64)
        targets = torch.tensor([row[2] for row in rows], dtype=torch.int64)
        return ComparisonExamples(left=left, right=right, targets=targets)

    return build(train_rows), build(validation_rows)


@torch.inference_mode()
def evaluate_comparison(model: ComparisonModel, examples: ComparisonExamples) -> dict[str, float]:
    if not isinstance(model, ComparisonModel):
        raise TypeError("model must be ComparisonModel")
    if not isinstance(examples, ComparisonExamples):
        raise TypeError("examples must be ComparisonExamples")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        left = examples.left.to(parameter.device)
        right = examples.right.to(parameter.device)
        targets = examples.targets.to(parameter.device)
        logits = model(left, right)
        nll = float(F.cross_entropy(logits, targets).item())
        predicted = logits.argmax(dim=-1)
        accuracy = float((predicted == targets).float().mean().item())
        class_accuracy: dict[int, float] = {}
        for label in (LESS, EQUAL, GREATER):
            mask = targets == label
            if not torch.any(mask):
                raise ValueError("evaluation split must contain every comparison class")
            class_accuracy[label] = float((predicted[mask] == targets[mask]).float().mean().item())
    finally:
        model.train(training)
    return {
        "nll": nll,
        "perplexity": math.exp(min(nll, 80.0)),
        "accuracy": accuracy,
        "less_accuracy": class_accuracy[LESS],
        "equal_accuracy": class_accuracy[EQUAL],
        "greater_accuracy": class_accuracy[GREATER],
    }


def train_comparison_task(
    *,
    config: ComparisonTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 300,
    learning_rate: float = 0.01,
    batch_size: int = 64,
    device: str | torch.device = "cpu",
) -> dict:
    """Train one deterministic held-out V5-B comparison experiment."""
    config = config or ComparisonTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train, validation = make_comparison_splits(config, seed=seed + 100)
    device = torch.device(device)
    model = ComparisonModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial = evaluate_comparison(model, validation)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        left = train.left[indices].to(device)
        right = train.right[indices].to(device)
        targets = train.targets[indices].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(left, right)
        loss = F.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise ValueError("comparison training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final = evaluate_comparison(model, validation)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train.size,
        "validation_examples": validation.size,
        "initial": initial,
        "final": final,
    }
