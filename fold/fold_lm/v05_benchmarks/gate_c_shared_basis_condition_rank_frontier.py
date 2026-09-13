"""C63: condition-task sub-dense rank frontier after the C62 rank-1 failure.

C62 showed that width-16 condition recovery at rank 1 improved strongly but did
not match its dense reference on any of three seeds.  C63 keeps the same model,
training schedule, factor learning rate, and frozen non-factor parameters, and
varies only the shared-basis rank across all sub-dense values selected here:
1, 2, 4, 6, 7.

Validation is recorded before tuning and at 25/50/75/100% of recovery to show
whether a rank ever reaches the dense reference before the final checkpoint.
Checkpoint maxima are diagnostic only, not a production selection protocol.
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
from torch.nn import functional as F

from fold_lm.v05.condition_task import evaluate_condition
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05.benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS, _build_condition
from fold_lm.v05.benchmarks.gate_c_shared_basis_task_aware_recovery import (
    TaskTunableSharedBasisCore,
    _freeze_except_factors,
    _score,
    _storage,
)

EXPERIMENT_ID = "C63-shared-basis-condition-rank-frontier"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
RANKS = (1, 2, 4, 6, 7)
DENSE_STEPS = 260
DENSE_LR = 0.01
FACTOR_STEPS = 260
FACTOR_LR = 0.002
BATCH_SIZE = 32
MARKS = (65, 130, 195, 260)
TOL = 1e-7


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _loss(model, train, indices, device):
    initial_values = train.initial_values[indices].to(device)
    operations = train.operations[indices].to(device)
    candidates = train.candidates[indices].to(device)
    targets = train.targets[indices].to(device)
    logits = model(initial_values, operations, candidates)
    return F.cross_entropy(logits.flatten(0, 1), targets.flatten())


def _train_dense(seed: int, device: torch.device):
    config, model, train, validation = _build_condition(seed, "v5b", device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=DENSE_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    for step in range(1, DENSE_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _loss(model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C63 seed={seed} dense loss non-finite")
        loss.backward()
        optimizer.step()
        if step in MARKS:
            print(
                f"[C63] seed={seed} dense step={step}/{DENSE_STEPS} "
                f"loss={float(loss.detach().item()):.8f}",
                flush=True,
            )
    score = float(evaluate_condition(model, validation)["trajectory_exact_accuracy"])
    return config, model, train, validation, score


def _recover(seed, rank, dense_model, train, validation, dense_score, device):
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C63 dense core type mismatch")
    width = int(dense_model.core.config.width)
    hidden = width * int(dense_model.core.config.hidden_mult)
    storage = _storage(width=width, hidden=hidden, rank=rank)
    if not bool(storage["below_dense_weight_bytes"]):
        raise RuntimeError(f"C63 rank={rank} is not sub-dense")

    candidate = copy.deepcopy(dense_model)
    core = TaskTunableSharedBasisCore(dense_model.core, rank).to(device)
    candidate.core = core
    candidate = candidate.to(device)
    _freeze_except_factors(candidate, core)

    pre_score = _score(
        candidate, evaluate_condition, validation, "trajectory_exact_accuracy"
    )
    checkpoints = [{"step": 0, "validation_score": pre_score}]
    optimizer = torch.optim.AdamW(core.factor_parameters(), lr=FACTOR_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    candidate.train()
    final_loss = None

    for step in range(1, FACTOR_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _loss(candidate, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C63 seed={seed} rank={rank} factor loss non-finite")
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in MARKS:
            score = _score(
                candidate, evaluate_condition, validation, "trajectory_exact_accuracy"
            )
            checkpoints.append({"step": step, "validation_score": score})
            print(
                f"[C63] seed={seed} rank={rank} step={step}/{FACTOR_STEPS} "
                f"loss={final_loss:.8f} val={score:.6f}",
                flush=True,
            )

    final_score = float(checkpoints[-1]["validation_score"])
    best = max(
        checkpoints,
        key=lambda item: (float(item["validation_score"]), -int(item["step"])),
    )
    best_score = float(best["validation_score"])
    return {
        "seed": seed,
        "rank": rank,
        **storage,
        "dense_score": dense_score,
        "pre_score": pre_score,
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


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c62_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C63 requires CUDA")
    c62 = json.loads(c62_summary_path.read_text(encoding="utf-8"))
    if c62.get("experiment_id") != "C62-shared-basis-cross-task-multiseed":
        raise RuntimeError("C63 requires C62 summary")
    if c62.get("status") != "PASS":
        raise RuntimeError("C62 summary is not PASS")
    if bool(c62.get("summary", {}).get("tasks", {}).get("condition", {}).get("all_post_scores_match_dense", True)):
        raise RuntimeError("C63 requires the observed C62 condition failure")

    expected_dense = {
        int(row["seed"]): float(row["dense_score"])
        for row in c62.get("records", [])
        if row.get("task") == "condition"
    }
    if set(expected_dense) != set(SEEDS):
        raise RuntimeError("C62 condition dense references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records = []

    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C63] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        _config, dense_model, train, validation, dense_score = _train_dense(seed, device)
        if abs(dense_score - expected_dense[seed]) > TOL:
            raise RuntimeError(
                f"C63 seed={seed} dense score changed: {dense_score} vs {expected_dense[seed]}"
            )
        for rank_index, rank in enumerate(RANKS, start=1):
            record = _recover(
                seed, rank, dense_model, train, validation, dense_score, device
            )
            records.append(record)
            print(
                f"[C63] seed={seed} rank={rank} done ({rank_index}/{len(RANKS)}) "
                f"final={record['final_score']:.6f} best={record['best_checkpoint_score']:.6f} "
                f"storage={record['representation_weight_ratio']:.6f}",
                flush=True,
            )
        del dense_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C63")

    rank_summary = {}
    for rank in RANKS:
        rows = [row for row in records if int(row["rank"]) == rank]
        rank_summary[str(rank)] = {
            "storage_ratio": float(rows[0]["representation_weight_ratio"]),
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

    min_final = next(
        (rank for rank in RANKS if rank_summary[str(rank)]["all_final_meet_dense"]),
        None,
    )
    min_best = next(
        (
            rank
            for rank in RANKS
            if rank_summary[str(rank)]["all_best_checkpoints_meet_dense"]
        ),
        None,
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "condition-task sub-dense shared-basis rank/checkpoint frontier",
        "seeds": list(SEEDS),
        "ranks": list(RANKS),
        "dense_steps": DENSE_STEPS,
        "factor_steps": FACTOR_STEPS,
        "factor_learning_rate": FACTOR_LR,
        "records": records,
        "summary": {
            "ranks": rank_summary,
            "minimum_rank_all_final_meet_dense": min_final,
            "minimum_rank_all_best_checkpoints_meet_dense": min_best,
        },
        "C62_summary_sha256": _sha256(c62_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C63 diagnoses condition only; language checkpoint behavior is deferred to C64",
            "validation checkpoint maxima are diagnostic only",
            "all tested ranks remain below dense routed-weight bytes",
            "C63 alone cannot establish Gate C pass",
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
    parser.add_argument("--c62-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c62_summary_path=args.c62_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C63 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
