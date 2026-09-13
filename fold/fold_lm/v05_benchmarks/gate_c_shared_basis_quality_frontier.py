"""C59: real-fixture shared-basis representation/quality frontier.

C58 established that a GPU-native shared-input low-rank basis can approach dense
runtime at large widths while using ~57.8% of two independent dense module
weights at rank W/16.  C59 asks the next necessary question on the trusted real
composition fixture: can the trained routed module weights be represented by the
same family without destroying task quality?

For each tested rank, fit each role independently as

    W_module = W_base + A_module @ B_shared

using the mean module weight as W_base and the optimal truncated SVD of the
stacked centered residuals.  The resulting weights are materialized only into a
copy of the already-trained dense model for evaluation; there is no training and
no production runtime modification.

Ranks above the sub-dense storage frontier are included only to locate the
capacity threshold and provide an exact-reconstruction sanity check.  With two
modules and this width-32 fixture, rank 32 can represent both Up and Down module
differences exactly (up to floating-point roundoff).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import time

import torch

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture


EXPERIMENT_ID = "C59-shared-basis-real-fixture-quality-frontier"
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
RANKS = (2, 4, 8, 12, 14, 16, 24, 32)
MODULES = 2


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _fit_role(weights: torch.Tensor, rank: int) -> dict[str, torch.Tensor | float]:
    if weights.ndim != 3 or int(weights.shape[0]) != MODULES:
        raise ValueError("C59 expects exactly two module weight matrices")
    module_count, output_width, input_width = map(int, weights.shape)
    max_rank = min(module_count * output_width, input_width)
    if rank <= 0 or rank > max_rank:
        raise ValueError(f"invalid C59 rank {rank} for role max_rank={max_rank}")

    base = weights.mean(dim=0)
    centered = weights - base.unsqueeze(0)
    stacked = centered.reshape(module_count * output_width, input_width)
    _u, _s, vh = torch.linalg.svd(stacked, full_matrices=False)
    basis = vh[:rank].contiguous()
    coefficients = torch.matmul(stacked, basis.transpose(0, 1)).reshape(
        module_count, output_width, rank
    )
    reconstructed = base.unsqueeze(0) + torch.matmul(coefficients, basis)
    error = reconstructed - weights
    return {
        "base": base,
        "basis": basis,
        "coefficients": coefficients,
        "reconstructed": reconstructed,
        "mse": float(error.square().mean().item()),
        "rmse": float(error.square().mean().sqrt().item()),
        "max_abs": float(error.abs().max().item()),
    }


def _weight_storage_bytes(
    *,
    width: int,
    hidden: int,
    rank: int,
    modules: int,
) -> dict[str, int | float | bool]:
    # Up: M=hidden, K=width. Down: M=width, K=hidden.
    dense_floats = modules * hidden * width + modules * width * hidden
    up_floats = hidden * width + rank * width + modules * hidden * rank
    down_floats = width * hidden + rank * hidden + modules * width * rank
    representation_floats = up_floats + down_floats
    dense_bytes = dense_floats * 4
    representation_bytes = representation_floats * 4
    return {
        "dense_weight_bytes": dense_bytes,
        "representation_weight_bytes": representation_bytes,
        "representation_weight_ratio": representation_bytes / dense_bytes,
        "below_dense_weight_bytes": representation_bytes < dense_bytes,
    }


@torch.inference_mode()
def run(*, fixture_path: Path, protected_result_path: Path, output_dir: Path) -> dict:
    protected_before = _sha256(protected_result_path)
    fixture_hash = _sha256(fixture_path)

    fixture = load_runtime_fixture(fixture_path, device="cuda")
    dense_model = fixture["models"]["dense"]
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C59 fixture dense core must be HighPrecisionFixedRoutingCore")
    core = dense_model.core
    if core.config.width != 32 or core.config.hidden_mult != 2 or core.config.modules != MODULES:
        raise RuntimeError(
            f"unexpected C59 core config: width={core.config.width} "
            f"hidden_mult={core.config.hidden_mult} modules={core.config.modules}"
        )

    width = int(core.config.width)
    hidden = width * int(core.config.hidden_mult)
    evaluator = fixture["evaluator"]
    validation = fixture["validation"]
    score_name = str(fixture["score_name"])
    fixture_scores = {name: float(value) for name, value in fixture["scores"].items()}

    dense_metrics = evaluator(dense_model, validation)
    dense_score = float(dense_metrics[score_name])

    up_weights = torch.stack(
        [module.up.weight.detach().float().cpu() for module in core.module_set], dim=0
    )
    down_weights = torch.stack(
        [module.down.weight.detach().float().cpu() for module in core.module_set], dim=0
    )

    records: list[dict] = []
    total = len(RANKS)
    for index, rank in enumerate(RANKS, start=1):
        up_fit = _fit_role(up_weights, rank)
        down_fit = _fit_role(down_weights, rank)
        storage = _weight_storage_bytes(
            width=width,
            hidden=hidden,
            rank=rank,
            modules=MODULES,
        )

        candidate = copy.deepcopy(dense_model)
        candidate_core = candidate.core
        assert isinstance(candidate_core, HighPrecisionFixedRoutingCore)
        up_reconstructed = up_fit["reconstructed"]
        down_reconstructed = down_fit["reconstructed"]
        assert isinstance(up_reconstructed, torch.Tensor)
        assert isinstance(down_reconstructed, torch.Tensor)

        for module_index, module in enumerate(candidate_core.module_set):
            module.up.weight.copy_(
                up_reconstructed[module_index].to(
                    device=module.up.weight.device,
                    dtype=module.up.weight.dtype,
                )
            )
            module.down.weight.copy_(
                down_reconstructed[module_index].to(
                    device=module.down.weight.device,
                    dtype=module.down.weight.dtype,
                )
            )

        metrics = evaluator(candidate, validation)
        score = float(metrics[score_name])
        records.append(
            {
                "rank": rank,
                **storage,
                "score_name": score_name,
                "dense_score": dense_score,
                "shared_basis_score": score,
                "score_delta": score - dense_score,
                "up_reconstruction_mse": float(up_fit["mse"]),
                "up_reconstruction_rmse": float(up_fit["rmse"]),
                "up_reconstruction_max_abs": float(up_fit["max_abs"]),
                "down_reconstruction_mse": float(down_fit["mse"]),
                "down_reconstruction_rmse": float(down_fit["rmse"]),
                "down_reconstruction_max_abs": float(down_fit["max_abs"]),
            }
        )
        print(
            f"[C59] rank={rank} checked ({index}/{total}) "
            f"storage_ratio={storage['representation_weight_ratio']:.6f} "
            f"score={score:.6f}",
            flush=True,
        )

    rank32 = next(record for record in records if int(record["rank"]) == 32)
    if float(rank32["up_reconstruction_max_abs"]) > 2e-5:
        raise RuntimeError("C59 rank32 Up sanity check did not reconstruct closely")
    if float(rank32["down_reconstruction_max_abs"]) > 2e-5:
        raise RuntimeError("C59 rank32 Down sanity check did not reconstruct closely")
    if abs(float(rank32["shared_basis_score"]) - dense_score) > 1e-7:
        raise RuntimeError("C59 rank32 sanity check changed task score")

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C59")

    sub_dense = [record for record in records if bool(record["below_dense_weight_bytes"])]
    preserving = [
        record for record in sub_dense
        if abs(float(record["shared_basis_score"]) - dense_score) <= 1e-7
    ]
    best_preserving_rank = (
        min(int(record["rank"]) for record in preserving) if preserving else None
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "real composition fixture shared-basis post-hoc representation/quality frontier",
        "task": fixture["task"],
        "fixture_seed": int(fixture["seed"]),
        "score_name": score_name,
        "dense_score": dense_score,
        "fixture_recorded_scores": fixture_scores,
        "width": width,
        "hidden_width": hidden,
        "module_count": MODULES,
        "ranks": list(RANKS),
        "matched_runtime_rank_from_C58": 2,
        "max_rank_below_dense_weight_storage": max(
            int(record["rank"]) for record in sub_dense
        ),
        "best_sub_dense_rank_preserving_dense_score": best_preserving_rank,
        "records": records,
        "fixture_sha256": fixture_hash,
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C59 uses post-hoc truncated-SVD fitting, not task-aware shared-basis training",
            "only the trusted composition runtime fixture is evaluated",
            "C59 tests representation capacity/quality, not factorized runtime",
            "a failed low rank may still recover under task-aware joint training",
            "C59 alone cannot establish Gate C pass",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        fixture_path=args.fixture,
        protected_result_path=args.protected_result,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C59 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
