"""Exact-distance long-memory benchmark with diverse held-out filler.

Version 1 used one repeated neutral sentence to create distance.  That made the
intervening token stream itself a deterministic recurrent-state trajectory.  V2
keeps the ownership task and exact byte-distance contract, but varies filler per
example and uses disjoint train/validation filler vocabularies and templates.

The filler stream is generated from an RNG independent from the RNG selecting the
owner/object/distractors, so filler is not a deliberate owner cue.  Validation
therefore tests retrieval through filler patterns not seen during training.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import tempfile

from .data import digest_file, json_text
from .long_memory_benchmark import NAMES, OBJECTS
from .long_memory_distance import (
    DEFAULT_LOCAL_WINDOW,
    DEFAULT_TRAIN_SEED,
    DEFAULT_VALIDATION_SEED,
    FILLER_UNIT,
)


TRAIN_FILLER_WORDS = (
    "amber", "cedar", "drift", "field", "glass", "harbor", "linen", "meadow",
    "north", "paper", "quiet", "ridge", "silver", "stone", "timber", "violet",
)
VALIDATION_FILLER_WORDS = (
    "bronze", "canyon", "delta", "forest", "granite", "island", "marble", "orbit",
    "plain", "quartz", "river", "summit", "tunnel", "valley", "willow", "zenith",
)

TRAIN_TEMPLATES = (
    "Log {n}: {a} {b} {c}. ",
    "Record {n} notes {a} near {b} and {c}. ",
    "Status {n}: {a}; {b}; {c}. ",
)
VALIDATION_TEMPLATES = (
    "Memo {n}: {a} beside {b}; marker {c}. ",
    "Entry {n} lists {a}, {b}, then {c}. ",
    "Survey {n}: {a} beyond {b}, with {c}. ",
)


def _diverse_filler(length: int, rng: random.Random, *, split: str) -> str:
    """Return exactly ``length`` ASCII bytes of split-specific neutral filler."""
    if length < 0:
        raise ValueError("filler length must be nonnegative")
    if split == "train":
        words, templates = TRAIN_FILLER_WORDS, TRAIN_TEMPLATES
    elif split == "validation":
        words, templates = VALIDATION_FILLER_WORDS, VALIDATION_TEMPLATES
    else:
        raise ValueError("split must be 'train' or 'validation'")

    if length == 0:
        return ""

    # Preserve the existing diagnostic marker once at filler start.  Unlike v1,
    # it is not repeated to fill the gap, so its contribution does not scale with
    # requested distance.
    text = FILLER_UNIT[:length]
    while len(text) < length:
        a, b, c = (rng.choice(words) for _ in range(3))
        template = rng.choice(templates)
        text += template.format(n=rng.randrange(10_000), a=a, b=b, c=c)
    filler = text[:length]
    if len(filler.encode("ascii")) != length:
        raise RuntimeError("V2 filler failed exact ASCII byte-length contract")

    lowered = filler.lower()
    forbidden = tuple(name.lower() for name in NAMES) + tuple(obj.lower() for obj in OBJECTS)
    if any(term and term in lowered for term in forbidden):
        raise RuntimeError("V2 filler unexpectedly contains an owner/object benchmark term")
    return filler


def _build_exact_row_v2(
    content_rng: random.Random,
    filler_rng: random.Random,
    *,
    target_distance: int,
    local_window: int,
    split: str,
) -> tuple[dict, int, int]:
    owner = content_rng.choice(NAMES)
    obj = content_rng.choice(OBJECTS)
    others = [name for name in NAMES if name != owner]
    content_rng.shuffle(others)

    fact_prefix = f"Important fact: the {obj} belongs to "
    distractors = (
        f"{owner}. "
        f"{others[0]} walked through the garden. "
        f"{others[1]} looked at the clouds. "
        f"{others[2]} opened a window. "
    )
    question = f"Question: who owns the {obj}? Answer: "

    base_prompt = fact_prefix + distractors + question
    fact_owner_byte = len(fact_prefix.encode("utf-8"))
    base_distance = len(base_prompt.encode("utf-8")) - fact_owner_byte
    if target_distance < base_distance:
        raise ValueError(
            f"target distance {target_distance} is shorter than generated base distance {base_distance}; "
            "use at least 134 bytes for this benchmark template"
        )
    if target_distance <= local_window:
        raise ValueError("target distance must exceed the local-attention window")

    filler_bytes = target_distance - base_distance
    filler = _diverse_filler(filler_bytes, filler_rng, split=split)
    prompt = fact_prefix + distractors + filler + question
    target = f"{owner}."

    distance = len(prompt.encode("utf-8")) - fact_owner_byte
    if distance != target_distance:
        raise RuntimeError(f"Exact-distance construction failed: {distance} != {target_distance}")

    total_bytes = len((prompt + target).encode("utf-8"))
    return {"prompt": prompt, "target": target}, filler_bytes, total_bytes


def generate_exact_distance_dataset_v2(
    output: Path,
    *,
    target_distance: int,
    train_rows: int = 20_000,
    validation_rows: int = 2_000,
    train_seed: int = DEFAULT_TRAIN_SEED,
    validation_seed: int = DEFAULT_VALIDATION_SEED,
    local_window: int = DEFAULT_LOCAL_WINDOW,
) -> dict:
    """Generate deterministic exact-distance SFT JSONL with held-out filler."""
    if train_rows <= 0 or validation_rows <= 0:
        raise ValueError("train_rows and validation_rows must be positive")
    if local_window <= 0:
        raise ValueError("local_window must be positive")
    if type(target_distance) is not int or target_distance <= 0:
        raise ValueError("target_distance must be a positive integer")
    if target_distance > 16 * 1024 * 1024 - 128:
        raise ValueError("target_distance is too large for the current 16 MiB document safety limit")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".long-memory-distance-v2-", dir=output.parent))
    known_files = ("train.jsonl", "validation.jsonl", "generation.json")
    try:
        train_content_rng = random.Random(train_seed)
        train_filler_rng = random.Random(train_seed ^ 0x5A17D15E)
        train = []
        train_texts = set()
        filler_lengths = []
        example_lengths = []
        train_fillers = set()
        for _ in range(train_rows):
            row, filler_bytes, total_bytes = _build_exact_row_v2(
                train_content_rng,
                train_filler_rng,
                target_distance=target_distance,
                local_window=local_window,
                split="train",
            )
            train.append(row)
            train_texts.add(row["prompt"] + row["target"])
            filler_lengths.append(filler_bytes)
            example_lengths.append(total_bytes)
            start = row["prompt"].find(FILLER_UNIT)
            train_fillers.add(row["prompt"][start:start + filler_bytes] if start >= 0 else "")

        val_content_rng = random.Random(validation_seed)
        val_filler_rng = random.Random(validation_seed ^ 0x2C91A4B7)
        validation_by_text: dict[str, dict] = {}
        validation_fillers = set()
        attempts = 0
        while len(validation_by_text) < validation_rows:
            attempts += 1
            row, filler_bytes, total_bytes = _build_exact_row_v2(
                val_content_rng,
                val_filler_rng,
                target_distance=target_distance,
                local_window=local_window,
                split="validation",
            )
            text = row["prompt"] + row["target"]
            if text in train_texts or text in validation_by_text:
                continue
            validation_by_text[text] = row
            filler_lengths.append(filler_bytes)
            example_lengths.append(total_bytes)
            start = row["prompt"].find(FILLER_UNIT)
            validation_fillers.add(row["prompt"][start:start + filler_bytes] if start >= 0 else "")

        if train_fillers & validation_fillers:
            raise RuntimeError("V2 generator produced exact train/validation filler overlap")

        validation = [validation_by_text[text] for text in sorted(validation_by_text)]
        for name, rows in (("train.jsonl", train), ("validation.jsonl", validation)):
            with (stage / name).open("x", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        overlap = train_texts & set(validation_by_text)
        if overlap:
            raise RuntimeError("Generator produced train/validation example overlap")

        meta = {
            "schema": 1,
            "benchmark": "fold-r-long-memory-owner-distance-v2-diverse-filler",
            "target_distance_bytes": target_distance,
            "fact_to_answer_distance_bytes": {"min": target_distance, "max": target_distance},
            "local_window_bytes": local_window,
            "train_rows": train_rows,
            "train_unique": len(train_texts),
            "validation_rows": validation_rows,
            "validation_unique": len(validation_by_text),
            "validation_attempts": attempts,
            "cross_split_overlap": 0,
            "exact_filler_overlap": 0,
            "train_seed": train_seed,
            "validation_seed": validation_seed,
            "filler_policy": {
                "kind": "diverse-held-out-v1",
                "independent_rng_streams": True,
                "shared_prefix_once": FILLER_UNIT,
                "train_vocabulary": list(TRAIN_FILLER_WORDS),
                "validation_vocabulary": list(VALIDATION_FILLER_WORDS),
                "train_templates": list(TRAIN_TEMPLATES),
                "validation_templates": list(VALIDATION_TEMPLATES),
            },
            "filler_bytes": {"min": min(filler_lengths), "max": max(filler_lengths)},
            "example_bytes": {"min": min(example_lengths), "max": max(example_lengths)},
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FOLD-R exact-distance diverse-filler dataset generator")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="generate one exact-distance diverse-filler ownership dataset")
    generate.add_argument("--distance", type=int, required=True, help="exact fact-owner to answer-owner byte distance")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--train-rows", type=int, default=20_000)
    generate.add_argument("--validation-rows", type=int, default=2_000)
    generate.add_argument("--train-seed", type=int, default=DEFAULT_TRAIN_SEED)
    generate.add_argument("--validation-seed", type=int, default=DEFAULT_VALIDATION_SEED)
    generate.add_argument("--local-window", type=int, default=DEFAULT_LOCAL_WINDOW)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "generate":
        raise AssertionError(args.command)
    result = generate_exact_distance_dataset_v2(
        args.output,
        target_distance=args.distance,
        train_rows=args.train_rows,
        validation_rows=args.validation_rows,
        train_seed=args.train_seed,
        validation_seed=args.validation_seed,
        local_window=args.local_window,
    )
    print(json_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
