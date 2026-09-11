"""V5-B exact-copy learning task for the uncompressed fixed-routing core.

This is the first trainability task for V5-B.  It deliberately avoids language,
compression, learned routing, FOLD-R memory, acquisition, and vision.  Discrete
symbols are embedded into working-slot context, passed through the new learned
core, and decoded back to the same symbol sequence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F

from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


@dataclass(frozen=True)
class CopyTaskConfig:
    vocab_size: int = 8
    sequence_length: int = 4
    width: int = 16
    modules: int = 2
    hidden_mult: int = 2
    route_index: int = 0
    internal_steps: int = 1

    def __post_init__(self) -> None:
        for name in (
            "vocab_size",
            "sequence_length",
            "width",
            "modules",
            "hidden_mult",
            "internal_steps",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.route_index) is not int or not 0 <= self.route_index < self.modules:
            raise ValueError("route_index is out of range")
        if self.vocab_size < 2:
            raise ValueError("vocab_size must be at least 2")


class ExactCopyModel(nn.Module):
    """Minimal V5-B model that must reconstruct every input symbol exactly."""

    def __init__(self, config: CopyTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, CopyTaskConfig):
            raise TypeError("config must be CopyTaskConfig")
        self.config = config
        core_config = LearnedCoreConfig(
            width=config.width,
            slots=config.sequence_length,
            modules=config.modules,
            hidden_mult=config.hidden_mult,
        )
        self.embedding = nn.Embedding(config.vocab_size, config.width)
        self.core = HighPrecisionFixedRoutingCore(core_config)
        self.readout_norm = nn.LayerNorm(config.width)
        self.decoder = nn.Linear(config.width, config.vocab_size)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        if not isinstance(tokens, torch.Tensor):
            raise TypeError("tokens must be torch.Tensor")
        if tokens.dtype != torch.int64:
            raise TypeError("tokens must use torch.int64")
        if tokens.ndim != 2 or tokens.shape[1] != self.config.sequence_length:
            raise ValueError("tokens must have shape [batch, sequence_length]")
        if tokens.shape[0] <= 0:
            raise ValueError("batch must be non-empty")
        if torch.any(tokens < 0) or torch.any(tokens >= self.config.vocab_size):
            raise ValueError("token id out of range")

        context = self.embedding(tokens)
        working = self.core.initial_working_state(
            tokens.shape[0], device=context.device, dtype=context.dtype
        )
        for _ in range(self.config.internal_steps):
            working = self.core(
                working,
                context,
                route_index=self.config.route_index,
            )
        return self.decoder(self.readout_norm(working))


def _unique_sequences(
    *,
    count: int,
    config: CopyTaskConfig,
    seed: int,
    excluded: set[tuple[int, ...]] | None = None,
) -> tuple[torch.Tensor, set[tuple[int, ...]]]:
    if type(count) is not int or count <= 0:
        raise ValueError("count must be a positive integer")
    capacity = config.vocab_size ** config.sequence_length
    excluded = set() if excluded is None else set(excluded)
    if count + len(excluded) > capacity:
        raise ValueError("requested unique sequences exceed task capacity")

    generator = torch.Generator(device="cpu").manual_seed(seed)
    rows: list[tuple[int, ...]] = []
    seen = set(excluded)
    while len(rows) < count:
        row = tuple(
            int(value)
            for value in torch.randint(
                config.vocab_size,
                (config.sequence_length,),
                generator=generator,
            ).tolist()
        )
        if row in seen:
            continue
        seen.add(row)
        rows.append(row)
    return torch.tensor(rows, dtype=torch.int64), seen


def make_copy_splits(
    config: CopyTaskConfig,
    *,
    train_examples: int = 256,
    validation_examples: int = 128,
    seed: int = 20260911,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Create deterministic disjoint train/validation exact-copy sequences."""
    if not isinstance(config, CopyTaskConfig):
        raise TypeError("config must be CopyTaskConfig")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    train, seen = _unique_sequences(count=train_examples, config=config, seed=seed)
    validation, _ = _unique_sequences(
        count=validation_examples,
        config=config,
        seed=seed + 1,
        excluded=seen,
    )
    return train, validation


@torch.inference_mode()
def evaluate_copy(model: ExactCopyModel, tokens: torch.Tensor) -> dict[str, float]:
    if not isinstance(model, ExactCopyModel):
        raise TypeError("model must be ExactCopyModel")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        batch = tokens.to(device=parameter.device)
        logits = model(batch)
        nll = float(F.cross_entropy(logits.flatten(0, 1), batch.flatten()).item())
        predicted = logits.argmax(dim=-1)
        token_accuracy = float((predicted == batch).float().mean().item())
        exact_accuracy = float((predicted == batch).all(dim=1).float().mean().item())
    finally:
        model.train(training)
    return {
        "nll": nll,
        "perplexity": math.exp(min(nll, 80.0)),
        "token_accuracy": token_accuracy,
        "exact_accuracy": exact_accuracy,
    }


def train_copy_task(
    *,
    config: CopyTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 200,
    learning_rate: float = 0.01,
    batch_size: int = 32,
    train_examples: int = 256,
    validation_examples: int = 128,
    device: str | torch.device = "cpu",
) -> dict:
    """Run one deterministic V5-B copy experiment and return measured metrics."""
    config = config or CopyTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train_tokens, validation_tokens = make_copy_splits(
        config,
        train_examples=train_examples,
        validation_examples=validation_examples,
        seed=seed + 100,
    )
    device = torch.device(device)
    model = ExactCopyModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial = evaluate_copy(model, validation_tokens)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train_examples, (batch_size,), generator=sampler)
        batch = train_tokens[indices].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(batch)
        loss = F.cross_entropy(logits.flatten(0, 1), batch.flatten())
        if not torch.isfinite(loss):
            raise ValueError("copy training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final = evaluate_copy(model, validation_tokens)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train_examples,
        "validation_examples": validation_examples,
        "initial": initial,
        "final": final,
    }
