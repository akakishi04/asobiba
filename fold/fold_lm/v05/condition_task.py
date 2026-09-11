"""V5-B condition hold/update task for the uncompressed learned core.

The task keeps one authoritative discrete value in working state.  Each event is
teacher-routed as HOLD or UPDATE.  HOLD carries a random distractor value that
must not change the state; UPDATE must replace the state with its candidate.
Trajectory supervision is used so failure to preserve an intermediate state is
not hidden by a lucky final answer.

This is a trainability reference, not an efficient sparse-routing runtime.  For
mixed-operation batches both teacher-routed branches are evaluated and selected
with ``torch.where``; V5-D owns efficient/adaptive routing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


HOLD = 0
UPDATE = 1


@dataclass(frozen=True)
class ConditionTaskConfig:
    value_vocab_size: int = 8
    operation_steps: int = 3
    width: int = 16
    modules: int = 2
    hidden_mult: int = 2
    hold_route: int = 0
    update_route: int = 1

    def __post_init__(self) -> None:
        for name in ("value_vocab_size", "operation_steps", "width", "modules", "hidden_mult"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.value_vocab_size < 2:
            raise ValueError("value_vocab_size must be at least 2")
        for name in ("hold_route", "update_route"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < self.modules:
                raise ValueError(f"{name} is out of range")
        if self.hold_route == self.update_route:
            raise ValueError("hold_route and update_route must be distinct")


@dataclass(frozen=True)
class ConditionExamples:
    initial_values: torch.Tensor
    operations: torch.Tensor
    candidates: torch.Tensor
    targets: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.initial_values.shape[0])


class ConditionHoldUpdateModel(nn.Module):
    """Maintain or replace one discrete value under teacher-routed events."""

    def __init__(self, config: ConditionTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, ConditionTaskConfig):
            raise TypeError("config must be ConditionTaskConfig")
        self.config = config
        core_config = LearnedCoreConfig(
            width=config.width,
            slots=1,
            modules=config.modules,
            hidden_mult=config.hidden_mult,
        )
        # State and event values deliberately use different encoders.  The core
        # receives H + C, so separating their learned representations avoids an
        # artificial symmetry between the current state and an update candidate.
        self.state_embedding = nn.Embedding(config.value_vocab_size, config.width)
        self.event_embedding = nn.Embedding(config.value_vocab_size, config.width)
        self.core = HighPrecisionFixedRoutingCore(core_config)
        self.readout_norm = nn.LayerNorm(config.width)
        self.decoder = nn.Linear(config.width, config.value_vocab_size)

    def _validate_inputs(
        self,
        initial_values: torch.Tensor,
        operations: torch.Tensor,
        candidates: torch.Tensor,
    ) -> None:
        for name, value in (
            ("initial_values", initial_values),
            ("operations", operations),
            ("candidates", candidates),
        ):
            if not isinstance(value, torch.Tensor):
                raise TypeError(f"{name} must be torch.Tensor")
            if value.dtype != torch.int64:
                raise TypeError(f"{name} must use torch.int64")
        if initial_values.ndim != 1 or initial_values.shape[0] <= 0:
            raise ValueError("initial_values must have shape [batch]")
        expected = (initial_values.shape[0], self.config.operation_steps)
        if tuple(operations.shape) != expected or tuple(candidates.shape) != expected:
            raise ValueError("operations and candidates must have shape [batch, operation_steps]")
        if initial_values.device != operations.device or initial_values.device != candidates.device:
            raise ValueError("all inputs must be on the same device")
        if torch.any(initial_values < 0) or torch.any(initial_values >= self.config.value_vocab_size):
            raise ValueError("initial value out of range")
        if torch.any(candidates < 0) or torch.any(candidates >= self.config.value_vocab_size):
            raise ValueError("candidate value out of range")
        if torch.any((operations != HOLD) & (operations != UPDATE)):
            raise ValueError("operations must be HOLD(0) or UPDATE(1)")

    def _decode(self, working: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.readout_norm(working[:, 0, :]))

    def forward(
        self,
        initial_values: torch.Tensor,
        operations: torch.Tensor,
        candidates: torch.Tensor,
    ) -> torch.Tensor:
        self._validate_inputs(initial_values, operations, candidates)

        working = self.state_embedding(initial_values).unsqueeze(1)
        logits = [self._decode(working)]
        for step in range(self.config.operation_steps):
            context = self.event_embedding(candidates[:, step]).unsqueeze(1)
            hold_state = self.core(working, context, route_index=self.config.hold_route)
            update_state = self.core(working, context, route_index=self.config.update_route)
            update_mask = operations[:, step].bool().view(-1, 1, 1)
            working = torch.where(update_mask, update_state, hold_state)
            logits.append(self._decode(working))
        return torch.stack(logits, dim=1)


def authoritative_targets(
    initial_values: torch.Tensor,
    operations: torch.Tensor,
    candidates: torch.Tensor,
) -> torch.Tensor:
    """Return the authoritative value before and after every operation."""
    if initial_values.dtype != torch.int64 or operations.dtype != torch.int64 or candidates.dtype != torch.int64:
        raise TypeError("condition targets require torch.int64 inputs")
    if initial_values.ndim != 1 or operations.ndim != 2 or candidates.shape != operations.shape:
        raise ValueError("invalid condition-target shapes")
    if operations.shape[0] != initial_values.shape[0]:
        raise ValueError("batch dimensions must match")
    if torch.any((operations != HOLD) & (operations != UPDATE)):
        raise ValueError("operations must be HOLD(0) or UPDATE(1)")

    current = initial_values.clone()
    trajectory = [current.clone()]
    for step in range(operations.shape[1]):
        current = torch.where(operations[:, step].bool(), candidates[:, step], current)
        trajectory.append(current.clone())
    return torch.stack(trajectory, dim=1)


def _sample_examples(
    *,
    count: int,
    config: ConditionTaskConfig,
    seed: int,
    excluded: set[tuple[int, ...]] | None = None,
) -> tuple[ConditionExamples, set[tuple[int, ...]]]:
    if type(count) is not int or count <= 0:
        raise ValueError("count must be a positive integer")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    excluded = set() if excluded is None else set(excluded)
    capacity = config.value_vocab_size * (2 * config.value_vocab_size) ** config.operation_steps
    if count + len(excluded) > capacity:
        raise ValueError("requested unique examples exceed task capacity")

    generator = torch.Generator(device="cpu").manual_seed(seed)
    initial_rows: list[int] = []
    operation_rows: list[tuple[int, ...]] = []
    candidate_rows: list[tuple[int, ...]] = []
    seen = set(excluded)
    while len(initial_rows) < count:
        initial = int(torch.randint(config.value_vocab_size, (), generator=generator).item())
        operations = tuple(
            int(value)
            for value in torch.randint(2, (config.operation_steps,), generator=generator).tolist()
        )
        candidates = tuple(
            int(value)
            for value in torch.randint(
                config.value_vocab_size,
                (config.operation_steps,),
                generator=generator,
            ).tolist()
        )
        signature = (initial, *operations, *candidates)
        if signature in seen:
            continue
        seen.add(signature)
        initial_rows.append(initial)
        operation_rows.append(operations)
        candidate_rows.append(candidates)

    initial_tensor = torch.tensor(initial_rows, dtype=torch.int64)
    operation_tensor = torch.tensor(operation_rows, dtype=torch.int64)
    candidate_tensor = torch.tensor(candidate_rows, dtype=torch.int64)
    examples = ConditionExamples(
        initial_values=initial_tensor,
        operations=operation_tensor,
        candidates=candidate_tensor,
        targets=authoritative_targets(initial_tensor, operation_tensor, candidate_tensor),
    )
    return examples, seen


def make_condition_splits(
    config: ConditionTaskConfig,
    *,
    train_examples: int = 256,
    validation_examples: int = 128,
    seed: int = 20260911,
) -> tuple[ConditionExamples, ConditionExamples]:
    """Create deterministic, unique, disjoint hold/update trajectories."""
    if not isinstance(config, ConditionTaskConfig):
        raise TypeError("config must be ConditionTaskConfig")
    train, seen = _sample_examples(count=train_examples, config=config, seed=seed)
    validation, _ = _sample_examples(
        count=validation_examples,
        config=config,
        seed=seed + 1,
        excluded=seen,
    )
    return train, validation


@torch.inference_mode()
def evaluate_condition(model: ConditionHoldUpdateModel, examples: ConditionExamples) -> dict[str, float]:
    if not isinstance(model, ConditionHoldUpdateModel):
        raise TypeError("model must be ConditionHoldUpdateModel")
    if not isinstance(examples, ConditionExamples):
        raise TypeError("examples must be ConditionExamples")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        initial = examples.initial_values.to(parameter.device)
        operations = examples.operations.to(parameter.device)
        candidates = examples.candidates.to(parameter.device)
        targets = examples.targets.to(parameter.device)
        logits = model(initial, operations, candidates)
        nll = float(F.cross_entropy(logits.flatten(0, 1), targets.flatten()).item())
        predicted = logits.argmax(dim=-1)
        trajectory_accuracy = float((predicted == targets).float().mean().item())
        trajectory_exact_accuracy = float((predicted == targets).all(dim=1).float().mean().item())
        final_accuracy = float((predicted[:, -1] == targets[:, -1]).float().mean().item())
    finally:
        model.train(training)
    return {
        "nll": nll,
        "perplexity": math.exp(min(nll, 80.0)),
        "trajectory_accuracy": trajectory_accuracy,
        "trajectory_exact_accuracy": trajectory_exact_accuracy,
        "final_accuracy": final_accuracy,
    }


def train_condition_task(
    *,
    config: ConditionTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 240,
    learning_rate: float = 0.01,
    batch_size: int = 32,
    train_examples: int = 256,
    validation_examples: int = 128,
    device: str | torch.device = "cpu",
) -> dict:
    """Train one deterministic held-out V5-B hold/update experiment."""
    config = config or ConditionTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train, validation = make_condition_splits(
        config,
        train_examples=train_examples,
        validation_examples=validation_examples,
        seed=seed + 100,
    )
    device = torch.device(device)
    model = ConditionHoldUpdateModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial_metrics = evaluate_condition(model, validation)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        candidates = train.candidates[indices].to(device)
        targets = train.targets[indices].to(device)

        optimizer.zero_grad(set_to_none=True)
        logits = model(initial_values, operations, candidates)
        loss = F.cross_entropy(logits.flatten(0, 1), targets.flatten())
        if not torch.isfinite(loss):
            raise ValueError("condition training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final_metrics = evaluate_condition(model, validation)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train_examples,
        "validation_examples": validation_examples,
        "initial": initial_metrics,
        "final": final_metrics,
    }
