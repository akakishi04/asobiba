"""Deterministic synthetic long-memory benchmark used by the FOLD-R prototype.

This module intentionally keeps the benchmark small and explicit.  It generates
prompt/target SFT JSONL, scores a fixed 12-name owner candidate set, and builds a
counterfactual control where only the distant owner fact changes while the final
local-attention-visible suffix remains byte-identical.

No work starts at import time.  Run with::

    python -m fold_lm.long_memory_benchmark generate --output data/raw/long-memory-sft-repro
    python -m fold_lm.long_memory_benchmark compare \
        --memory-on runs/long-memory-sft-on-2k/best.pt \
        --memory-off runs/long-memory-sft-off-2k/best.pt \
        --validation data/raw/long-memory-sft-repro/validation.jsonl \
        --device cuda
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
import re
import tempfile
import time

import torch

from .data import digest_file, json_text
from .model import BOS, PAD, FoldLanguageModel, ModelConfig
from .runner import device_for, load_checkpoint


NAMES = (
    "Alice", "Bob", "Carol", "Dave", "Emma", "Frank",
    "Grace", "Henry", "Iris", "Jack", "Kate", "Leo",
)
OBJECTS = (
    "red key", "blue key", "green key", "silver key",
    "gold coin", "small book", "glass cup", "wooden box",
)
TARGET_RE = re.compile(r"([A-Za-z]+)\.")
FACT_RE = re.compile(r"^(Important fact: the [^.]+ belongs to )([A-Za-z]+)(\.)")
DEFAULT_TRAIN_SEED = 20260909
DEFAULT_VALIDATION_SEED = 20260910
DEFAULT_COUNTERFACTUAL_SEED = 20260910
DEFAULT_LOCAL_WINDOW = 64
DEFAULT_MAX_BYTES = 250


@dataclass(frozen=True)
class OwnerExample:
    prompt: str
    expected: str
    original_owner: str | None = None


def _full_text(prompt: str, target: str) -> str:
    return prompt + target


def _build_row(rng: random.Random, *, local_window: int, max_bytes: int) -> tuple[dict, int, int]:
    owner = rng.choice(NAMES)
    obj = rng.choice(OBJECTS)
    others = [name for name in NAMES if name != owner]
    rng.shuffle(others)

    fact_prefix = f"Important fact: the {obj} belongs to "
    prompt = (
        f"{fact_prefix}{owner}. "
        f"{others[0]} walked through the garden. "
        f"{others[1]} looked at the clouds. "
        f"{others[2]} opened a window. "
        f"Question: who owns the {obj}? Answer: "
    )
    target = f"{owner}."
    text = _full_text(prompt, target)

    fact_owner_byte = len(fact_prefix.encode("utf-8"))
    answer_owner_byte = len(prompt.encode("utf-8"))
    distance = answer_owner_byte - fact_owner_byte
    total_bytes = len(text.encode("utf-8"))

    if distance <= local_window:
        raise RuntimeError(f"Generated fact distance {distance} does not exceed local window {local_window}")
    if total_bytes > max_bytes:
        raise RuntimeError(f"Generated example is {total_bytes} bytes, over max {max_bytes}")

    return {"prompt": prompt, "target": target}, distance, total_bytes


def generate_dataset(
    output: Path,
    *,
    train_rows: int = 20_000,
    validation_rows: int = 2_000,
    train_seed: int = DEFAULT_TRAIN_SEED,
    validation_seed: int = DEFAULT_VALIDATION_SEED,
    local_window: int = DEFAULT_LOCAL_WINDOW,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """Generate the ownership benchmark without overwriting existing data.

    Training rows deliberately retain exact duplicates so the normal ``prepare``
    path exercises and records its de-duplication policy, matching the original
    experiment workflow.  Validation rows are unique and excluded from the set of
    training full texts.
    """
    if train_rows <= 0 or validation_rows <= 0:
        raise ValueError("train_rows and validation_rows must be positive")
    if local_window <= 0 or max_bytes <= 0:
        raise ValueError("local_window and max_bytes must be positive")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".long-memory-", dir=output.parent))
    known_files = ("train.jsonl", "validation.jsonl", "generation.json")
    try:
        train_rng = random.Random(train_seed)
        train = []
        train_texts = set()
        distances = []
        lengths = []
        for _ in range(train_rows):
            row, distance, total_bytes = _build_row(
                train_rng, local_window=local_window, max_bytes=max_bytes
            )
            train.append(row)
            train_texts.add(_full_text(row["prompt"], row["target"]))
            distances.append(distance)
            lengths.append(total_bytes)

        val_rng = random.Random(validation_seed)
        validation_by_text: dict[str, dict] = {}
        attempts = 0
        while len(validation_by_text) < validation_rows:
            attempts += 1
            row, distance, total_bytes = _build_row(
                val_rng, local_window=local_window, max_bytes=max_bytes
            )
            text = _full_text(row["prompt"], row["target"])
            if text in train_texts or text in validation_by_text:
                continue
            validation_by_text[text] = row
            distances.append(distance)
            lengths.append(total_bytes)

        # The original validation-v2 repair wrote the unique set in sorted full-text
        # order.  Preserve that convention for stable reproduction.
        validation = [validation_by_text[text] for text in sorted(validation_by_text)]

        for name, rows in (("train.jsonl", train), ("validation.jsonl", validation)):
            with (stage / name).open("x", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        overlap = train_texts & set(validation_by_text)
        if overlap:
            raise RuntimeError("Generator produced train/validation overlap")

        meta = {
            "schema": 1,
            "benchmark": "fold-r-long-memory-owner-v1",
            "train_rows": train_rows,
            "train_unique": len(train_texts),
            "validation_rows": validation_rows,
            "validation_unique": len(validation_by_text),
            "validation_attempts": attempts,
            "cross_split_overlap": 0,
            "train_seed": train_seed,
            "validation_seed": validation_seed,
            "local_window_bytes": local_window,
            "max_example_bytes": max_bytes,
            "fact_to_answer_distance_bytes": {"min": min(distances), "max": max(distances)},
            "example_bytes": {"min": min(lengths), "max": max(lengths)},
            "names": list(NAMES),
            "objects": list(OBJECTS),
            "files": {
                "train.jsonl": digest_file(stage / "train.jsonl"),
                "validation.jsonl": digest_file(stage / "validation.jsonl"),
            },
        }
        (stage / "generation.json").write_text(json_text(meta), encoding="utf-8")
        stage.rename(output)
        return meta
    finally:
        if stage.exists():
            for name in known_files:
                (stage / name).unlink(missing_ok=True)
            stage.rmdir()


def load_validation(path: Path) -> list[OwnerExample]:
    examples = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}") from exc
            if not isinstance(obj, dict) or not isinstance(obj.get("prompt"), str) or not isinstance(obj.get("target"), str):
                raise ValueError(f"Expected prompt/target strings at {path}:{line_no}")
            match = TARGET_RE.fullmatch(obj["target"])
            if not match or match.group(1) not in NAMES:
                raise ValueError(f"Invalid owner target at {path}:{line_no}")
            expected = match.group(1)
            fact = FACT_RE.match(obj["prompt"])
            if not fact or fact.group(2) != expected:
                raise ValueError(f"Fact/target owner mismatch at {path}:{line_no}")
            examples.append(OwnerExample(obj["prompt"], expected))
    if not examples:
        raise ValueError(f"No validation examples in {path}")
    return examples


def make_counterfactuals(
    examples: list[OwnerExample],
    *,
    seed: int = DEFAULT_COUNTERFACTUAL_SEED,
    local_window: int = DEFAULT_LOCAL_WINDOW,
) -> tuple[list[OwnerExample], dict[str, int]]:
    """Change only the distant owner while preserving prompt length/local suffix."""
    if local_window <= 0:
        raise ValueError("local_window must be positive")
    rng = random.Random(seed)
    changed_examples = []
    counts = Counter()

    for example in examples:
        match = FACT_RE.match(example.prompt)
        if not match or match.group(2) != example.expected:
            raise ValueError("Counterfactual input fact does not match expected owner")
        original = example.expected
        candidates = [
            name for name in NAMES
            if name != original
            and len(name.encode("utf-8")) == len(original.encode("utf-8"))
            and not re.search(rf"\b{re.escape(name)}\b", example.prompt)
        ]
        if not candidates:
            continue
        replacement = rng.choice(candidates)
        changed = example.prompt[:match.start(2)] + replacement + example.prompt[match.end(2):]

        old_raw = example.prompt.encode("utf-8")
        new_raw = changed.encode("utf-8")
        if len(old_raw) != len(new_raw):
            raise RuntimeError("Counterfactual changed prompt byte length")
        if old_raw[-local_window:] != new_raw[-local_window:]:
            raise RuntimeError("Counterfactual changed local-attention-visible suffix")

        changed_examples.append(OwnerExample(changed, replacement, original_owner=original))
        counts[replacement] += 1

    if not changed_examples:
        raise ValueError("No usable same-length counterfactual examples")
    return changed_examples, dict(sorted(counts.items()))


def _checkpoint_info(path: Path) -> tuple[dict, ModelConfig]:
    ckpt = load_checkpoint(path)
    config = ModelConfig(**ckpt["config"]["model"])
    return ckpt, config


@torch.inference_mode()
def evaluate_owner_candidates(
    checkpoint: Path,
    examples: list[OwnerExample],
    *,
    device_name: str = "auto",
    batch_examples: int = 16,
    mistake_limit: int = 10,
) -> dict:
    """Score each fixed candidate by summed owner-byte log probability."""
    if batch_examples <= 0 or mistake_limit < 0:
        raise ValueError("batch_examples must be positive and mistake_limit nonnegative")

    ckpt, config = _checkpoint_info(checkpoint)
    device = device_for(device_name)
    torch.set_num_threads(ckpt["config"]["train"]["cpu_threads"])
    model = FoldLanguageModel(config).to(device).eval()
    model.load_state_dict(ckpt["model"])

    groups: dict[int, list[tuple[bytes, OwnerExample]]] = defaultdict(list)
    for example in examples:
        raw = example.prompt.encode("utf-8")
        groups[len(raw)].append((raw, example))

    max_name_len = max(len(name.encode("utf-8")) for name in NAMES)
    correct = 0
    original_owner_predictions = 0
    total = 0
    margins = []
    mistakes = []
    started = time.perf_counter()

    for prefix_len, group in sorted(groups.items()):
        for start in range(0, len(group), batch_examples):
            batch = group[start:start + batch_examples]
            sequences = []
            metadata = []
            for prefix_bytes, _ in batch:
                for candidate in NAMES:
                    candidate_bytes = candidate.encode("utf-8")
                    sequences.append(
                        [BOS] + list(prefix_bytes) + list(candidate_bytes)
                        + [PAD] * (max_name_len - len(candidate_bytes))
                    )
                    metadata.append(candidate)

            tokens = torch.tensor(sequences, dtype=torch.long, device=device)
            logits, _ = model(tokens)
            log_probs = logits.float().log_softmax(-1)
            candidate_start = 1 + prefix_len
            scores = []
            for row, candidate in enumerate(metadata):
                score = 0.0
                for j, byte in enumerate(candidate.encode("utf-8")):
                    score += float(log_probs[row, candidate_start + j - 1, byte])
                scores.append(score)

            scores_tensor = torch.tensor(scores).view(len(batch), len(NAMES))
            top_values, top_indices = scores_tensor.topk(2, dim=1)
            for i, (_, example) in enumerate(batch):
                predicted = NAMES[int(top_indices[i, 0])]
                margin = float(top_values[i, 0] - top_values[i, 1])
                total += 1
                margins.append(margin)
                if predicted == example.expected:
                    correct += 1
                if example.original_owner is not None and predicted == example.original_owner:
                    original_owner_predictions += 1
                if predicted != example.expected and len(mistakes) < mistake_limit:
                    row = {
                        "expected": example.expected,
                        "predicted": predicted,
                        "margin": margin,
                    }
                    if example.original_owner is not None:
                        row = {
                            "old_fact": example.original_owner,
                            "new_fact": example.expected,
                            "predicted": predicted,
                            "margin": margin,
                        }
                    mistakes.append(row)

    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - started

    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_step": ckpt["step"],
        "memory": config.memory,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "local_attention_window": config.window,
        "examples": total,
        "correct": correct,
        "accuracy": correct / total,
        "chance_accuracy": 1 / len(NAMES),
        "mean_top1_margin": sum(margins) / len(margins),
        "elapsed_seconds": elapsed,
        "first_mistakes": mistakes,
    }
    if any(example.original_owner is not None for example in examples):
        result["original_owner_prediction_rate"] = original_owner_predictions / total
    return result


def compare_checkpoints(
    memory_on: Path,
    memory_off: Path,
    validation: Path,
    *,
    device_name: str = "auto",
    batch_examples: int = 16,
    counterfactual_seed: int = DEFAULT_COUNTERFACTUAL_SEED,
) -> dict:
    examples = load_validation(validation)
    on_ckpt, on_config = _checkpoint_info(memory_on)
    off_ckpt, off_config = _checkpoint_info(memory_off)
    del on_ckpt, off_ckpt
    if on_config.window != off_config.window:
        raise ValueError("ON/OFF local-attention windows differ; comparison is not controlled")

    counterfactuals, replacement_counts = make_counterfactuals(
        examples, seed=counterfactual_seed, local_window=on_config.window
    )
    return {
        "benchmark": "fold-r-long-memory-owner-v1",
        "validation": str(validation),
        "candidates": len(NAMES),
        "chance_accuracy": 1 / len(NAMES),
        "standard": {
            "memory_on": evaluate_owner_candidates(
                memory_on, examples, device_name=device_name, batch_examples=batch_examples
            ),
            "memory_off": evaluate_owner_candidates(
                memory_off, examples, device_name=device_name, batch_examples=batch_examples
            ),
        },
        "counterfactual": {
            "seed": counterfactual_seed,
            "examples": len(counterfactuals),
            "replacement_counts": replacement_counts,
            "memory_on": evaluate_owner_candidates(
                memory_on, counterfactuals, device_name=device_name, batch_examples=batch_examples
            ),
            "memory_off": evaluate_owner_candidates(
                memory_off, counterfactuals, device_name=device_name, batch_examples=batch_examples
            ),
        },
    }


def _write_result(result: dict, output: Path | None) -> None:
    text = json_text(result)
    if output is not None:
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FOLD-R synthetic long-memory benchmark")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate deterministic prompt/target JSONL")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--train-rows", type=int, default=20_000)
    generate.add_argument("--validation-rows", type=int, default=2_000)
    generate.add_argument("--train-seed", type=int, default=DEFAULT_TRAIN_SEED)
    generate.add_argument("--validation-seed", type=int, default=DEFAULT_VALIDATION_SEED)
    generate.add_argument("--local-window", type=int, default=DEFAULT_LOCAL_WINDOW)
    generate.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)

    evaluate = sub.add_parser("evaluate", help="evaluate one checkpoint on owner retrieval")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--validation", type=Path, required=True)
    evaluate.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    evaluate.add_argument("--batch-examples", type=int, default=16)
    evaluate.add_argument("--counterfactual", action="store_true")
    evaluate.add_argument("--counterfactual-seed", type=int, default=DEFAULT_COUNTERFACTUAL_SEED)
    evaluate.add_argument("--output", type=Path)

    compare = sub.add_parser("compare", help="run standard and counterfactual ON/OFF evaluation")
    compare.add_argument("--memory-on", type=Path, required=True)
    compare.add_argument("--memory-off", type=Path, required=True)
    compare.add_argument("--validation", type=Path, required=True)
    compare.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    compare.add_argument("--batch-examples", type=int, default=16)
    compare.add_argument("--counterfactual-seed", type=int, default=DEFAULT_COUNTERFACTUAL_SEED)
    compare.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "generate":
        result = generate_dataset(
            args.output,
            train_rows=args.train_rows,
            validation_rows=args.validation_rows,
            train_seed=args.train_seed,
            validation_seed=args.validation_seed,
            local_window=args.local_window,
            max_bytes=args.max_bytes,
        )
        print(json_text(result), end="")
        return 0

    examples = load_validation(args.validation)
    if args.command == "evaluate":
        if args.counterfactual:
            _, config = _checkpoint_info(args.checkpoint)
            examples, replacement_counts = make_counterfactuals(
                examples, seed=args.counterfactual_seed, local_window=config.window
            )
            result = evaluate_owner_candidates(
                args.checkpoint, examples, device_name=args.device, batch_examples=args.batch_examples
            )
            result["counterfactual_seed"] = args.counterfactual_seed
            result["replacement_counts"] = replacement_counts
        else:
            result = evaluate_owner_candidates(
                args.checkpoint, examples, device_name=args.device, batch_examples=args.batch_examples
            )
        _write_result(result, args.output)
        return 0

    if args.command == "compare":
        result = compare_checkpoints(
            args.memory_on,
            args.memory_off,
            args.validation,
            device_name=args.device,
            batch_examples=args.batch_examples,
            counterfactual_seed=args.counterfactual_seed,
        )
        _write_result(result, args.output)
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
