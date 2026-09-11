"""V5-C diagnostic frontier for composition-sensitive module compression.

C7/C8 showed that the first balanced compression candidate preserves some tasks
but destroys the recurrent composition task even when compressed weights are
materialized back into dense Linear layers.  This benchmark therefore ignores
runtime optimization and asks one narrower question:

    how much representation capacity is required before composition quality
    recovers?

Each seed trains the high-precision composition model exactly once, then applies
four fixed compression profiles to the same trained core.  Profiles are a
diagnostic ladder, not a final Gate-C choice.  Any candidate selected from this
frontier must later be re-tested on fresh seeds and the full task set.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS
from fold_lm.v05_benchmarks.gate_c_role_ablation import _materialized_variant
from fold_lm.v05_benchmarks.gate_c_task_quality import (
    CompressionProfile,
    _train_high_precision,
    compress_trained_core,
)


PROFILE_ORDER = ("balanced", "finer_blocks", "richer_codebooks", "high_fidelity")
PROFILES = {
    "balanced": CompressionProfile(
        block_rows=4,
        block_cols=4,
        codebook_count=2,
        entries_per_codebook=4,
        correction_fraction=0.015625,
        max_abs_correction=0.10,
        initial_tuning_steps=80,
        post_reassignment_tuning_steps=40,
        reassignment_sweeps=2,
        tuning_learning_rate=0.01,
    ),
    "finer_blocks": CompressionProfile(
        block_rows=2,
        block_cols=2,
        codebook_count=2,
        entries_per_codebook=4,
        correction_fraction=0.015625,
        max_abs_correction=0.10,
        initial_tuning_steps=80,
        post_reassignment_tuning_steps=40,
        reassignment_sweeps=2,
        tuning_learning_rate=0.01,
    ),
    "richer_codebooks": CompressionProfile(
        block_rows=4,
        block_cols=4,
        codebook_count=3,
        entries_per_codebook=8,
        correction_fraction=0.015625,
        max_abs_correction=0.10,
        initial_tuning_steps=100,
        post_reassignment_tuning_steps=50,
        reassignment_sweeps=2,
        tuning_learning_rate=0.01,
    ),
    "high_fidelity": CompressionProfile(
        block_rows=2,
        block_cols=2,
        codebook_count=3,
        entries_per_codebook=8,
        correction_fraction=0.03125,
        max_abs_correction=0.15,
        initial_tuning_steps=120,
        post_reassignment_tuning_steps=60,
        reassignment_sweeps=3,
        tuning_learning_rate=0.01,
    ),
}


def _validate_profile_names(profile_names: tuple[str, ...]) -> None:
    if not profile_names:
        raise ValueError("profile_names must be non-empty")
    if len(set(profile_names)) != len(profile_names):
        raise ValueError("profile_names must be unique")
    if any(name not in PROFILES for name in profile_names):
        raise ValueError("unknown profile name")


def run_seed(
    seed: int,
    *,
    profile_names: tuple[str, ...] = PROFILE_ORDER,
    device: str | torch.device = "cpu",
) -> list[dict]:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    _validate_profile_names(profile_names)
    device = torch.device(device)

    model, validation, evaluator, score_name = _train_high_precision(
        "composition", seed, device
    )
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained composition core must remain HighPrecisionFixedRoutingCore")
    high_metrics = evaluator(model, validation)
    high_score = float(high_metrics[score_name])

    records: list[dict] = []
    for profile_name in profile_names:
        profile = PROFILES[profile_name]
        compressed_core, diagnostics = compress_trained_core(
            model.core, profile, device=device
        )
        materialized = _materialized_variant(
            model,
            compressed_core,
            use_up=True,
            use_down=True,
        ).to(device)
        compressed_metrics = evaluator(materialized, validation)
        compressed_score = float(compressed_metrics[score_name])
        records.append(
            {
                "seed": seed,
                "profile": profile_name,
                "score_name": score_name,
                "high_precision_score": high_score,
                "compressed_score": compressed_score,
                "score_delta": compressed_score - high_score,
                "module_payload_ratio": float(diagnostics["module_payload_ratio"]),
                "up_final_reconstruction_mse": float(diagnostics["up"]["final_mse"]),
                "down_final_reconstruction_mse": float(diagnostics["down"]["final_mse"]),
                "correction_nnz": int(diagnostics["correction_nnz"]),
                "max_observed_abs_correction": float(
                    diagnostics["max_observed_abs_correction"]
                ),
                "profile_config": profile.__dict__,
            }
        )
    return records


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    summary: dict[str, dict] = {}
    for profile_name in PROFILE_ORDER:
        rows = [row for row in records if row["profile"] == profile_name]
        if not rows:
            continue
        summary[profile_name] = {
            "runs": len(rows),
            "mean_high_precision_score": sum(
                float(row["high_precision_score"]) for row in rows
            ) / len(rows),
            "mean_compressed_score": sum(
                float(row["compressed_score"]) for row in rows
            ) / len(rows),
            "min_compressed_score": min(float(row["compressed_score"]) for row in rows),
            "mean_score_delta": sum(float(row["score_delta"]) for row in rows) / len(rows),
            "worst_score_delta": min(float(row["score_delta"]) for row in rows),
            "mean_module_payload_ratio": sum(
                float(row["module_payload_ratio"]) for row in rows
            ) / len(rows),
            "mean_up_final_reconstruction_mse": sum(
                float(row["up_final_reconstruction_mse"]) for row in rows
            ) / len(rows),
            "mean_down_final_reconstruction_mse": sum(
                float(row["down_final_reconstruction_mse"]) for row in rows
            ) / len(rows),
            "max_observed_abs_correction": max(
                float(row["max_observed_abs_correction"]) for row in rows
            ),
        }
    return {"profiles": summary}


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    profile_names: tuple[str, ...] = PROFILE_ORDER,
    device: str | torch.device = "cpu",
) -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(
        type(seed) is not int or seed < 0 for seed in seeds
    ):
        raise ValueError("seeds must be distinct nonnegative integers")
    _validate_profile_names(profile_names)

    records: list[dict] = []
    total = len(seeds) * len(profile_names)
    completed = 0
    for seed in seeds:
        print(
            f"[gate-c-frontier] train composition seed={seed}",
            file=sys.stderr,
            flush=True,
        )
        seed_records = run_seed(
            seed,
            profile_names=profile_names,
            device=device,
        )
        for record in seed_records:
            completed += 1
            records.append(record)
            print(
                f"[gate-c-frontier] done seed={seed} profile={record['profile']} "
                f"score={record['compressed_score']:.6f} "
                f"payload={record['module_payload_ratio']:.6f} "
                f"({completed}/{total})",
                file=sys.stderr,
                flush=True,
            )

    return {
        "schema": "fold-v05-gate-c-composition-frontier-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "profile_names": list(profile_names),
        "records": records,
        "summary": summarize(records),
        "diagnostic_only": True,
        "fresh_seed_revalidation_required": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=PROFILE_ORDER,
        default=list(PROFILE_ORDER),
    )
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        profile_names=tuple(args.profiles),
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
