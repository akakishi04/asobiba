"""Mixed-distance FOLD-R benchmark with held-out extrapolation distances.

Training covers a continuous range from 256 through 4096 bytes using equal
allocation across four log2-style bands. Distances inside each band are sampled
independently from owner/object content and from diverse filler generation.

The generated validation split stays inside the training distance range but uses
the held-out V2 filler vocabulary/templates. Separate evaluation files at 6144,
8192, 12288, and 16384 bytes are never present in training and are intended for
zero-shot distance-extrapolation evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import tempfile

from .data import digest_file, json_text
from .long_memory_distance import DEFAULT_LOCAL_WINDOW, DEFAULT_TRAIN_SEED, DEFAULT_VALIDATION_SEED
from .long_memory_distance_v2 import _build_exact_row_v2


TRAIN_DISTANCE_BANDS = (
    (256, 511),
    (512, 1023),
    (1024, 2047),
    (2048, 4096),
)
DEFAULT_EXTRAPOLATION_DISTANCES = (6144, 8192, 12288, 16384)
DEFAULT_EXTRAPOLATION_ROWS = 500


def _distance_schedule(rows: int, rng: random.Random) -> list[int]:
    """Return a shuffled, band-balanced schedule of training-range distances."""
    if rows <= 0:
        raise ValueError("rows must be positive")
    distances = []
    for i in range(rows):
        lo, hi = TRAIN_DISTANCE_BANDS[i % len(TRAIN_DISTANCE_BANDS)]
        distances.append(rng.randint(lo, hi))
    rng.shuffle(distances)
    return distances


def _band_name(distance: int) -> str:
    for lo, hi in TRAIN_DISTANCE_BANDS:
        if lo <= distance <= hi:
            return f"{lo}-{hi}"
    return "out-of-range"


def _build_unique_rows(
    *,
    distances: list[int],
    content_rng: random.Random,
    filler_rng: random.Random,
    split: str,
    local_window: int,
    forbidden_texts: set[str] | None = None,
) -> tuple[list[dict], set[str]]:
    rows = []
    texts: set[str] = set()
    forbidden = forbidden_texts or set()
    for distance in distances:
        for _ in range(100):
            row, _, _ = _build_exact_row_v2(
                content_rng,
                filler_rng,
                target_distance=distance,
                local_window=local_window,
                split=split,
            )
            text = row["prompt"] + row["target"]
            if text in texts or text in forbidden:
                continue
            row = dict(row)
            row["distance_bytes"] = distance
            rows.append(row)
            texts.add(text)
            break
        else:
            raise RuntimeError(f"Could not generate a unique row at distance {distance}")
    return rows, texts


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def generate_mixed_distance_dataset(
    output: Path,
    *,
    train_rows: int = 20_000,
    validation_rows: int = 2_000,
    extrapolation_rows: int = DEFAULT_EXTRAPOLATION_ROWS,
    train_seed: int = DEFAULT_TRAIN_SEED,
    validation_seed: int = DEFAULT_VALIDATION_SEED,
    local_window: int = DEFAULT_LOCAL_WINDOW,
    extrapolation_distances: tuple[int, ...] = DEFAULT_EXTRAPOLATION_DISTANCES,
) -> dict:
    """Generate mixed training data plus exact unseen-distance evaluation sets."""
    if train_rows <= 0 or validation_rows <= 0 or extrapolation_rows <= 0:
        raise ValueError("row counts must be positive")
    if local_window <= 0:
        raise ValueError("local_window must be positive")
    if not extrapolation_distances:
        raise ValueError("extrapolation_distances must be nonempty")
    train_max = max(hi for _, hi in TRAIN_DISTANCE_BANDS)
    if any(type(distance) is not int or distance <= train_max for distance in extrapolation_distances):
        raise ValueError("every extrapolation distance must be an integer greater than 4096")
    if len(set(extrapolation_distances)) != len(extrapolation_distances):
        raise ValueError("extrapolation distances must be unique")
    if max(extrapolation_distances) > 16 * 1024 * 1024 - 128:
        raise ValueError("extrapolation distance exceeds current 16 MiB safety limit")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".long-memory-mixed-", dir=output.parent))
    generated_names: list[str] = []
    try:
        train_dist_rng = random.Random(train_seed ^ 0x13579BDF)
        train_content_rng = random.Random(train_seed)
        train_filler_rng = random.Random(train_seed ^ 0x5A17D15E)
        train_distances = _distance_schedule(train_rows, train_dist_rng)
        train, train_texts = _build_unique_rows(
            distances=train_distances,
            content_rng=train_content_rng,
            filler_rng=train_filler_rng,
            split="train",
            local_window=local_window,
        )
        _write_jsonl(stage / "train.jsonl", train)
        generated_names.append("train.jsonl")

        val_dist_rng = random.Random(validation_seed ^ 0x2468ACE0)
        val_content_rng = random.Random(validation_seed)
        val_filler_rng = random.Random(validation_seed ^ 0x2C91A4B7)
        validation_distances = _distance_schedule(validation_rows, val_dist_rng)
        validation, validation_texts = _build_unique_rows(
            distances=validation_distances,
            content_rng=val_content_rng,
            filler_rng=val_filler_rng,
            split="validation",
            local_window=local_window,
            forbidden_texts=train_texts,
        )
        _write_jsonl(stage / "validation.jsonl", validation)
        generated_names.append("validation.jsonl")

        heldout_texts = set(validation_texts)
        extrapolation_meta = {}
        for index, distance in enumerate(extrapolation_distances):
            content_rng = random.Random(validation_seed ^ (0x71000000 + distance + index))
            filler_rng = random.Random(validation_seed ^ (0x4D000000 + distance + index))
            distances = [distance] * extrapolation_rows
            rows, texts = _build_unique_rows(
                distances=distances,
                content_rng=content_rng,
                filler_rng=filler_rng,
                split="validation",
                local_window=local_window,
                forbidden_texts=train_texts | heldout_texts,
            )
            heldout_texts.update(texts)
            name = f"eval-{distance}.jsonl"
            _write_jsonl(stage / name, rows)
            generated_names.append(name)
            extrapolation_meta[str(distance)] = {
                "rows": len(rows),
                "unique": len(texts),
                "file": name,
            }

        if train_texts & heldout_texts:
            raise RuntimeError("Mixed generator produced train/held-out overlap")

        train_band_counts = Counter(_band_name(distance) for distance in train_distances)
        validation_band_counts = Counter(_band_name(distance) for distance in validation_distances)
        files = {name: digest_file(stage / name) for name in generated_names}
        meta = {
            "schema": 1,
            "benchmark": "fold-r-long-memory-mixed-distance-v1",
            "local_window_bytes": local_window,
            "train_rows": len(train),
            "train_unique": len(train_texts),
            "validation_rows": len(validation),
            "validation_unique": len(validation_texts),
            "cross_split_overlap": 0,
            "train_seed": train_seed,
            "validation_seed": validation_seed,
            "training_distance_policy": {
                "kind": "balanced-log2-bands-uniform-within-band",
                "min_bytes": min(lo for lo, _ in TRAIN_DISTANCE_BANDS),
                "max_bytes": train_max,
                "bands": [list(band) for band in TRAIN_DISTANCE_BANDS],
                "counts": dict(sorted(train_band_counts.items())),
                "distance_rng_independent_from_content_and_filler": True,
            },
            "validation_distance_policy": {
                "min_bytes": min(validation_distances),
                "max_bytes": max(validation_distances),
                "counts": dict(sorted(validation_band_counts.items())),
                "held_out_filler_vocabulary_and_templates": True,
            },
            "extrapolation": extrapolation_meta,
            "extrapolation_distances_seen_in_training": 0,
            "files": files,
        }
        (stage / "generation.json").write_text(json_text(meta), encoding="utf-8")
        generated_names.append("generation.json")
        stage.rename(output)
        return meta
    finally:
        if stage.exists():
            for name in generated_names:
                (stage / name).unlink(missing_ok=True)
            (stage / "generation.json").unlink(missing_ok=True)
            stage.rmdir()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate mixed-distance FOLD-R long-memory benchmark data")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-rows", type=int, default=20_000)
    parser.add_argument("--validation-rows", type=int, default=2_000)
    parser.add_argument("--extrapolation-rows", type=int, default=DEFAULT_EXTRAPOLATION_ROWS)
    parser.add_argument("--train-seed", type=int, default=DEFAULT_TRAIN_SEED)
    parser.add_argument("--validation-seed", type=int, default=DEFAULT_VALIDATION_SEED)
    parser.add_argument("--local-window", type=int, default=DEFAULT_LOCAL_WINDOW)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = generate_mixed_distance_dataset(
        args.output,
        train_rows=args.train_rows,
        validation_rows=args.validation_rows,
        extrapolation_rows=args.extrapolation_rows,
        train_seed=args.train_seed,
        validation_seed=args.validation_seed,
        local_window=args.local_window,
    )
    print(json_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
