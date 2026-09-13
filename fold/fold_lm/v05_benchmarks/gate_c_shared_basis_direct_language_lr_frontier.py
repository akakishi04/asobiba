"""C66: direct-joint language factor learning-rate/checkpoint frontier.

C65 showed that direct-from-initialization joint training is robust for
composition, nearly robust for condition, but unstable for the language smoke
benchmark at rank 4.  C65 used the original language learning rate (0.01) for
all ordinary/shared parameters while the shared-basis factors used 0.002.
That 5x learning-rate mismatch did not exist in the earlier post-hoc recovery
setting and may cause the shared representation to move faster than the factors
can co-adapt.

C66 changes exactly one design axis: factor learning rate.  Language stays at
rank 4, common/non-factor parameters stay at lr=0.01, initialization and batch
schedule stay identical to C65, and factor lr is swept across 0.002, 0.005,
0.01.  Validation accuracy is recorded every 50 steps to separate final-step
instability from inability to learn.

This is a bounded optimizer/co-adaptation diagnostic, not a production training
policy and not a Gate-C pass test.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS, _build_language
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _task_loss,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C66-shared-basis-direct-language-factor-lr-frontier"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
RANK = 4
DENSE_STEPS = 600
COMMON_LR = 0.01
FACTOR_LRS = (0.002, 0.005, 0.01)
BATCH_SIZE = 24
CHECKPOINT_INTERVAL = 50
TOL = 1e-7


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _train_dense(seed: int, initial_model, train, validation, device: torch.device):
    model = copy.deepcopy(initial_model).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=COMMON_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    final_loss = None
    for step in range(1, DENSE_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss("language", model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C66 seed={seed} dense loss non-finite")
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step % 150 == 0:
            print(
                f"[C66] seed={seed} dense step={step}/{DENSE_STEPS} "
                f"loss={final_loss:.8f}",
                flush=True,
            )
    score = float(evaluate_language(model, validation)["accuracy"])
    return score, float(final_loss)


def _train_factorized(
    *,
    seed: int,
    factor_lr: float,
    initial_model,
    train,
    validation,
    dense_score: float,
    device: torch.device,
) -> dict:
    model = copy.deepcopy(initial_model).to(device)
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C66 initial core must be HighPrecisionFixedRoutingCore")
    model.core = JointTrainSharedBasisCore(model.core, RANK).to(device)
    model = model.to(device)

    factor_params = list(model.core.factor_parameters())
    factor_ids = {id(parameter) for parameter in factor_params}
    common_params = [
        parameter
        for parameter in model.parameters()
        if parameter.requires_grad and id(parameter) not in factor_ids
    ]
    optimizer = torch.optim.AdamW(
        [
            {"params": common_params, "lr": COMMON_LR},
            {"params": factor_params, "lr": float(factor_lr)},
        ],
        weight_decay=0.0,
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)

    initial_score = float(evaluate_language(model, validation)["accuracy"])
    checkpoints = [
        {
            "step": 0,
            "validation_score": initial_score,
            "training_loss": None,
        }
    ]
    model.train()
    final_loss = None
    for step in range(1, DENSE_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss("language", model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C66 seed={seed} factor_lr={factor_lr} produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step % CHECKPOINT_INTERVAL == 0:
            score = float(evaluate_language(model, validation)["accuracy"])
            checkpoints.append(
                {
                    "step": step,
                    "validation_score": score,
                    "training_loss": final_loss,
                }
            )
            print(
                f"[C66] seed={seed} factor_lr={factor_lr:.3f} "
                f"step={step}/{DENSE_STEPS} loss={final_loss:.8f} val={score:.6f}",
                flush=True,
            )

    final_score = float(checkpoints[-1]["validation_score"])
    best = max(
        checkpoints,
        key=lambda row: (float(row["validation_score"]), -int(row["step"])),
    )
    best_score = float(best["validation_score"])
    return {
        "seed": seed,
        "factor_learning_rate": float(factor_lr),
        "dense_score": dense_score,
        "initial_score": initial_score,
        "final_score": final_score,
        "best_checkpoint_score": best_score,
        "best_checkpoint_step": int(best["step"]),
        "final_delta": final_score - dense_score,
        "best_delta": best_score - dense_score,
        "final_meets_or_exceeds_dense": final_score + TOL >= dense_score,
        "best_checkpoint_meets_or_exceeds_dense": best_score + TOL >= dense_score,
        "factor_final_training_loss": float(final_loss),
        "checkpoints": checkpoints,
    }


def run(*, protected_result_path: Path, c65_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C66 requires CUDA")

    c65 = json.loads(c65_summary_path.read_text(encoding="utf-8"))
    if c65.get("experiment_id") != "C65-shared-basis-direct-joint-training":
        raise RuntimeError("C66 requires accepted C65 summary")
    if c65.get("status") != "PASS":
        raise RuntimeError("C65 summary is not PASS")
    language = c65.get("summary", {}).get("tasks", {}).get("language", {})
    if bool(language.get("all_direct_match_or_exceed_dense", True)):
        raise RuntimeError("C66 requires the observed C65 direct language failure")

    accepted_dense = {
        int(row["seed"]): float(row["dense_score"])
        for row in c65.get("records", [])
        if row.get("task") == "language"
    }
    accepted_lr002 = {
        int(row["seed"]): float(row["direct_score"])
        for row in c65.get("records", [])
        if row.get("task") == "language"
    }
    if set(accepted_dense) != set(SEEDS) or set(accepted_lr002) != set(SEEDS):
        raise RuntimeError("C65 language references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records: list[dict] = []

    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C66] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        _config, initial_model, train, validation = _build_language(seed, "v5b", device)
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C66 initial core must be HighPrecisionFixedRoutingCore")

        dense_score, dense_final_loss = _train_dense(
            seed, initial_model, train, validation, device
        )
        if abs(dense_score - accepted_dense[seed]) > TOL:
            raise RuntimeError(
                f"C66 seed={seed} dense score changed: {dense_score} vs {accepted_dense[seed]}"
            )

        for lr_index, factor_lr in enumerate(FACTOR_LRS, start=1):
            row = _train_factorized(
                seed=seed,
                factor_lr=factor_lr,
                initial_model=initial_model,
                train=train,
                validation=validation,
                dense_score=dense_score,
                device=device,
            )
            row["dense_final_training_loss"] = dense_final_loss
            records.append(row)
            if abs(factor_lr - 0.002) <= 1e-12:
                if abs(float(row["final_score"]) - accepted_lr002[seed]) > TOL:
                    raise RuntimeError(
                        f"C66 seed={seed} lr=0.002 failed to reproduce C65 final score: "
                        f"{row['final_score']} vs {accepted_lr002[seed]}"
                    )
            print(
                f"[C66] seed={seed} factor_lr={factor_lr:.3f} done "
                f"({lr_index}/{len(FACTOR_LRS)}) final={row['final_score']:.6f} "
                f"best={row['best_checkpoint_score']:.6f} "
                f"best_step={row['best_checkpoint_step']}",
                flush=True,
            )
        del initial_model
        torch.cuda.empty_cache()

    width = 32
    hidden = 64
    storage = _storage(width=width, hidden=hidden, rank=RANK)
    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C66")

    lr_summary: dict[str, dict] = {}
    for factor_lr in FACTOR_LRS:
        rows = [
            row
            for row in records
            if abs(float(row["factor_learning_rate"]) - factor_lr) <= 1e-12
        ]
        lr_summary[f"{factor_lr:.3f}"] = {
            "final_score": _stats([float(row["final_score"]) for row in rows]),
            "best_checkpoint_score": _stats(
                [float(row["best_checkpoint_score"]) for row in rows]
            ),
            "all_final_meet_dense": all(
                bool(row["final_meets_or_exceeds_dense"]) for row in rows
            ),
            "all_best_checkpoints_meet_dense": all(
                bool(row["best_checkpoint_meets_or_exceeds_dense"]) for row in rows
            ),
        }

    first_final_lr = next(
        (
            factor_lr
            for factor_lr in FACTOR_LRS
            if bool(lr_summary[f"{factor_lr:.3f}"]["all_final_meet_dense"])
        ),
        None,
    )
    first_best_lr = next(
        (
            factor_lr
            for factor_lr in FACTOR_LRS
            if bool(
                lr_summary[f"{factor_lr:.3f}"]["all_best_checkpoints_meet_dense"]
            )
        ),
        None,
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "direct-joint language factor learning-rate/checkpoint frontier",
        "seeds": list(SEEDS),
        "rank": RANK,
        "representation_weight_ratio": float(storage["representation_weight_ratio"]),
        "common_learning_rate": COMMON_LR,
        "factor_learning_rates": list(FACTOR_LRS),
        "steps": DENSE_STEPS,
        "checkpoint_interval": CHECKPOINT_INTERVAL,
        "records": records,
        "summary": {
            "factor_learning_rates": lr_summary,
            "minimum_tested_factor_lr_all_final_meet_dense": first_final_lr,
            "minimum_tested_factor_lr_all_best_checkpoints_meet_dense": first_best_lr,
        },
        "C65_summary_sha256": _sha256(c65_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "direct_joint_language_factor_lr_sweep",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C66 diagnoses the existing small language smoke task only",
            "only factor learning rate changes; common lr remains 0.01",
            "validation checkpoint maxima are diagnostic, not a production early-stop rule",
            "C66 does not test independent factor initialization or production runtime",
            "C66 alone cannot establish Gate C pass",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c65-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c65_summary_path=args.c65_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C66 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
