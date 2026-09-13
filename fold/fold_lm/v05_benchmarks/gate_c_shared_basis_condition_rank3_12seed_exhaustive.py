"""C74: 12-seed exhaustive Condition rank-3 native shared-basis test.

C73 showed that large-width runtime overhead depends strongly on rank fraction:
lean/medium profiles approach Dense much more closely than the high rank=width/4
profile.  Condition currently uses rank 4 at width 16 (rank fraction 1/4), but
C63 never tested rank 3.  C74 therefore asks one isolated question: can rank 3
replace rank 4 for native aligned-lr Condition training without introducing a
systematic exhaustive quality deficit?

The exact C69 12-seed training/evaluation setup is reused except for the direct
candidate rank.  Dense references must reproduce C69.  Rank-3 results are also
compared seed-by-seed with the accepted C69 rank-4 direct scores.  No runtime is
measured here; C73 supplies the motivation for reducing rank.
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


EXPERIMENT_ID = "C74-shared-basis-condition-rank3-12seed-exhaustive"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(range(20260911, 20260923))
RANK = 3
ACCEPTED_RANK = 4
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
                f"C74 seed={seed} phase={phase} produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in (65, 130, 195, 260):
            print(
                f"[C74] seed={seed} {phase} step={step}/{STEPS} "
                f"loss={final_loss:.8f}",
                flush=True,
            )
    return float(final_loss)


def _two_sided_sign_pvalue(a_wins: int, b_wins: int) -> float:
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    k = min(a_wins, b_wins)
    lower = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * lower)


def run(
    *,
    protected_result_path: Path,
    c69_summary_path: Path,
    c73_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C74 requires CUDA")

    c69 = json.loads(c69_summary_path.read_text(encoding="utf-8"))
    if c69.get("experiment_id") != "C69-shared-basis-condition-12seed-exhaustive-robustness":
        raise RuntimeError("C74 requires accepted C69 summary")
    if c69.get("status") != "PASS" or int(c69.get("rank", -1)) != ACCEPTED_RANK:
        raise RuntimeError("C74 requires accepted C69 rank-4 result")
    if tuple(int(value) for value in c69.get("seeds", ())) != SEEDS:
        raise RuntimeError("C69 seed set mismatch")

    c73 = json.loads(c73_summary_path.read_text(encoding="utf-8"))
    if c73.get("experiment_id") != "C73-shared-basis-full-core-width-rank-scaling":
        raise RuntimeError("C74 requires accepted C73 summary")
    if c73.get("status") != "PASS":
        raise RuntimeError("C73 summary is not PASS")
    if max(int(value) for value in c73.get("widths", ())) != 5120:
        raise RuntimeError("C74 requires the extended C73 width5120 sweep")

    accepted_rows = {int(row["seed"]): row for row in c69.get("records", [])}
    if set(accepted_rows) != set(SEEDS):
        raise RuntimeError("C69 accepted seed references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)

    records: list[dict] = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C74] seed={seed} start ({seed_index}/{len(SEEDS)}) rank={RANK}", flush=True)
        config, initial_model, train, validation = _build_condition(seed, "v5b", device)
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C74 initial core must be HighPrecisionFixedRoutingCore")

        dense_model = copy.deepcopy(initial_model).to(device)
        rank3_model = copy.deepcopy(initial_model).to(device)
        rank3_model.core = JointTrainSharedBasisCore(initial_model.core, RANK).to(device)
        rank3_model = rank3_model.to(device)

        dense_final_loss = _train(dense_model, train, seed, device, "dense")
        rank3_final_loss = _train(rank3_model, train, seed, device, "rank3_aligned_factor")

        dense_validation = evaluate_condition(dense_model, validation)
        rank3_validation = evaluate_condition(rank3_model, validation)
        exhaustive = _exhaustive_complement(config, train)
        dense_full, dense_exact = _evaluate_batched(dense_model, exhaustive)
        rank3_full, rank3_exact = _evaluate_batched(rank3_model, exhaustive)

        accepted = accepted_rows[seed]
        dense_checks = (
            ("validation", dense_validation["trajectory_exact_accuracy"], accepted["dense_validation_score"]),
            ("exhaustive", dense_full["trajectory_exact_accuracy"], accepted["dense_exhaustive"]["trajectory_exact_accuracy"]),
            ("nll", dense_full["nll"], accepted["dense_exhaustive"]["nll"]),
        )
        for name, actual, expected in dense_checks:
            if abs(float(actual) - float(expected)) > TOL:
                raise RuntimeError(
                    f"C74 seed={seed} failed C69 dense reproduction for {name}: "
                    f"{actual} vs {expected}"
                )

        dense_only = int((dense_exact & ~rank3_exact).sum().item())
        rank3_only = int((rank3_exact & ~dense_exact).sum().item())
        both_wrong = int((~dense_exact & ~rank3_exact).sum().item())
        both_correct = int((dense_exact & rank3_exact).sum().item())
        rank3_score = float(rank3_full["trajectory_exact_accuracy"])
        dense_score = float(dense_full["trajectory_exact_accuracy"])
        rank4_score = float(accepted["direct_exhaustive"]["trajectory_exact_accuracy"])

        width = int(initial_model.core.config.width)
        hidden = width * int(initial_model.core.config.hidden_mult)
        rank3_storage = _storage(width=width, hidden=hidden, rank=RANK)
        rank4_storage = _storage(width=width, hidden=hidden, rank=ACCEPTED_RANK)

        record = {
            "seed": seed,
            "rank": RANK,
            **rank3_storage,
            "accepted_rank4_representation_weight_ratio": float(
                rank4_storage["representation_weight_ratio"]
            ),
            "validation_examples": validation.size,
            "dense_validation_score": float(dense_validation["trajectory_exact_accuracy"]),
            "rank3_validation_score": float(rank3_validation["trajectory_exact_accuracy"]),
            "exhaustive_examples": exhaustive.size,
            "dense_exhaustive": dense_full,
            "rank3_exhaustive": rank3_full,
            "accepted_rank4_exhaustive_exact_accuracy": rank4_score,
            "rank3_minus_dense_exact_delta": rank3_score - dense_score,
            "rank3_minus_rank4_exact_delta": rank3_score - rank4_score,
            "paired_dense_only_correct": dense_only,
            "paired_rank3_only_correct": rank3_only,
            "paired_both_wrong": both_wrong,
            "paired_both_correct": both_correct,
            "paired_net_rank3_advantage": rank3_only - dense_only,
            "dense_final_training_loss": dense_final_loss,
            "rank3_final_training_loss": rank3_final_loss,
        }
        records.append(record)
        print(
            f"[C74] seed={seed} full={exhaustive.size} "
            f"dense={dense_score:.8f} rank3={rank3_score:.8f} rank4={rank4_score:.8f} "
            f"r3-dense={rank3_score-dense_score:+.8f} "
            f"r3-r4={rank3_score-rank4_score:+.8f} "
            f"dense_only={dense_only} rank3_only={rank3_only}",
            flush=True,
        )

        del initial_model, dense_model, rank3_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C74")

    dense_deltas = [float(row["rank3_minus_dense_exact_delta"]) for row in records]
    rank4_deltas = [float(row["rank3_minus_rank4_exact_delta"]) for row in records]
    rank3_wins = sum(value > TOL for value in dense_deltas)
    dense_wins = sum(value < -TOL for value in dense_deltas)
    dense_ties = len(dense_deltas) - rank3_wins - dense_wins
    r3_over_r4 = sum(value > TOL for value in rank4_deltas)
    r4_over_r3 = sum(value < -TOL for value in rank4_deltas)
    r3_r4_ties = len(rank4_deltas) - r3_over_r4 - r4_over_r3
    total_dense_only = sum(int(row["paired_dense_only_correct"]) for row in records)
    total_rank3_only = sum(int(row["paired_rank3_only_correct"]) for row in records)

    rank3_ratio = float(records[0]["representation_weight_ratio"])
    rank4_ratio = float(records[0]["accepted_rank4_representation_weight_ratio"])
    summary = {
        "seed_count": len(SEEDS),
        "exhaustive_examples_per_seed": int(records[0]["exhaustive_examples"]),
        "accepted_c69_dense_reproduction": True,
        "rank3_representation_weight_ratio": rank3_ratio,
        "rank4_representation_weight_ratio": rank4_ratio,
        "rank3_storage_ratio_reduction_vs_rank4": rank3_ratio / rank4_ratio,
        "rank3_minus_dense_exact_delta": _stats(dense_deltas),
        "rank3_win_seed_count": rank3_wins,
        "dense_win_seed_count": dense_wins,
        "dense_tie_seed_count": dense_ties,
        "rank3_vs_dense_sign_test_two_sided_p": _two_sided_sign_pvalue(rank3_wins, dense_wins),
        "rank3_minus_rank4_exact_delta": _stats(rank4_deltas),
        "rank3_better_than_rank4_seed_count": r3_over_r4,
        "rank4_better_than_rank3_seed_count": r4_over_r3,
        "rank3_rank4_tie_seed_count": r3_r4_ties,
        "total_paired_dense_only_correct": total_dense_only,
        "total_paired_rank3_only_correct": total_rank3_only,
        "total_paired_net_rank3_advantage": total_rank3_only - total_dense_only,
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "12-seed exhaustive Condition rank3 viability after C73 runtime-rank findings",
        "seeds": list(SEEDS),
        "rank": RANK,
        "accepted_rank": ACCEPTED_RANK,
        "learning_rate": LR,
        "steps": STEPS,
        "training_examples": 256,
        "condition_domain_size": 32768,
        "records": records,
        "summary": summary,
        "C69_summary_sha256": _sha256(c69_summary_path),
        "C73_summary_sha256": _sha256(c73_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "aligned_rank3_condition_12seed_exhaustive",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C74 is exhaustive only for the existing tiny synthetic Condition domain",
            "rank3 runtime is motivated by C73 but is not directly benchmarked in C74",
            "no formal equivalence margin is declared inside C74",
            "C74 does not establish broad-task quality or Gate C passage",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c69-summary", type=Path, required=True)
    parser.add_argument("--c73-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c69_summary_path=args.c69_summary,
        c73_summary_path=args.c73_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C74 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
