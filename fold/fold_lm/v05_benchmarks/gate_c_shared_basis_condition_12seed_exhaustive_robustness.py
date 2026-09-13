"""C69: 12-seed exhaustive robustness for native shared-basis condition training.

C68 exhaustively evaluated the entire held-out condition domain for the three
accepted seeds.  Rank-4 aligned-lr shared-basis training was better than dense
on two seeds and worse on one; the pooled paired count favored the direct model
by 87 trajectories.  This mixed sign means the remaining question is seed
robustness, not yet a reason to increase rank.

C69 changes only the number of deterministic seeds.  It keeps the exact C68
condition training/evaluation setup (rank 4, lr 0.01, 260 steps, batch 32) and
runs seeds 20260911 through 20260922.  The first three seeds must reproduce the
accepted C68 exhaustive results exactly within tolerance.

This experiment reports the distribution of dense-vs-direct exhaustive deltas
and pooled paired wins.  It does not define an equivalence margin, change the
representation, or establish Gate C passage.
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

from fold_lm.v05.condition_task import evaluate_condition
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_condition
from fold_lm.v05_benchmarks.gate_c_shared_basis_condition_exhaustive_generalization import (
    _evaluate_batched,
    _exhaustive_complement,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _task_loss,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C69-shared-basis-condition-12seed-exhaustive-robustness"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(range(20260911, 20260923))
RANK = 4
STEPS = 260
LR = 0.01
BATCH_SIZE = 32
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


def _train(model, train, seed: int, device: torch.device, phase: str) -> float:
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    final_loss = None
    for step in range(1, STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss("condition", model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C69 seed={seed} phase={phase} produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in (65, 130, 195, 260):
            print(
                f"[C69] seed={seed} {phase} step={step}/{STEPS} "
                f"loss={final_loss:.8f}",
                flush=True,
            )
    return float(final_loss)


def _two_sided_sign_pvalue(direct_wins: int, dense_wins: int) -> float:
    n = direct_wins + dense_wins
    if n == 0:
        return 1.0
    k = min(direct_wins, dense_wins)
    lower = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * lower)


def run(*, protected_result_path: Path, c68_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C69 requires CUDA")

    c68 = json.loads(c68_summary_path.read_text(encoding="utf-8"))
    if c68.get("experiment_id") != "C68-shared-basis-condition-exhaustive-generalization":
        raise RuntimeError("C69 requires accepted C68 summary")
    if c68.get("status") != "PASS":
        raise RuntimeError("C68 summary is not PASS")
    if int(c68.get("rank", -1)) != RANK or abs(float(c68.get("learning_rate", -1.0)) - LR) > TOL:
        raise RuntimeError("C69 requires the accepted C68 rank/lr setup")

    accepted_rows = {int(row["seed"]): row for row in c68.get("records", [])}
    accepted_seeds = {20260911, 20260912, 20260913}
    if set(accepted_rows) != accepted_seeds:
        raise RuntimeError("C68 accepted seed references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C69] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        config, initial_model, train, validation = _build_condition(seed, "v5b", device)
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C69 initial core must be HighPrecisionFixedRoutingCore")

        dense_model = copy.deepcopy(initial_model).to(device)
        direct_model = copy.deepcopy(initial_model).to(device)
        direct_model.core = JointTrainSharedBasisCore(initial_model.core, RANK).to(device)
        direct_model = direct_model.to(device)

        dense_final_loss = _train(dense_model, train, seed, device, "dense")
        direct_final_loss = _train(direct_model, train, seed, device, "aligned_factor")

        dense_validation = evaluate_condition(dense_model, validation)
        direct_validation = evaluate_condition(direct_model, validation)
        exhaustive = _exhaustive_complement(config, train)
        dense_full, dense_exact = _evaluate_batched(dense_model, exhaustive)
        direct_full, direct_exact = _evaluate_batched(direct_model, exhaustive)

        dense_only = int((dense_exact & ~direct_exact).sum().item())
        direct_only = int((direct_exact & ~dense_exact).sum().item())
        both_wrong = int((~dense_exact & ~direct_exact).sum().item())
        both_correct = int((dense_exact & direct_exact).sum().item())
        delta = (
            float(direct_full["trajectory_exact_accuracy"])
            - float(dense_full["trajectory_exact_accuracy"])
        )
        storage = _storage(
            width=int(initial_model.core.config.width),
            hidden=int(initial_model.core.config.width * initial_model.core.config.hidden_mult),
            rank=RANK,
        )

        record = {
            "seed": seed,
            "rank": RANK,
            **storage,
            "validation_examples": validation.size,
            "dense_validation_score": float(dense_validation["trajectory_exact_accuracy"]),
            "direct_validation_score": float(direct_validation["trajectory_exact_accuracy"]),
            "exhaustive_examples": exhaustive.size,
            "dense_exhaustive": dense_full,
            "direct_exhaustive": direct_full,
            "exhaustive_exact_delta": delta,
            "paired_dense_only_correct": dense_only,
            "paired_direct_only_correct": direct_only,
            "paired_both_wrong": both_wrong,
            "paired_both_correct": both_correct,
            "paired_net_direct_advantage": direct_only - dense_only,
            "dense_final_training_loss": dense_final_loss,
            "direct_final_training_loss": direct_final_loss,
        }

        if seed in accepted_rows:
            accepted = accepted_rows[seed]
            checks = (
                ("dense_validation_score", record["dense_validation_score"], accepted["dense_validation_score"]),
                ("direct_validation_score", record["direct_validation_score"], accepted["direct_validation_score"]),
                ("dense_exhaustive", record["dense_exhaustive"]["trajectory_exact_accuracy"], accepted["dense_exhaustive"]["trajectory_exact_accuracy"]),
                ("direct_exhaustive", record["direct_exhaustive"]["trajectory_exact_accuracy"], accepted["direct_exhaustive"]["trajectory_exact_accuracy"]),
                ("exhaustive_exact_delta", record["exhaustive_exact_delta"], accepted["exhaustive_exact_delta"]),
            )
            for name, actual, expected in checks:
                if abs(float(actual) - float(expected)) > TOL:
                    raise RuntimeError(
                        f"C69 seed={seed} failed C68 reproduction for {name}: "
                        f"{actual} vs {expected}"
                    )
            if dense_only != int(accepted["paired_dense_only_correct"]):
                raise RuntimeError(f"C69 seed={seed} dense-only paired count changed")
            if direct_only != int(accepted["paired_direct_only_correct"]):
                raise RuntimeError(f"C69 seed={seed} direct-only paired count changed")

        records.append(record)
        print(
            f"[C69] seed={seed} full={exhaustive.size} "
            f"dense={dense_full['trajectory_exact_accuracy']:.8f} "
            f"direct={direct_full['trajectory_exact_accuracy']:.8f} "
            f"delta={delta:+.8f} dense_only={dense_only} direct_only={direct_only}",
            flush=True,
        )

        del initial_model, dense_model, direct_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C69")

    deltas = [float(row["exhaustive_exact_delta"]) for row in records]
    direct_wins = sum(delta > TOL for delta in deltas)
    dense_wins = sum(delta < -TOL for delta in deltas)
    ties = len(deltas) - direct_wins - dense_wins
    total_dense_only = sum(int(row["paired_dense_only_correct"]) for row in records)
    total_direct_only = sum(int(row["paired_direct_only_correct"]) for row in records)

    summary = {
        "seed_count": len(SEEDS),
        "exhaustive_examples_per_seed": int(records[0]["exhaustive_examples"]),
        "accepted_c68_seed_reproduction": True,
        "exhaustive_exact_delta": _stats(deltas),
        "direct_win_seed_count": direct_wins,
        "dense_win_seed_count": dense_wins,
        "tie_seed_count": ties,
        "seed_sign_test_two_sided_p": _two_sided_sign_pvalue(direct_wins, dense_wins),
        "mean_delta_nonnegative": statistics.mean(deltas) >= -TOL,
        "median_delta_nonnegative": statistics.median(deltas) >= -TOL,
        "total_paired_dense_only_correct": total_dense_only,
        "total_paired_direct_only_correct": total_direct_only,
        "total_paired_net_direct_advantage": total_direct_only - total_dense_only,
        "pooled_paired_net_direct_nonnegative": total_direct_only >= total_dense_only,
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "12-seed exhaustive condition robustness at the C68 rank/lr point",
        "seeds": list(SEEDS),
        "rank": RANK,
        "learning_rate": LR,
        "steps": STEPS,
        "training_examples": 256,
        "condition_domain_size": 32768,
        "records": records,
        "summary": summary,
        "C68_summary_sha256": _sha256(c68_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "aligned_rank4_condition_12seed_exhaustive_robustness",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C69 is exhaustive only for the existing tiny synthetic condition domain",
            "the 12 deterministic seeds estimate optimizer/initialization robustness but are not broad task coverage",
            "no equivalence margin is declared inside C69",
            "C69 does not change rank, optimizer family, initialization scheme, runtime, or recurrence",
            "C69 alone cannot establish Gate C pass",
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
    parser.add_argument("--c68-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c68_summary_path=args.c68_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C69 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
