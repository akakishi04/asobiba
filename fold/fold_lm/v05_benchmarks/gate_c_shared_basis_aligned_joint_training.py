"""C67: aligned learning-rate direct joint training across Gate-B tasks.

C65 showed that direct-from-initialization shared-basis training already works
robustly for composition, is nearly robust for condition, but is unstable for
language when factor parameters use lr=0.002 while ordinary/shared parameters
use each task's original Gate-B learning rate. C66 isolated the language failure
and showed that factor_lr=0.01, matching language common_lr=0.01, recovers all
three language seeds through the final checkpoint.

C67 tests one training-rule hypothesis across all three task families:

    factor_lr = common_lr

Everything else stays aligned with C65: same seeded untrained model, same SVD
factor initialization, same task-specific ranks, same dense reference schedule,
same batch schedule, and same number of steps. This is a bounded co-adaptation
training diagnostic, not a production runtime or Gate-C pass test.
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

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _build_task,
    _task_loss,
    _trainable_parameter_count,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C67-shared-basis-aligned-factor-lr-joint-training"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
TASKS = ("condition", "composition", "language")
TOL = 1e-7

TASK_SPECS = {
    "condition": {
        "rank": 4,
        "steps": 260,
        "common_lr": 0.01,
        "batch_size": 32,
        "score_name": "trajectory_exact_accuracy",
    },
    "composition": {
        "rank": 2,
        "steps": 300,
        "common_lr": 0.005,
        "batch_size": 64,
        "score_name": "trajectory_exact_accuracy",
    },
    "language": {
        "rank": 4,
        "steps": 600,
        "common_lr": 0.01,
        "batch_size": 24,
        "score_name": "accuracy",
    },
}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _progress_marks(steps: int) -> tuple[int, ...]:
    return tuple(sorted({max(1, round(steps * x)) for x in (0.25, 0.5, 0.75, 1.0)}))


def _score(task: str, evaluator, model, validation) -> float:
    return float(evaluator(model, validation)[str(TASK_SPECS[task]["score_name"])])


def _train_one(
    *,
    task: str,
    seed: int,
    model,
    train,
    validation,
    evaluator,
    device: torch.device,
    factorized: bool,
) -> dict:
    spec = TASK_SPECS[task]
    steps = int(spec["steps"])
    lr = float(spec["common_lr"])
    batch_size = int(spec["batch_size"])
    marks = _progress_marks(steps)

    # C67's only changed training rule: every trainable parameter, including
    # shared-basis factors, uses the same task-native learning rate.
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    initial_loss = None
    final_loss = None
    phase = "aligned_factor" if factorized else "dense"

    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C67 task={task} seed={seed} phase={phase} non-finite loss"
            )
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in marks:
            print(
                f"[C67] task={task} seed={seed} {phase} step={step}/{steps} "
                f"loss={loss_value:.8f}",
                flush=True,
            )

    return {
        "score": _score(task, evaluator, model, validation),
        "initial_training_loss": float(initial_loss),
        "final_training_loss": float(final_loss),
        "trainable_parameters": _trainable_parameter_count(model),
    }


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _summarize(records: list[dict]) -> dict:
    tasks: dict[str, dict] = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        deltas = [float(row["direct_score_delta"]) for row in rows]
        tasks[task] = {
            "runs": len(rows),
            "rank": int(rows[0]["rank"]),
            "learning_rate": float(rows[0]["common_learning_rate"]),
            "representation_weight_ratio": float(rows[0]["representation_weight_ratio"]),
            "dense_score": _stats([float(row["dense_score"]) for row in rows]),
            "direct_score": _stats([float(row["direct_score"]) for row in rows]),
            "direct_score_delta": _stats(deltas),
            "all_direct_match_or_exceed_dense": all(delta >= -TOL for delta in deltas),
        }
    return {
        "tasks": tasks,
        "all_tasks_all_seeds_direct_match_or_exceed_dense": all(
            bool(tasks[task]["all_direct_match_or_exceed_dense"]) for task in TASKS
        ),
    }


def run(*, protected_result_path: Path, c66_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C67 requires CUDA")

    c66 = json.loads(c66_summary_path.read_text(encoding="utf-8"))
    if c66.get("experiment_id") != "C66-shared-basis-direct-language-factor-lr-frontier":
        raise RuntimeError("C67 requires accepted C66 summary")
    if c66.get("status") != "PASS":
        raise RuntimeError("C66 summary is not PASS")
    if abs(
        float(c66.get("summary", {}).get("minimum_tested_factor_lr_all_final_meet_dense", -1.0))
        - 0.01
    ) > 1e-12:
        raise RuntimeError("C67 requires accepted C66 language factor_lr=0.01 result")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records: list[dict] = []
    total = len(TASKS) * len(SEEDS)
    completed = 0

    for task in TASKS:
        spec = TASK_SPECS[task]
        rank = int(spec["rank"])
        common_lr = float(spec["common_lr"])
        for seed in SEEDS:
            print(
                f"[C67] task={task} seed={seed} start ({completed + 1}/{total}) "
                f"rank={rank} aligned_lr={common_lr}",
                flush=True,
            )
            _config, initial_model, train, validation, evaluator = _build_task(
                task, seed, device
            )
            if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
                raise TypeError("C67 initial core must be HighPrecisionFixedRoutingCore")

            dense_model = copy.deepcopy(initial_model).to(device)
            direct_model = copy.deepcopy(initial_model).to(device)
            direct_model.core = JointTrainSharedBasisCore(initial_model.core, rank).to(device)
            direct_model = direct_model.to(device)

            width = int(initial_model.core.config.width)
            hidden = width * int(initial_model.core.config.hidden_mult)
            storage = _storage(width=width, hidden=hidden, rank=rank)
            if not bool(storage["below_dense_weight_bytes"]):
                raise RuntimeError(f"C67 task={task} rank is not sub-dense")

            dense_result = _train_one(
                task=task,
                seed=seed,
                model=dense_model,
                train=train,
                validation=validation,
                evaluator=evaluator,
                device=device,
                factorized=False,
            )
            direct_result = _train_one(
                task=task,
                seed=seed,
                model=direct_model,
                train=train,
                validation=validation,
                evaluator=evaluator,
                device=device,
                factorized=True,
            )

            record = {
                "task": task,
                "seed": seed,
                "rank": rank,
                "common_learning_rate": common_lr,
                "factor_learning_rate": common_lr,
                **storage,
                "dense_score": float(dense_result["score"]),
                "direct_score": float(direct_result["score"]),
                "direct_score_delta": float(direct_result["score"])
                - float(dense_result["score"]),
                "dense_initial_training_loss": dense_result["initial_training_loss"],
                "dense_final_training_loss": dense_result["final_training_loss"],
                "direct_initial_training_loss": direct_result["initial_training_loss"],
                "direct_final_training_loss": direct_result["final_training_loss"],
                "dense_trainable_parameters": dense_result["trainable_parameters"],
                "direct_trainable_parameters": direct_result["trainable_parameters"],
                "direct_parameter_ratio": direct_result["trainable_parameters"]
                / dense_result["trainable_parameters"],
            }
            records.append(record)
            completed += 1
            print(
                f"[C67] task={task} seed={seed} done ({completed}/{total}) "
                f"dense={record['dense_score']:.6f} direct={record['direct_score']:.6f} "
                f"delta={record['direct_score_delta']:+.6f} "
                f"storage={record['representation_weight_ratio']:.6f}",
                flush=True,
            )

            del initial_model, dense_model, direct_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C67")

    summary = _summarize(records)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "direct joint training with factor lr aligned to task common lr",
        "tasks": list(TASKS),
        "seeds": list(SEEDS),
        "training_rule": "factor_lr_equals_common_lr",
        "task_specs": TASK_SPECS,
        "records": records,
        "summary": summary,
        "C66_summary_sha256": _sha256(c66_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "joint_training_from_untrained_shared_basis_with_aligned_lr",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C67 covers only the three existing small Gate-B tasks and three deterministic seeds",
            "task-specific ranks remain selected from prior diagnostics",
            "factorized initialization remains truncated SVD of the untrained dense routed weights",
            "C67 tests training feasibility, not production factorized runtime or recurrence stability",
            "C67 alone cannot establish Gate C pass",
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
    parser.add_argument("--c66-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c66_summary_path=args.c66_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C67 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
