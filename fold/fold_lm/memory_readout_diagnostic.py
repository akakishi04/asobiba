"""Decompose where owner-specific FOLD-R signal changes inside capsule readout.

This diagnostic complements ``memory_state_drift``. It compares same-length
original/counterfactual pairs at fixed fractions through filler and measures the
owner-specific separation at four stages:

1. raw recurrent state (W,b)
2. capsule RHS: b - Wg
3. solved correction: (I + WK)^-1 (b - Wg)
4. final capsule response: y0 + V correction

It also reports the spectrum of the symmetric positive-definite denominator form
I + L.T W L (K = L L.T) for the pair-common W state. This helps distinguish
raw-memory retention from RHS cancellation and solve-stage attenuation.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import torch

from .capsule import compile_capsule
from .data import json_text
from .long_memory_benchmark import (
    DEFAULT_COUNTERFACTUAL_SEED,
    load_validation,
    make_counterfactuals,
)
from .memory_state_drift import (
    DEFAULT_FRACTIONS,
    _parse_fractions,
    filler_bounds,
    original_prompt,
)
from .model import BOS, FoldLanguageModel, ModelConfig
from .runner import device_for, load_checkpoint


def _norm(x: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(x))


def _cosine(a: torch.Tensor, b: torch.Tensor) -> float | None:
    denom = torch.linalg.vector_norm(a) * torch.linalg.vector_norm(b)
    if float(denom) <= 1e-12:
        return None
    return float(torch.dot(a, b) / denom)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pair_metrics(current: torch.Tensor, baseline: torch.Tensor, prefix: str) -> dict[str, float | None]:
    signal = current[0] - current[1]
    baseline_signal = baseline[0] - baseline[1]
    signal_norm = _norm(signal)
    baseline_norm = _norm(baseline_signal)
    return {
        f"{prefix}_signal_norm": signal_norm,
        f"{prefix}_signal_ratio": signal_norm / baseline_norm if baseline_norm > 1e-12 else None,
        f"{prefix}_signal_cosine_to_start": _cosine(signal, baseline_signal),
    }


def _readout_parts(capsule, state: dict) -> dict[str, torch.Tensor | float]:
    W = state["W"].float()
    b = state["b"].float()
    batch = W.shape[0]
    r = W.shape[-1]

    raw = torch.cat((W.flatten(1), b.flatten(1)), dim=1)
    rhs = (b.unsqueeze(-1) - W @ capsule.g.float().unsqueeze(-1)).squeeze(-1)
    eye = torch.eye(r, device=W.device, dtype=W.dtype)
    denominator = eye + W @ capsule.K.float()
    correction = torch.linalg.solve(denominator, rhs.unsqueeze(-1)).squeeze(-1)
    response = capsule.y0.float().unsqueeze(0).expand(batch, -1, -1) + (
        capsule.V.float().unsqueeze(0) @ correction.unsqueeze(-1)
    ).squeeze(-1)

    common_W = 0.5 * (W[0] + W[1])
    L = torch.linalg.cholesky(capsule.K.float())
    symmetric_denominator = eye + L.mT @ common_W @ L
    eig = torch.linalg.eigvalsh(symmetric_denominator)
    min_eig = float(eig.min())
    max_eig = float(eig.max())

    return {
        "raw": raw,
        "rhs": rhs.flatten(1),
        "correction": correction.flatten(1),
        "response": response.flatten(1),
        "common_w_norm": _norm(common_W),
        "common_b_norm": _norm(0.5 * (b[0] + b[1])),
        "denominator_min_eigenvalue": min_eig,
        "denominator_max_eigenvalue": max_eig,
        "denominator_condition": max_eig / min_eig if min_eig > 0 else math.inf,
        "inverse_min_gain_bound": 1.0 / max_eig if max_eig > 0 else math.inf,
        "inverse_max_gain_bound": 1.0 / min_eig if min_eig > 0 else math.inf,
    }


def _snapshot_metrics(current: dict, baseline: dict) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for key in ("raw", "rhs", "correction", "response"):
        metrics.update(_pair_metrics(current[key], baseline[key], key))
    for key in (
        "common_w_norm",
        "common_b_norm",
        "denominator_min_eigenvalue",
        "denominator_max_eigenvalue",
        "denominator_condition",
        "inverse_min_gain_bound",
        "inverse_max_gain_bound",
    ):
        metrics[key] = float(current[key])
    return metrics


@torch.inference_mode()
def measure_readout_diagnostic(
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
        raise ValueError("Readout diagnostic requires a checkpoint with memory=true")
    device = device_for(device_name)
    torch.set_num_threads(ckpt["config"]["train"]["cpu_threads"])
    model = FoldLanguageModel(config).to(device).eval()
    model.load_state_dict(ckpt["model"])

    J = (
        torch.eye(config.latent, device=device, dtype=model.base_A.dtype)
        + model.base_A @ model.base_A.mT
    )
    capsule = compile_capsule(J, model.base_eta, model.Q, model.U, check=False)

    source = load_validation(validation)
    changed, _ = make_counterfactuals(source, seed=counterfactual_seed, local_window=config.window)
    selected = changed[:examples]
    if not selected:
        raise ValueError("No counterfactual pairs available")

    metric_keys = (
        "raw_signal_norm",
        "raw_signal_ratio",
        "raw_signal_cosine_to_start",
        "rhs_signal_norm",
        "rhs_signal_ratio",
        "rhs_signal_cosine_to_start",
        "correction_signal_norm",
        "correction_signal_ratio",
        "correction_signal_cosine_to_start",
        "response_signal_norm",
        "response_signal_ratio",
        "response_signal_cosine_to_start",
        "common_w_norm",
        "common_b_norm",
        "denominator_min_eigenvalue",
        "denominator_max_eigenvalue",
        "denominator_condition",
        "inverse_min_gain_bound",
        "inverse_max_gain_bound",
    )
    aggregates: dict[float, dict[str, list[float]]] = {fraction: {} for fraction in fractions}
    bytes_at_fraction: dict[float, list[float]] = {fraction: [] for fraction in fractions}
    filler_lengths: list[int] = []

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
        baseline = _readout_parts(capsule, state)
        baseline = {
            key: value.clone() if isinstance(value, torch.Tensor) else value
            for key, value in baseline.items()
        }

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

            current = _readout_parts(capsule, state)
            metrics = _snapshot_metrics(current, baseline)
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
        for key in metric_keys:
            point[f"mean_{key}"] = _mean(bucket.get(key, []))
        points.append(point)

    return {
        "benchmark": "fold-r-memory-readout-diagnostic-v1",
        "checkpoint": str(checkpoint),
        "checkpoint_step": ckpt["step"],
        "validation": str(validation),
        "examples": len(selected),
        "local_attention_window": config.window,
        "filler_bytes": {"min": min(filler_lengths), "max": max(filler_lengths)},
        "interpretation": {
            "raw_signal_ratio": "owner-specific separation in recurrent W/b state relative to filler start",
            "rhs_signal_ratio": "owner-specific separation after forming b-Wg, before the solve",
            "correction_signal_ratio": "owner-specific separation after solving (I+WK)^-1 rhs, before V projection",
            "response_signal_ratio": "owner-specific separation in final capsule response",
            "denominator_max_eigenvalue": "largest eigenvalue of I+L.T W L for pair-common W; growth implies a smaller inverse gain floor",
            "inverse_min_gain_bound": "1 / denominator_max_eigenvalue; a simple lower-direction gain bound for the symmetric solve form",
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
    parser = argparse.ArgumentParser(description="Decompose FOLD-R readout attenuation through filler")
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
    result = measure_readout_diagnostic(
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
