"""V5-B short English/Japanese byte-level language smoke task.

This stage reuses the repository's existing UTF-8 byte vocabulary instead of
introducing a new tokenizer or variable-length runtime.  Prompts are padded to a
fixed slot count and teacher-routed as NEXT-BYTE or INSTRUCTION-RESPONSE.

The task is intentionally small.  It demonstrates that the uncompressed V5-B
core can train through raw English/Japanese UTF-8 byte inputs; it is not evidence
of general language understanding.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F

from ..data import BOS, EOS, PAD, TOKENIZER
from .modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig


LANG_EN = 0
LANG_JA = 1
TASK_NEXT = 0
TASK_INSTRUCTION = 1
BYTE_VOCAB_SIZE = int(TOKENIZER["vocab_size"])
OUTPUT_BYTE_CLASSES = 256


@dataclass(frozen=True)
class LanguageTaskConfig:
    symbol_count: int = 8
    max_tokens: int = 20
    width: int = 32
    modules: int = 2
    hidden_mult: int = 2
    next_route: int = 0
    instruction_route: int = 1
    internal_steps: int = 2

    def __post_init__(self) -> None:
        for name in (
            "symbol_count",
            "max_tokens",
            "width",
            "modules",
            "hidden_mult",
            "internal_steps",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not 2 <= self.symbol_count <= 10:
            raise ValueError("symbol_count must be in [2, 10] for ASCII digit symbols")
        for name in ("next_route", "instruction_route"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < self.modules:
                raise ValueError(f"{name} is out of range")
        if self.next_route == self.instruction_route:
            raise ValueError("next_route and instruction_route must be distinct")
        if self.max_tokens < 8:
            raise ValueError("max_tokens is too small for the fixed prompt family")


@dataclass(frozen=True)
class LanguageExamples:
    tokens: torch.Tensor
    targets: torch.Tensor
    languages: torch.Tensor
    tasks: torch.Tensor
    prompts: tuple[str, ...]

    @property
    def size(self) -> int:
        return int(self.tokens.shape[0])


def encode_fixed_prompt(text: str, *, max_tokens: int) -> torch.Tensor:
    if not isinstance(text, str) or not text:
        raise ValueError("text must be a non-empty string")
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    raw = text.encode("utf-8")
    ids = [BOS, *raw, EOS]
    if len(ids) > max_tokens:
        raise ValueError("UTF-8 prompt does not fit fixed token slots")
    ids.extend([PAD] * (max_tokens - len(ids)))
    return torch.tensor(ids, dtype=torch.int64)


def _prompt_target(language: int, task: int, symbol: int, config: LanguageTaskConfig) -> tuple[str, int]:
    if language not in (LANG_EN, LANG_JA):
        raise ValueError("unknown language")
    if task not in (TASK_NEXT, TASK_INSTRUCTION):
        raise ValueError("unknown task")
    if not 0 <= symbol < config.symbol_count:
        raise ValueError("symbol out of range")

    if task == TASK_NEXT:
        if symbol >= config.symbol_count - 1:
            raise ValueError("NEXT examples require a symbol with a following byte")
        sequence = "".join(str(value) for value in range(symbol + 1))
        prompt = f"sequence:{sequence}" if language == LANG_EN else f"列:{sequence}"
        target = ord(str(symbol + 1))
    else:
        digit = str(symbol)
        prompt = f"reply:{digit}" if language == LANG_EN else f"答え:{digit}"
        target = ord(digit)
    return prompt, target


def make_language_splits(
    config: LanguageTaskConfig,
) -> tuple[LanguageExamples, LanguageExamples]:
    """Create deterministic disjoint bilingual prompt-combination splits."""
    if not isinstance(config, LanguageTaskConfig):
        raise TypeError("config must be LanguageTaskConfig")

    train_rows: list[tuple[int, int, int, str, int]] = []
    validation_rows: list[tuple[int, int, int, str, int]] = []
    for language in (LANG_EN, LANG_JA):
        for task in (TASK_NEXT, TASK_INSTRUCTION):
            symbols = range(config.symbol_count - 1) if task == TASK_NEXT else range(config.symbol_count)
            for symbol in symbols:
                prompt, target = _prompt_target(language, task, symbol, config)
                row = (language, task, symbol, prompt, target)
                # At most one language/task realization for a given symbol is
                # held out, so the symbolic mapping remains learnable while the
                # exact UTF-8 prompt combination is unseen.
                if (symbol + language + 2 * task) % 3 == 0:
                    validation_rows.append(row)
                else:
                    train_rows.append(row)

    def build(rows: list[tuple[int, int, int, str, int]]) -> LanguageExamples:
        if not rows:
            raise ValueError("language split must be non-empty")
        prompts = tuple(row[3] for row in rows)
        tokens = torch.stack(
            [encode_fixed_prompt(prompt, max_tokens=config.max_tokens) for prompt in prompts]
        )
        return LanguageExamples(
            tokens=tokens,
            targets=torch.tensor([row[4] for row in rows], dtype=torch.int64),
            languages=torch.tensor([row[0] for row in rows], dtype=torch.int64),
            tasks=torch.tensor([row[1] for row in rows], dtype=torch.int64),
            prompts=prompts,
        )

    train = build(train_rows)
    validation = build(validation_rows)
    for examples in (train, validation):
        if set(examples.languages.tolist()) != {LANG_EN, LANG_JA}:
            raise ValueError("each language split must contain English and Japanese")
        if set(examples.tasks.tolist()) != {TASK_NEXT, TASK_INSTRUCTION}:
            raise ValueError("each language split must contain both task kinds")
    return train, validation


class ShortByteLanguageModel(nn.Module):
    """Fixed-slot byte model around the uncompressed V5-B learned core."""

    def __init__(self, config: LanguageTaskConfig) -> None:
        super().__init__()
        if not isinstance(config, LanguageTaskConfig):
            raise TypeError("config must be LanguageTaskConfig")
        self.config = config
        self.byte_embedding = nn.Embedding(BYTE_VOCAB_SIZE, config.width, padding_idx=PAD)
        self.position_embedding = nn.Embedding(config.max_tokens, config.width)
        self.core = HighPrecisionFixedRoutingCore(
            LearnedCoreConfig(
                width=config.width,
                slots=config.max_tokens,
                modules=config.modules,
                hidden_mult=config.hidden_mult,
            )
        )
        self.readout_norm = nn.LayerNorm(config.width)
        self.decoder = nn.Linear(config.width, OUTPUT_BYTE_CLASSES)

    def forward(self, tokens: torch.Tensor, tasks: torch.Tensor) -> torch.Tensor:
        if not isinstance(tokens, torch.Tensor) or not isinstance(tasks, torch.Tensor):
            raise TypeError("tokens and tasks must be torch.Tensor")
        if tokens.dtype != torch.int64 or tasks.dtype != torch.int64:
            raise TypeError("tokens and tasks must use torch.int64")
        if tokens.ndim != 2 or tuple(tokens.shape[1:]) != (self.config.max_tokens,):
            raise ValueError("tokens must have shape [batch, max_tokens]")
        if tokens.shape[0] <= 0 or tasks.shape != (tokens.shape[0],):
            raise ValueError("tasks must have shape [batch] for a non-empty batch")
        if tokens.device != tasks.device:
            raise ValueError("tokens and tasks must be on the same device")
        if torch.any(tokens < 0) or torch.any(tokens >= BYTE_VOCAB_SIZE):
            raise ValueError("byte token id out of range")
        if torch.any((tasks != TASK_NEXT) & (tasks != TASK_INSTRUCTION)):
            raise ValueError("tasks must be NEXT(0) or INSTRUCTION(1)")

        parameter = next(self.parameters())
        positions = torch.arange(self.config.max_tokens, device=tokens.device)
        valid = (tokens != PAD).unsqueeze(-1)
        context = self.byte_embedding(tokens) + self.position_embedding(positions).unsqueeze(0)
        context = context * valid.to(dtype=context.dtype)
        working = self.core.initial_working_state(
            tokens.shape[0], device=tokens.device, dtype=parameter.dtype
        )
        for _ in range(self.config.internal_steps):
            next_state = self.core(working, context, route_index=self.config.next_route)
            instruction_state = self.core(
                working, context, route_index=self.config.instruction_route
            )
            instruction_mask = tasks.bool().view(-1, 1, 1)
            working = torch.where(instruction_mask, instruction_state, next_state)

        valid_float = valid.to(dtype=working.dtype)
        pooled = (working * valid_float).sum(dim=1) / valid_float.sum(dim=1).clamp_min(1.0)
        return self.decoder(self.readout_norm(pooled))


@torch.inference_mode()
def evaluate_language(
    model: ShortByteLanguageModel,
    examples: LanguageExamples,
) -> dict[str, float]:
    if not isinstance(model, ShortByteLanguageModel):
        raise TypeError("model must be ShortByteLanguageModel")
    if not isinstance(examples, LanguageExamples):
        raise TypeError("examples must be LanguageExamples")
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        tokens = examples.tokens.to(parameter.device)
        tasks = examples.tasks.to(parameter.device)
        targets = examples.targets.to(parameter.device)
        languages = examples.languages.to(parameter.device)
        logits = model(tokens, tasks)
        nll = float(F.cross_entropy(logits, targets).item())
        predicted = logits.argmax(dim=-1)
        correct = predicted == targets

        def subgroup(mask: torch.Tensor) -> float:
            if not torch.any(mask):
                raise ValueError("evaluation subgroup must be non-empty")
            return float(correct[mask].float().mean().item())

        accuracy = float(correct.float().mean().item())
        metrics = {
            "nll": nll,
            "perplexity": math.exp(min(nll, 80.0)),
            "accuracy": accuracy,
            "english_accuracy": subgroup(languages == LANG_EN),
            "japanese_accuracy": subgroup(languages == LANG_JA),
            "next_accuracy": subgroup(tasks == TASK_NEXT),
            "instruction_accuracy": subgroup(tasks == TASK_INSTRUCTION),
        }
    finally:
        model.train(training)
    return metrics


def train_short_language_task(
    *,
    config: LanguageTaskConfig | None = None,
    seed: int = 20260911,
    steps: int = 600,
    learning_rate: float = 0.01,
    batch_size: int = 24,
    device: str | torch.device = "cpu",
) -> dict:
    """Train one deterministic held-out bilingual byte smoke experiment."""
    config = config or LanguageTaskConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be a positive integer")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    torch.manual_seed(seed)
    train, validation = make_language_splits(config)
    device = torch.device(device)
    model = ShortByteLanguageModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial = evaluate_language(model, validation)
    model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        tokens = train.tokens[indices].to(device)
        tasks = train.tasks[indices].to(device)
        targets = train.targets[indices].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(tokens, tasks)
        loss = F.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise ValueError("language training produced non-finite loss")
        loss.backward()
        optimizer.step()

    final = evaluate_language(model, validation)
    return {
        "seed": seed,
        "steps": steps,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_examples": train.size,
        "validation_examples": validation.size,
        "initial": initial,
        "final": final,
    }
