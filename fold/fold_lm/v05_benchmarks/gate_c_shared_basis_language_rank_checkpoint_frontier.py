"""C64: language shared-basis rank/checkpoint frontier after C62.

C62 found one language seed where rank-2 SVD initialization scored 0.909091 and
600 steps of task-aware factor tuning ended lower at 0.818182 even while training
loss decreased. Two other seeds already matched dense at rank 2. C64 separates
rank capacity from checkpoint/optimization behavior.

For each of the three accepted language seeds:

1. reproduce the dense Gate-B language model and verify its accepted C62 score;
2. test shared-basis ranks 2, 4, and 8 (all sub-dense routed-weight storage);
3. freeze every non-factor parameter;
4. tune factors for the same 600 steps at lr 0.002;
5. record validation accuracy every 50 steps, including step 0.

Primary questions:
- does rank 2 ever meet the dense reference even if the final checkpoint does not?
- if not, what is the minimum tested sub-dense rank whose final or best checkpoint
  meets the dense reference for all three seeds?

Checkpoint maxima are diagnostic only and do not define a production early-stop
policy. C64 does not modify production runtime.
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

from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS, _build_language
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import (
    TaskTunableSharedBasisCore,
    _freeze_except_factors,
    _score,
    _storage,
)

EXPERIMENT_ID = "C64-shared-basis-language-rank-checkpoint-frontier"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
RANKS = (2, 4, 8)
DENSE_STEPS = 600
DENSE_LR = 0.01
FACTOR_STEPS = 600
FACTOR_LR = 0.002
BATCH_SIZE = 24
CHECKPOINT_INTERVAL = 50
TOL = 1e-7


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _loss(model, train, indices, device):
    tokens = train.tokens[indices].to(device)
    tasks = train.tasks[indices].to(device)
    targets = train.targets[indices].to(device)
    logits = model(tokens, tasks)
    return F.cross_entropy(logits, targets)


def _train_dense(seed: int, device: torch.device):
    config, model, train, validation = _build_language(seed, "v5b", device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=DENSE_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    for step in range(1, DENSE_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _loss(model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C64 seed={seed} dense loss non-finite")
        loss.backward()
        optimizer.step()
        if step % 150 == 0:
            print(
                f"[C64] seed={seed} dense step={step}/{DENSE_STEPS} "
                f"loss={float(loss.detach().item()):.8f}",
                flush=True,
            )
    score = float(evaluate_language(model, validation)["accuracy"])
    return config, model, train, validation, score


def _recover(seed, rank, dense_model, train, validation, dense_score, device):
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C64 dense core type mismatch")
    width = int(dense_model.core.config.width)
    hidden = width * int(dense_model.core.config.hidden_mult)
    storage = _storage(width=width, hidden=hidden, rank=rank)
    if not bool(storage["below_dense_weight_bytes"]):
        raise RuntimeError(f"C64 rank={rank} is not sub-dense")

    candidate = copy.deepcopy(dense_model)
    core = TaskTunableSharedBasisCore(dense_model.core, rank).to(device)
    candidate.core = core
    candidate = candidate.to(device)
    _freeze_except_factors(candidate, core)

    pre_score = _score(candidate, evaluate_language, validation, "accuracy")
    checkpoints = [{"step": 0, "validation_score": pre_score, "training_loss": None}]
    optimizer = torch.optim.AdamW(core.factor_parameters(), lr=FACTOR_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    candidate.train()
    final_loss = None

    for step in range(1, FACTOR_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _loss(candidate, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C64 seed={seed} rank={rank} factor loss non-finite")
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())

        if step % CHECKPOINT_INTERVAL == 0:
            score = _score(candidate, evaluate_language, validation, "accuracy")
            checkpoints.append(
                {
                    "step": step,
                    "validation_score": score,
                    "training_loss": final_loss,
                }
            )
            print(
                f"[C64] seed={seed} rank={rank} step={step}/{FACTOR_STEPS} "
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
        raise RuntimeError("C64 requires CUDA")
    c62 = json.loads(c62_summary_path.read_text(encoding="utf-8"))
    if c62.get("experiment_id") != "C62-shared-basis-cross-task-multiseed":
        raise RuntimeError("C64 requires C62 summary")
    if c62.get("status") != "PASS":
        raise RuntimeError("C62 summary is not PASS")
    language_summary = c62.get("summary", {}).get("tasks", {}).get("language", {})
    if bool(language_summary.get("all_post_scores_match_dense", True)):
        raise RuntimeError("C64 requires the observed C62 language failure")

    expected_dense = {
        int(row["seed"]): float(row["dense_score"])
        for row in c62.get("records", [])
        if row.get("task") == "language"
    }
    if set(expected_dense) != set(SEEDS):
        raise RuntimeError("C62 language dense references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records = []

    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C64] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        _config, dense_model, train, validation, dense_score = _train_dense(seed, device)
        if abs(dense_score - expected_dense[seed]) > TOL:
            raise RuntimeError(
                f"C64 seed={seed} dense score changed: {dense_score} vs {expected_dense[seed]}"
            )
        for rank_index, rank in enumerate(RANKS, start=1):
            record = _recover(
                seed, rank, dense_model, train, validation, dense_score, device
            )
            records.append(record)
            print(
                f"[C64] seed={seed} rank={rank} done ({rank_index}/{len(RANKS)}) "
                f"final={record['final_score']:.6f} best={record['best_checkpoint_score']:.6f} "
                f"best_step={record['best_checkpoint_step']} "
                f"storage={record['representation_weight_ratio']:.6f}",
                flush=True,
            )
        del dense_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C64")

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
    failing_seed_rank2 = next(
        row
        for row in records
        if int(row["seed"]) == 20260911 and int(row["rank"]) == 2
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "language-task sub-dense shared-basis rank/checkpoint frontier",
        "seeds": list(SEEDS),
        "ranks": list(RANKS),
        "dense_steps": DENSE_STEPS,
        "factor_steps": FACTOR_STEPS,
        "factor_learning_rate": FACTOR_LR,
        "checkpoint_interval": CHECKPOINT_INTERVAL,
        "records": records,
        "summary": {
            "ranks": rank_summary,
            "minimum_rank_all_final_meet_dense": min_final,
            "minimum_rank_all_best_checkpoints_meet_dense": min_best,
            "seed_20260911_rank2_best_score": float(
                failing_seed_rank2["best_checkpoint_score"]
            ),
            "seed_20260911_rank2_best_step": int(
                failing_seed_rank2["best_checkpoint_step"]
            ),
            "seed_20260911_rank2_final_score": float(failing_seed_rank2["final_score"]),
        },
        "C62_summary_sha256": _sha256(c62_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C64 diagnoses the existing small language smoke task only",
            "validation checkpoint maxima are diagnostic only and are not a production early-stop policy",
            "ranks 2/4/8 are a bounded sub-dense capacity probe rather than an exhaustive rank search",
            "C64 alone cannot establish Gate C pass",
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
    print("\n=== C64 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
