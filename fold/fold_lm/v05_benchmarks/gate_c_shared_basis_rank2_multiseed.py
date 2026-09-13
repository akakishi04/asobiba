"""C61: multi-seed robustness for rank-2 task-aware shared-basis recovery.

C60 showed that the trusted composition fixture can recover dense task quality at
rank 2 while routed Up/Down weight storage remains 57.03125% of two independent
dense routed weights. C61 asks whether that result reproduces across independent
training seeds rather than only the frozen runtime fixture seed.

For each seed:

1. train the high-precision V5-B composition model from scratch using the exact
   Gate-B composition schedule;
2. replace only routed Up/Down weights with the rank-2 shared-basis family,
   initialized by the same post-hoc SVD used by C59/C60;
3. freeze every non-factor parameter;
4. tune only shared-basis factors for 300 task-aware steps;
5. compare pre/post validation trajectory accuracy with the independently trained
   dense reference.

This is a robustness/quality diagnostic. It does not modify production runtime.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.composition_task import evaluate_composition
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import (
    DEFAULT_SEEDS,
    _build_composition,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import (
    TaskTunableSharedBasisCore,
    _freeze_except_factors,
    _score,
    _storage,
)


EXPERIMENT_ID = "C61-shared-basis-rank2-multiseed"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
RANK = 2
MODULES = 2
DENSE_STEPS = 300
DENSE_LR = 0.005
FACTOR_STEPS = 300
FACTOR_LR = 0.002
BATCH_SIZE = 64
PROGRESS_MARKS = (75, 150, 225, 300)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _train_dense(seed: int, device: torch.device):
    config, model, train, validation = _build_composition(seed, "v5b", device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=DENSE_LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    initial_loss = None
    final_loss = None
    for step in range(1, DENSE_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(
            config.state_scale
        )
        optimizer.zero_grad(set_to_none=True)
        predicted = model(initial_values, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C61 seed={seed} dense training produced non-finite loss")
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in PROGRESS_MARKS:
            print(
                f"[C61] seed={seed} dense step={step}/{DENSE_STEPS} "
                f"loss={loss_value:.8f}",
                flush=True,
            )
    return model, train, validation, float(initial_loss), float(final_loss)


def _tune_rank2(
    *,
    seed: int,
    dense_model,
    train,
    validation,
    device: torch.device,
) -> dict:
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("C61 dense core must remain HighPrecisionFixedRoutingCore")
    if dense_model.core.config.modules != MODULES:
        raise RuntimeError("C61 expects exactly two routed modules")

    dense_score = float(evaluate_composition(dense_model, validation)["trajectory_exact_accuracy"])
    candidate = copy.deepcopy(dense_model)
    tunable_core = TaskTunableSharedBasisCore(dense_model.core, RANK).to(device)
    candidate.core = tunable_core
    candidate = candidate.to(device)
    _freeze_except_factors(candidate, tunable_core)

    pre_score = _score(
        candidate,
        evaluate_composition,
        validation,
        "trajectory_exact_accuracy",
    )
    optimizer = torch.optim.AdamW(
        tunable_core.factor_parameters(),
        lr=FACTOR_LR,
        weight_decay=0.0,
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    candidate.train()
    initial_loss = None
    final_loss = None
    for step in range(1, FACTOR_STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(candidate.parameters()).dtype) / float(
            candidate.config.state_scale
        )
        optimizer.zero_grad(set_to_none=True)
        predicted = candidate(initial_values, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C61 seed={seed} factor tuning produced non-finite loss")
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in PROGRESS_MARKS:
            print(
                f"[C61] seed={seed} rank2 step={step}/{FACTOR_STEPS} "
                f"loss={loss_value:.8f}",
                flush=True,
            )

    post_score = _score(
        candidate,
        evaluate_composition,
        validation,
        "trajectory_exact_accuracy",
    )
    width = int(dense_model.core.config.width)
    hidden = width * int(dense_model.core.config.hidden_mult)
    storage = _storage(width=width, hidden=hidden, rank=RANK)
    return {
        "seed": seed,
        "rank": RANK,
        **storage,
        "dense_score": dense_score,
        "pre_task_tuning_score": pre_score,
        "post_task_tuning_score": post_score,
        "pre_delta": pre_score - dense_score,
        "post_delta": post_score - dense_score,
        "recovered_score": post_score - pre_score,
        "factor_initial_training_loss": float(initial_loss),
        "factor_final_training_loss": float(final_loss),
        "factor_steps": FACTOR_STEPS,
        "factor_learning_rate": FACTOR_LR,
    }


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(
    *,
    protected_result_path: Path,
    c60_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C61 requires CUDA")
    c60 = json.loads(c60_summary_path.read_text(encoding="utf-8"))
    if c60.get("experiment_id") != "C60-shared-basis-task-aware-recovery":
        raise RuntimeError("C61 requires accepted C60 summary")
    if c60.get("status") != "PASS":
        raise RuntimeError("C60 summary is not PASS")
    rank2 = next((row for row in c60.get("records", []) if int(row.get("rank", -1)) == 2), None)
    if rank2 is None or abs(float(rank2.get("post_task_tuning_score", -1.0)) - 1.0) > 1e-7:
        raise RuntimeError("C61 requires C60 rank2 full recovery")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)

    records: list[dict] = []
    for index, seed in enumerate(SEEDS, start=1):
        print(f"[C61] seed={seed} start ({index}/{len(SEEDS)})", flush=True)
        dense_model, train, validation, dense_initial_loss, dense_final_loss = _train_dense(seed, device)
        result = _tune_rank2(
            seed=seed,
            dense_model=dense_model,
            train=train,
            validation=validation,
            device=device,
        )
        result["dense_initial_training_loss"] = dense_initial_loss
        result["dense_final_training_loss"] = dense_final_loss
        records.append(result)
        print(
            f"[C61] seed={seed} done ({index}/{len(SEEDS)}) "
            f"dense={result['dense_score']:.6f} "
            f"pre={result['pre_task_tuning_score']:.6f} "
            f"post={result['post_task_tuning_score']:.6f} "
            f"storage={result['representation_weight_ratio']:.6f}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C61")

    dense_scores = [float(row["dense_score"]) for row in records]
    pre_scores = [float(row["pre_task_tuning_score"]) for row in records]
    post_scores = [float(row["post_task_tuning_score"]) for row in records]
    post_deltas = [float(row["post_delta"]) for row in records]
    ratios = [float(row["representation_weight_ratio"]) for row in records]
    all_match_dense = all(abs(delta) <= 1e-7 for delta in post_deltas)
    all_dense_perfect = all(abs(score - 1.0) <= 1e-7 for score in dense_scores)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "rank-2 shared-basis task-aware recovery robustness across independent dense training seeds",
        "task": "composition",
        "seeds": list(SEEDS),
        "rank": RANK,
        "dense_steps": DENSE_STEPS,
        "dense_learning_rate": DENSE_LR,
        "factor_steps": FACTOR_STEPS,
        "factor_learning_rate": FACTOR_LR,
        "batch_size": BATCH_SIZE,
        "records": records,
        "summary": {
            "dense_score": _stats(dense_scores),
            "pre_task_tuning_score": _stats(pre_scores),
            "post_task_tuning_score": _stats(post_scores),
            "post_delta": _stats(post_deltas),
            "representation_weight_ratio": _stats(ratios),
            "all_dense_scores_one": all_dense_perfect,
            "all_rank2_post_scores_match_dense": all_match_dense,
        },
        "C60_summary_sha256": _sha256(c60_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "independent_dense_then_rank2_factor_recovery",
        "non_factor_parameters_frozen_during_recovery": True,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C61 covers composition only",
            "three deterministic training seeds are a robustness check, not broad task generalization",
            "factor recovery uses 300 bounded task-aware steps per seed",
            "C61 does not measure factorized inference runtime; C58 covers runtime scaling",
            "C61 alone cannot establish Gate C pass",
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
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c60-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c60_summary_path=args.c60_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C61 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
