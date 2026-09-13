"""C68: exhaustive held-out condition generalization after C67.

C67 aligned factor/common learning rates and made composition/language match the
corresponding dense reference on all three seeds, while condition rank-4 still
missed the 128-example validation set by exactly 1/128 on two seeds.  Before
changing rank or optimizer policy, C68 asks whether that one-example residual is
an artifact of the small validation sample.

C68 reproduces the C67 condition training exactly (rank 4, lr 0.01 for all
parameters, 260 steps, batch 32), verifies the ordinary 128-example validation
scores against the accepted C67 result, and then evaluates dense and shared-
basis models on every condition trajectory not used for training.

The condition domain has 32,768 unique input signatures.  With 256 training
examples, the exhaustive held-out complement contains 32,512 trajectories.
This is a deterministic full-domain diagnostic for the existing small condition
task, not evidence about broad language generalization or Gate-C passage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.condition_task import (
    ConditionExamples,
    authoritative_targets,
    evaluate_condition,
)
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS, _build_condition
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _task_loss,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C68-shared-basis-condition-exhaustive-generalization"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
RANK = 4
STEPS = 260
LR = 0.01
BATCH_SIZE = 32
EVAL_BATCH = 1024
TOL = 1e-7


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _train_condition(model, train, seed: int, device: torch.device, phase: str) -> float:
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    final_loss = None
    marks = (65, 130, 195, 260)
    for step in range(1, STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss("condition", model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C68 seed={seed} phase={phase} non-finite loss")
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in marks:
            print(
                f"[C68] seed={seed} {phase} step={step}/{STEPS} loss={final_loss:.8f}",
                flush=True,
            )
    return float(final_loss)


def _training_signatures(train: ConditionExamples) -> set[tuple[int, ...]]:
    signatures: set[tuple[int, ...]] = set()
    for index in range(train.size):
        signatures.add(
            (
                int(train.initial_values[index].item()),
                *[int(v) for v in train.operations[index].tolist()],
                *[int(v) for v in train.candidates[index].tolist()],
            )
        )
    if len(signatures) != train.size:
        raise RuntimeError("C68 training signatures are not unique")
    return signatures


def _exhaustive_complement(config, train: ConditionExamples) -> ConditionExamples:
    excluded = _training_signatures(train)
    initial_rows: list[int] = []
    operation_rows: list[tuple[int, ...]] = []
    candidate_rows: list[tuple[int, ...]] = []

    for initial in range(config.value_vocab_size):
        for operations in itertools.product((0, 1), repeat=config.operation_steps):
            for candidates in itertools.product(
                range(config.value_vocab_size), repeat=config.operation_steps
            ):
                signature = (initial, *operations, *candidates)
                if signature in excluded:
                    continue
                initial_rows.append(initial)
                operation_rows.append(tuple(int(v) for v in operations))
                candidate_rows.append(tuple(int(v) for v in candidates))

    initial_tensor = torch.tensor(initial_rows, dtype=torch.int64)
    operation_tensor = torch.tensor(operation_rows, dtype=torch.int64)
    candidate_tensor = torch.tensor(candidate_rows, dtype=torch.int64)
    targets = authoritative_targets(initial_tensor, operation_tensor, candidate_tensor)
    examples = ConditionExamples(
        initial_values=initial_tensor,
        operations=operation_tensor,
        candidates=candidate_tensor,
        targets=targets,
    )
    capacity = config.value_vocab_size * (2 * config.value_vocab_size) ** config.operation_steps
    expected = capacity - train.size
    if examples.size != expected:
        raise RuntimeError(f"C68 exhaustive size mismatch: {examples.size} vs {expected}")
    return examples


@torch.inference_mode()
def _evaluate_batched(model, examples: ConditionExamples) -> tuple[dict, torch.Tensor]:
    training = model.training
    model.eval()
    try:
        parameter = next(model.parameters())
        device = parameter.device
        total_nll = 0.0
        total_tokens = 0
        trajectory_correct = 0
        final_correct = 0
        exact_masks: list[torch.Tensor] = []
        for start in range(0, examples.size, EVAL_BATCH):
            end = min(start + EVAL_BATCH, examples.size)
            initial = examples.initial_values[start:end].to(device)
            operations = examples.operations[start:end].to(device)
            candidates = examples.candidates[start:end].to(device)
            targets = examples.targets[start:end].to(device)
            logits = model(initial, operations, candidates)
            total_nll += float(
                F.cross_entropy(
                    logits.flatten(0, 1), targets.flatten(), reduction="sum"
                ).item()
            )
            total_tokens += int(targets.numel())
            predicted = logits.argmax(dim=-1)
            matches = predicted == targets
            trajectory_correct += int(matches.sum().item())
            final_correct += int(matches[:, -1].sum().item())
            exact_masks.append(matches.all(dim=1).cpu())
        exact = torch.cat(exact_masks, dim=0)
        metrics = {
            "examples": examples.size,
            "nll": total_nll / total_tokens,
            "trajectory_accuracy": trajectory_correct / total_tokens,
            "trajectory_exact_accuracy": float(exact.float().mean().item()),
            "trajectory_exact_correct": int(exact.sum().item()),
            "trajectory_exact_errors": int((~exact).sum().item()),
            "final_accuracy": final_correct / examples.size,
        }
        return metrics, exact
    finally:
        model.train(training)


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c67_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C68 requires CUDA")

    c67 = json.loads(c67_summary_path.read_text(encoding="utf-8"))
    if c67.get("experiment_id") != "C67-shared-basis-aligned-factor-lr-joint-training":
        raise RuntimeError("C68 requires accepted C67 summary")
    if c67.get("status") != "PASS":
        raise RuntimeError("C67 summary is not PASS")
    condition_summary = c67.get("summary", {}).get("tasks", {}).get("condition", {})
    if bool(condition_summary.get("all_direct_match_or_exceed_dense", True)):
        raise RuntimeError("C68 requires the observed C67 condition residual")

    c67_rows = {
        int(row["seed"]): row
        for row in c67.get("records", [])
        if row.get("task") == "condition"
    }
    if set(c67_rows) != set(SEEDS):
        raise RuntimeError("C67 condition references incomplete")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C68] seed={seed} start ({seed_index}/{len(SEEDS)})", flush=True)
        config, initial_model, train, validation = _build_condition(seed, "v5b", device)
        if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
            raise TypeError("C68 initial core must be HighPrecisionFixedRoutingCore")

        dense_model = copy.deepcopy(initial_model).to(device)
        direct_model = copy.deepcopy(initial_model).to(device)
        direct_model.core = JointTrainSharedBasisCore(initial_model.core, RANK).to(device)
        direct_model = direct_model.to(device)

        dense_final_loss = _train_condition(dense_model, train, seed, device, "dense")
        direct_final_loss = _train_condition(direct_model, train, seed, device, "aligned_factor")

        dense_validation = evaluate_condition(dense_model, validation)
        direct_validation = evaluate_condition(direct_model, validation)
        expected = c67_rows[seed]
        if abs(float(dense_validation["trajectory_exact_accuracy"]) - float(expected["dense_score"])) > TOL:
            raise RuntimeError(f"C68 seed={seed} dense 128-score did not reproduce C67")
        if abs(float(direct_validation["trajectory_exact_accuracy"]) - float(expected["direct_score"])) > TOL:
            raise RuntimeError(f"C68 seed={seed} direct 128-score did not reproduce C67")

        exhaustive = _exhaustive_complement(config, train)
        dense_full, dense_exact = _evaluate_batched(dense_model, exhaustive)
        direct_full, direct_exact = _evaluate_batched(direct_model, exhaustive)

        dense_only_correct = int((dense_exact & ~direct_exact).sum().item())
        direct_only_correct = int((direct_exact & ~dense_exact).sum().item())
        both_wrong = int((~dense_exact & ~direct_exact).sum().item())
        both_correct = int((dense_exact & direct_exact).sum().item())
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
            "exhaustive_exact_delta": (
                float(direct_full["trajectory_exact_accuracy"])
                - float(dense_full["trajectory_exact_accuracy"])
            ),
            "paired_dense_only_correct": dense_only_correct,
            "paired_direct_only_correct": direct_only_correct,
            "paired_both_wrong": both_wrong,
            "paired_both_correct": both_correct,
            "paired_net_direct_advantage": direct_only_correct - dense_only_correct,
            "dense_final_training_loss": dense_final_loss,
            "direct_final_training_loss": direct_final_loss,
        }
        records.append(record)
        print(
            f"[C68] seed={seed} full={exhaustive.size} "
            f"dense={dense_full['trajectory_exact_accuracy']:.8f} "
            f"direct={direct_full['trajectory_exact_accuracy']:.8f} "
            f"delta={record['exhaustive_exact_delta']:+.8f} "
            f"dense_only={dense_only_correct} direct_only={direct_only_correct}",
            flush=True,
        )
        del initial_model, dense_model, direct_model
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C68")

    deltas = [float(row["exhaustive_exact_delta"]) for row in records]
    summary = {
        "exhaustive_examples_per_seed": int(records[0]["exhaustive_examples"]),
        "exhaustive_exact_delta": _stats(deltas),
        "all_exhaustive_direct_match_or_exceed_dense": all(delta >= -TOL for delta in deltas),
        "total_paired_dense_only_correct": sum(int(row["paired_dense_only_correct"]) for row in records),
        "total_paired_direct_only_correct": sum(int(row["paired_direct_only_correct"]) for row in records),
        "total_paired_net_direct_advantage": sum(int(row["paired_net_direct_advantage"]) for row in records),
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "exhaustive held-out condition generalization after C67 one-example residuals",
        "seeds": list(SEEDS),
        "rank": RANK,
        "learning_rate": LR,
        "steps": STEPS,
        "training_examples": 256,
        "condition_domain_size": 32768,
        "records": records,
        "summary": summary,
        "C67_summary_sha256": _sha256(c67_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "c67_condition_reproduction_plus_exhaustive_heldout_evaluation",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C68 is exhaustive only for the existing tiny synthetic condition domain",
            "full-domain equality here would not imply broad language/general reasoning equivalence",
            "C68 does not change rank, optimizer, initialization, runtime, or recurrence",
            "C68 alone cannot establish Gate C pass",
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
    parser.add_argument("--c67-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c67_summary_path=args.c67_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C68 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
