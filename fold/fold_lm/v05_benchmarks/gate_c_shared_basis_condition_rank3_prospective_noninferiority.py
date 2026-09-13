"""C76: prospective independent-seed non-inferiority test for Condition rank3.

C74 showed that Condition rank3 is not catastrophically capacity-limited, but
its 12-seed evidence was mildly worse than Dense and did not justify replacing
the accepted rank4 point. C75 then quantified the operational benefit of the
3/16 rank fraction: at width5120 it reduced full-core persistent bytes by about
5.5% relative to the 1/4 profile and improved the Shared/Dense latency ratio by
roughly 3-5.5% at the tested endpoint.

C76 therefore makes one final quality decision with a criterion fixed before
looking at any new seeds. It uses 24 seeds disjoint from C69/C74 and compares
rank3 directly against rank4 with identical initialization provenance, data,
batch order, optimizer, and schedule.

Primary prospective rule:

    mean(rank3 exhaustive exact - rank4 exhaustive exact)

is declared non-inferior only if the deterministic paired-bootstrap one-sided
95% lower confidence bound is strictly greater than -0.002 absolute accuracy
(-0.20 percentage point). The margin is a design tolerance chosen before these
new seeds are evaluated; it is not inferred from C76 outcomes.

Experiment PASS means the benchmark executed correctly. The scientific result
is reported separately as ``noninferiority_gate_passed``.
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


EXPERIMENT_ID = "C76-shared-basis-condition-rank3-prospective-noninferiority"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(range(20260923, 20260947))
RANK3 = 3
RANK4 = 4
STEPS = 260
LR = 0.01
BATCH_SIZE = 32
NONINFERIORITY_MARGIN = 0.002
BOOTSTRAP_RESAMPLES = 100_000
BOOTSTRAP_SEED = 20260914
LOWER_QUANTILE = 0.05
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
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
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
                f"C76 seed={seed} phase={phase} produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in (65, 130, 195, 260):
            print(
                f"[C76] seed={seed} {phase} step={step}/{STEPS} "
                f"loss={final_loss:.8f}",
                flush=True,
            )
    return float(final_loss)


def _two_sided_sign_pvalue(a_wins: int, b_wins: int) -> float:
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    k = min(a_wins, b_wins)
    lower = sum(math.comb(n, index) for index in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * lower)


def _bootstrap_lower_mean(values: list[float]) -> float:
    if not values:
        raise ValueError("bootstrap requires values")
    samples = torch.tensor(values, dtype=torch.float64)
    generator = torch.Generator(device="cpu").manual_seed(BOOTSTRAP_SEED)
    indices = torch.randint(
        len(values),
        (BOOTSTRAP_RESAMPLES, len(values)),
        generator=generator,
        dtype=torch.int64,
    )
    means = samples[indices].mean(dim=1)
    return float(torch.quantile(means, LOWER_QUANTILE).item())


def run(
    *,
    protected_result_path: Path,
    c74_summary_path: Path,
    c75_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C76 requires CUDA")

    c74 = json.loads(c74_summary_path.read_text(encoding="utf-8"))
    if c74.get("experiment_id") != "C74-shared-basis-condition-rank3-12seed-exhaustive":
        raise RuntimeError("C76 requires accepted C74 summary")
    if c74.get("status") != "PASS":
        raise RuntimeError("C74 summary is not PASS")
    if int(c74.get("rank", -1)) != RANK3 or int(c74.get("accepted_rank", -1)) != RANK4:
        raise RuntimeError("C76 requires C74 rank3/rank4 comparison")

    c75 = json.loads(c75_summary_path.read_text(encoding="utf-8"))
    if c75.get("experiment_id") != "C75-shared-basis-condition-rank3-rank4-runtime-bridge":
        raise RuntimeError("C76 requires accepted C75 summary")
    if c75.get("status") != "PASS":
        raise RuntimeError("C75 summary is not PASS")
    c75s = c75.get("summary", {})
    if float(c75s.get("width5120_rank3_over_rank4_persistent_bytes", 2.0)) >= 1.0:
        raise RuntimeError("C76 requires C75 rank3 persistent-byte benefit")
    c75_profiles = c75s.get("profiles", {})
    r3_5120 = c75_profiles.get("rank3_bridge", {}).get("points", {}).get("5120", {})
    r4_5120 = c75_profiles.get("rank4_high", {}).get("points", {}).get("5120", {})
    for batch in ("1", "8"):
        r3_latency = float(
            r3_5120["slot_points"]["20"]["batches"][batch]["shared_over_dense_latency"]["median"]
        )
        r4_latency = float(
            r4_5120["slot_points"]["20"]["batches"][batch]["shared_over_dense_latency"]["median"]
        )
        if r3_latency >= r4_latency:
            raise RuntimeError(f"C76 requires C75 endpoint latency benefit at batch={batch}")

    old_seeds = set(int(seed) for seed in c74.get("seeds", ()))
    if old_seeds.intersection(SEEDS):
        raise RuntimeError("C76 prospective seeds must be disjoint from C74")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)

    records: list[dict] = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C76] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        config, initial_model, train, validation = _build_condition(seed, "v5b", device)
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C76 initial core must be HighPrecisionFixedRoutingCore")

        rank3_model = copy.deepcopy(initial_model).to(device)
        rank4_model = copy.deepcopy(initial_model).to(device)
        rank3_model.core = JointTrainSharedBasisCore(initial_model.core, RANK3).to(device)
        rank4_model.core = JointTrainSharedBasisCore(initial_model.core, RANK4).to(device)
        rank3_model = rank3_model.to(device)
        rank4_model = rank4_model.to(device)

        rank3_final_loss = _train(rank3_model, train, seed, device, "rank3")
        rank4_final_loss = _train(rank4_model, train, seed, device, "rank4")

        rank3_validation = evaluate_condition(rank3_model, validation)
        rank4_validation = evaluate_condition(rank4_model, validation)
        exhaustive = _exhaustive_complement(config, train)
        rank3_full, rank3_exact = _evaluate_batched(rank3_model, exhaustive)
        rank4_full, rank4_exact = _evaluate_batched(rank4_model, exhaustive)

        rank3_only = int((rank3_exact & ~rank4_exact).sum().item())
        rank4_only = int((rank4_exact & ~rank3_exact).sum().item())
        both_wrong = int((~rank3_exact & ~rank4_exact).sum().item())
        both_correct = int((rank3_exact & rank4_exact).sum().item())
        delta = (
            float(rank3_full["trajectory_exact_accuracy"])
            - float(rank4_full["trajectory_exact_accuracy"])
        )

        storage3 = _storage(
            width=int(initial_model.core.config.width),
            hidden=int(initial_model.core.config.width * initial_model.core.config.hidden_mult),
            rank=RANK3,
        )
        storage4 = _storage(
            width=int(initial_model.core.config.width),
            hidden=int(initial_model.core.config.width * initial_model.core.config.hidden_mult),
            rank=RANK4,
        )

        record = {
            "seed": seed,
            "rank3_representation_weight_ratio": float(storage3["representation_weight_ratio"]),
            "rank4_representation_weight_ratio": float(storage4["representation_weight_ratio"]),
            "validation_examples": validation.size,
            "rank3_validation_score": float(rank3_validation["trajectory_exact_accuracy"]),
            "rank4_validation_score": float(rank4_validation["trajectory_exact_accuracy"]),
            "exhaustive_examples": exhaustive.size,
            "rank3_exhaustive": rank3_full,
            "rank4_exhaustive": rank4_full,
            "rank3_minus_rank4_exact_delta": delta,
            "paired_rank3_only_correct": rank3_only,
            "paired_rank4_only_correct": rank4_only,
            "paired_both_wrong": both_wrong,
            "paired_both_correct": both_correct,
            "paired_net_rank3_advantage": rank3_only - rank4_only,
            "rank3_final_training_loss": rank3_final_loss,
            "rank4_final_training_loss": rank4_final_loss,
        }
        records.append(record)
        print(
            f"[C76] seed={seed} full={exhaustive.size} "
            f"rank3={rank3_full['trajectory_exact_accuracy']:.8f} "
            f"rank4={rank4_full['trajectory_exact_accuracy']:.8f} "
            f"delta={delta:+.8f} r3_only={rank3_only} r4_only={rank4_only}",
            flush=True,
        )

        del initial_model, rank3_model, rank4_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C76")

    deltas = [float(row["rank3_minus_rank4_exact_delta"]) for row in records]
    lower_bound = _bootstrap_lower_mean(deltas)
    rank3_wins = sum(delta > TOL for delta in deltas)
    rank4_wins = sum(delta < -TOL for delta in deltas)
    ties = len(deltas) - rank3_wins - rank4_wins
    total_rank3_only = sum(int(row["paired_rank3_only_correct"]) for row in records)
    total_rank4_only = sum(int(row["paired_rank4_only_correct"]) for row in records)
    noninferiority = lower_bound > -NONINFERIORITY_MARGIN

    summary = {
        "seed_count": len(SEEDS),
        "prospective_seeds_disjoint_from_c74": True,
        "exhaustive_examples_per_seed": int(records[0]["exhaustive_examples"]),
        "noninferiority_margin_absolute_accuracy": NONINFERIORITY_MARGIN,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_one_sided_confidence": 1.0 - LOWER_QUANTILE,
        "rank3_minus_rank4_exact_delta": _stats(deltas),
        "rank3_minus_rank4_mean_bootstrap_lower_95": lower_bound,
        "noninferiority_gate_passed": noninferiority,
        "rank3_win_seed_count": rank3_wins,
        "rank4_win_seed_count": rank4_wins,
        "tie_seed_count": ties,
        "rank3_vs_rank4_sign_test_two_sided_p": _two_sided_sign_pvalue(rank3_wins, rank4_wins),
        "total_paired_rank3_only_correct": total_rank3_only,
        "total_paired_rank4_only_correct": total_rank4_only,
        "total_paired_net_rank3_advantage": total_rank3_only - total_rank4_only,
        "rank3_representation_weight_ratio": float(records[0]["rank3_representation_weight_ratio"]),
        "rank4_representation_weight_ratio": float(records[0]["rank4_representation_weight_ratio"]),
        "C75_width5120_rank3_over_rank4_persistent_bytes": float(
            c75s["width5120_rank3_over_rank4_persistent_bytes"]
        ),
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "prospective independent-seed Condition rank3 non-inferiority decision",
        "seeds": list(SEEDS),
        "rank3": RANK3,
        "rank4": RANK4,
        "learning_rate": LR,
        "steps": STEPS,
        "batch_size": BATCH_SIZE,
        "training_examples": 256,
        "condition_domain_size": 32768,
        "prospective_primary_rule": (
            "paired-bootstrap one-sided 95% lower bound of mean(rank3-rank4 exhaustive exact) "
            "> -0.002"
        ),
        "records": records,
        "summary": summary,
        "C74_summary_sha256": _sha256(c74_summary_path),
        "C75_summary_sha256": _sha256(c75_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "paired_rank3_rank4_aligned_lr_independent_24seed_exhaustive",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C76 tests non-inferiority only on the existing tiny synthetic Condition domain",
            "the -0.002 margin is a prospective engineering tolerance, not a universal statistical standard",
            "bootstrap inference is over model/data seeds, not over individual exhaustive trajectories",
            "C76 does not establish broad-task quality or Gate C passage",
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
    parser.add_argument("--c74-summary", type=Path, required=True)
    parser.add_argument("--c75-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c74_summary_path=args.c74_summary,
        c75_summary_path=args.c75_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted from console; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C76 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
