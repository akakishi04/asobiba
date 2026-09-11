"""Measure how exact-distance filler changes the FOLD-R recurrent memory state.

The diagnostic compares same-length original/counterfactual prompt pairs that differ
only in the distant owner.  It snapshots the recurrent FOLD-R state before filler
and at fixed fractions through filler.  This separates common state drift from
changes to the owner-specific state difference.

Example::

    python -m fold_lm.memory_state_drift \
        --checkpoint runs/long-memory-distance-2048-on-5k/best.pt \
        --validation data/raw/long-memory-distance-2048/validation.jsonl \
        --examples 64 --device cuda \
        --output runs/distance-2048-filler-drift.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch

from .data import json_text
from .long_memory_benchmark import (
    DEFAULT_COUNTERFACTUAL_SEED,
    FACT_RE,
    OwnerExample,
    load_validation,
    make_counterfactuals,
)
from .long_memory_distance import FILLER_UNIT
from .model import BOS, FoldLanguageModel, ModelConfig
from .runner import device_for, load_checkpoint


QUESTION_MARKER = b"Question: "
FILLER_MARKER = FILLER_UNIT.encode("utf-8")
DEFAULT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


def filler_bounds(prompt: str) -> tuple[int, int]:
    """Return byte offsets [start, end) for the exact-distance neutral filler."""
    raw = prompt.encode("utf-8")
    start = raw.find(FILLER_MARKER)
    end = raw.rfind(QUESTION_MARKER)
    if start < 0:
        raise ValueError("Prompt does not contain the exact-distance filler marker")
    if end <= start:
        raise ValueError("Prompt does not contain a question after the filler")
    return start, end


def original_prompt(counterfactual: OwnerExample) -> str:
    """Reconstruct the original same-length prompt from a counterfactual example."""
    if counterfactual.original_owner is None:
        raise ValueError("Counterfactual example is missing original_owner")
    match = FACT_RE.match(counterfactual.prompt)
    if not match or match.group(2) != counterfactual.expected:
        raise ValueError("Counterfactual fact does not match expected owner")
    return (
        counterfactual.prompt[:match.start(2)]
        + counterfactual.original_owner
        + counterfactual.prompt[match.end(2):]
    )


def _parse_fractions(text: str) -> tuple[float, ...]:
    try:
        values = tuple(float(part.strip()) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("fractions must be comma-separated numbers in [0,1]") from exc
    if not values or any(not math.isfinite(value) or value < 0 or value > 1 for value in values):
        raise ValueError("fractions must be comma-separated numbers in [0,1]")
    values = tuple(sorted(set(values) | {0.0, 1.0}))
    return values


def _state_parts(state: dict) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    W = state["W"].float().flatten(1)
    b = state["b"].float().flatten(1)
    return W, b, torch.cat((W, b), dim=1)


def _norm(x: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(x))


def _cosine(a: torch.Tensor, b: torch.Tensor) -> float | None:
    denom = torch.linalg.vector_norm(a) * torch.linalg.vector_norm(b)
    if float(denom) <= 1e-12:
        return None
    return float(torch.dot(a, b) / denom)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _snapshot_metrics(
    current: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    baseline: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
) -> dict[str, float | None]:
    cur_W, cur_b, cur = current
    base_W, base_b, base = baseline
    signal = cur[0] - cur[1]
    base_signal = base[0] - base[1]
    signal_norm = _norm(signal)
    base_signal_norm = _norm(base_signal)
    common = 0.5 * (cur[0] + cur[1])
    base_common = 0.5 * (base[0] + base[1])

    w_signal = cur_W[0] - cur_W[1]
    base_w_signal = base_W[0] - base_W[1]
    b_signal = cur_b[0] - cur_b[1]
    base_b_signal = base_b[0] - base_b[1]

    return {
        "owner_signal_norm": signal_norm,
        "owner_signal_ratio": signal_norm / base_signal_norm if base_signal_norm > 1e-12 else None,
        "owner_signal_cosine_to_start": _cosine(signal, base_signal),
        "owner_signal_change_norm": _norm(signal - base_signal),
        "common_state_drift_norm": _norm(common - base_common),
        "original_state_drift_norm": _norm(cur[0] - base[0]),
        "counterfactual_state_drift_norm": _norm(cur[1] - base[1]),
        "w_owner_signal_norm": _norm(w_signal),
        "w_owner_signal_ratio": _norm(w_signal) / _norm(base_w_signal) if _norm(base_w_signal) > 1e-12 else None,
        "b_owner_signal_norm": _norm(b_signal),
        "b_owner_signal_ratio": _norm(b_signal) / _norm(base_b_signal) if _norm(base_b_signal) > 1e-12 else None,
    }


@torch.inference_mode()
def measure_filler_state_drift(
    checkpoint: Path,
    validation: Path,
    *,
    device_name: str = "auto",
    examples: int = 64,
    fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
    counterfactual_seed: int = DEFAULT_COUNTERFACTUAL_SEED,
) -> dict:
    if examples <= 0:
        raise ValueError("examples must be positive")
    if any(value < 0 or value > 1 for value in fractions):
        raise ValueError("fractions must lie in [0,1]")
    fractions = tuple(sorted(set(fractions) | {0.0, 1.0}))

    ckpt = load_checkpoint(checkpoint)
    config = ModelConfig(**ckpt["config"]["model"])
    if not config.memory:
        raise ValueError("Filler state drift requires a checkpoint with memory=true")
    device = device_for(device_name)
    torch.set_num_threads(ckpt["config"]["train"]["cpu_threads"])
    model = FoldLanguageModel(config).to(device).eval()
    model.load_state_dict(ckpt["model"])

    source = load_validation(validation)
    changed, _ = make_counterfactuals(
        source,
        seed=counterfactual_seed,
        local_window=config.window,
    )
    selected = changed[:examples]
    if not selected:
        raise ValueError("No counterfactual pairs available")

    aggregates: dict[float, dict[str, list[float]]] = {
        fraction: {} for fraction in fractions
    }
    bytes_at_fraction: dict[float, list[float]] = {fraction: [] for fraction in fractions}
    filler_lengths = []

    for counterfactual in selected:
        original = original_prompt(counterfactual)
        original_raw = original.encode("utf-8")
        changed_raw = counterfactual.prompt.encode("utf-8")
        if len(original_raw) != len(changed_raw):
            raise RuntimeError("Counterfactual pair changed prompt byte length")

        start, end = filler_bounds(original)
        changed_start, changed_end = filler_bounds(counterfactual.prompt)
        if (start, end) != (changed_start, changed_end):
            raise RuntimeError("Counterfactual pair changed filler boundaries")
        if original_raw[start:end] != changed_raw[start:end]:
            raise RuntimeError("Counterfactual pair changed filler bytes")

        filler = original_raw[start:end]
        filler_lengths.append(len(filler))
        prefix_batch = torch.tensor(
            [[BOS] + list(original_raw[:start]), [BOS] + list(changed_raw[:start])],
            dtype=torch.long,
            device=device,
        )
        _, state = model(prefix_batch)
        baseline = tuple(part.clone() for part in _state_parts(state))

        offsets = {fraction: int(round(len(filler) * fraction)) for fraction in fractions}
        previous = 0
        for fraction in fractions:
            offset = offsets[fraction]
            if offset > previous:
                piece = torch.tensor(
                    [list(filler[previous:offset]), list(filler[previous:offset])],
                    dtype=torch.long,
                    device=device,
                )
                _, state = model(piece, state)
                previous = offset

            metrics = _snapshot_metrics(_state_parts(state), baseline)
            bytes_at_fraction[fraction].append(float(offset))
            bucket = aggregates[fraction]
            for key, value in metrics.items():
                if value is not None and math.isfinite(value):
                    bucket.setdefault(key, []).append(float(value))

    points = []
    for fraction in fractions:
        bucket = aggregates[fraction]
        point = {
            "fraction": fraction,
            "mean_filler_bytes_processed": _mean(bytes_at_fraction[fraction]),
        }
        for key in (
            "owner_signal_norm",
            "owner_signal_ratio",
            "owner_signal_cosine_to_start",
            "owner_signal_change_norm",
            "common_state_drift_norm",
            "original_state_drift_norm",
            "counterfactual_state_drift_norm",
            "w_owner_signal_norm",
            "w_owner_signal_ratio",
            "b_owner_signal_norm",
            "b_owner_signal_ratio",
        ):
            point[f"mean_{key}"] = _mean(bucket.get(key, []))
        points.append(point)

    return {
        "benchmark": "fold-r-filler-state-drift-v1",
        "checkpoint": str(checkpoint),
        "checkpoint_step": ckpt["step"],
        "validation": str(validation),
        "examples": len(selected),
        "counterfactual_seed": counterfactual_seed,
        "local_attention_window": config.window,
        "filler_bytes": {"min": min(filler_lengths), "max": max(filler_lengths)},
        "interpretation": {
            "owner_signal_ratio": "1 means owner-specific state separation kept the same norm as at filler start; >1 amplification; <1 attenuation",
            "owner_signal_cosine_to_start": "1 means the owner-specific state-difference direction was preserved; lower values indicate rotation",
            "common_state_drift_norm": "owner-independent/shared movement of the recurrent state during filler",
        },
        "points": points,
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
    parser = argparse.ArgumentParser(description="Measure FOLD-R state drift through exact-distance filler")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--examples", type=int, default=64)
    parser.add_argument("--fractions", default="0,0.25,0.5,0.75,1")
    parser.add_argument("--counterfactual-seed", type=int, default=DEFAULT_COUNTERFACTUAL_SEED)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = measure_filler_state_drift(
        args.checkpoint,
        args.validation,
        device_name=args.device,
        examples=args.examples,
        fractions=_parse_fractions(args.fractions),
        counterfactual_seed=args.counterfactual_seed,
    )
    _write_result(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
