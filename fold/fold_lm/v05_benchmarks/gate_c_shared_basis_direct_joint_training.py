"""C65: direct joint training of the shared-basis candidate from initialization.

C60-C64 established that task-aware shared-basis factors can recover dense task
quality after a dense model has already been trained, but the intended FOLD
training path should not require learning a full dense routed bank first and
compressing it afterward.

C65 therefore compares two models that start from the same untrained V5-B model
initialization for each task/seed:

1. the ordinary dense reference is trained with the original Gate-B schedule;
2. the candidate replaces the *untrained* routed Up/Down weights immediately
   with the shared-basis family, initialized by a truncated SVD of those random
   initial weights, and then trains the whole model jointly in factorized form.

The stable sub-dense ranks selected by prior diagnostics are used:

- condition: rank 4 (C63 robust final frontier);
- composition: rank 2 (C60/C61 robust frontier);
- language: rank 4 (C64 robust final checkpoint frontier).

All non-factor parameters are trainable. Factor parameters use lr=0.002, while
shared/core/surrounding parameters use the task's original Gate-B learning rate.
This is a direct-trainability diagnostic, not production runtime integration.
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
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.condition_task import evaluate_condition
from fold_lm.v05.composition_task import evaluate_composition
from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import (
    DEFAULT_SEEDS,
    _build_condition,
    _build_composition,
    _build_language,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_quality_frontier import _fit_role
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C65-shared-basis-direct-joint-training"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
TASKS = ("condition", "composition", "language")
FACTOR_LR = 0.002
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


def _trainable_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


class JointTrainSharedBasisCore(nn.Module):
    """Shared-basis routed core with every ordinary V5-B parameter trainable."""

    def __init__(self, source: HighPrecisionFixedRoutingCore, rank: int) -> None:
        super().__init__()
        if not isinstance(source, HighPrecisionFixedRoutingCore):
            raise TypeError("source must be HighPrecisionFixedRoutingCore")
        if type(rank) is not int or rank <= 0:
            raise ValueError("rank must be positive")
        if source.config.modules != 2:
            raise ValueError("C65 expects exactly two routed modules")

        self.config: LearnedCoreConfig = source.config
        self.rank = rank
        self.shared = copy.deepcopy(source.shared)
        self.norms = nn.ModuleList([copy.deepcopy(module.norm) for module in source.module_set])
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.up_biases = nn.Parameter(
            torch.stack([module.up.bias.detach().clone() for module in source.module_set], dim=0)
        )
        self.down_biases = nn.Parameter(
            torch.stack([module.down.bias.detach().clone() for module in source.module_set], dim=0)
        )

        up_weights = torch.stack(
            [module.up.weight.detach().float().cpu() for module in source.module_set], dim=0
        )
        down_weights = torch.stack(
            [module.down.weight.detach().float().cpu() for module in source.module_set], dim=0
        )
        up_fit = _fit_role(up_weights, rank)
        down_fit = _fit_role(down_weights, rank)

        self.up_base = nn.Parameter(up_fit["base"].clone())
        self.up_basis = nn.Parameter(up_fit["basis"].clone())
        self.up_coeff = nn.Parameter(up_fit["coefficients"].clone())
        self.down_base = nn.Parameter(down_fit["base"].clone())
        self.down_basis = nn.Parameter(down_fit["basis"].clone())
        self.down_coeff = nn.Parameter(down_fit["coefficients"].clone())

    def factor_parameters(self) -> tuple[nn.Parameter, ...]:
        return (
            self.up_base,
            self.up_basis,
            self.up_coeff,
            self.down_base,
            self.down_basis,
            self.down_coeff,
        )

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be positive")
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=self.up_base.device if device is None else device,
            dtype=self.up_base.dtype if dtype is None else dtype,
        )

    def _weight_pair(self, route_index: int) -> tuple[torch.Tensor, torch.Tensor]:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index out of range")
        up = self.up_base + self.up_coeff[route_index] @ self.up_basis
        down = self.down_base + self.down_coeff[route_index] @ self.down_basis
        return up, down

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        if working.ndim != 3 or tuple(working.shape[1:]) != (
            self.config.slots,
            self.config.width,
        ):
            raise ValueError("working shape does not match configured slots/width")
        if context.shape != working.shape:
            raise ValueError("context shape must match working")

        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        up_weight, down_weight = self._weight_pair(route_index)
        hidden = F.linear(normalized, up_weight, self.up_biases[route_index])
        hidden = F.gelu(hidden)
        routed_delta = F.linear(hidden, down_weight, self.down_biases[route_index])
        gate = torch.sigmoid(self.gate_logits).to(dtype=z.dtype, device=z.device)
        return working + gate * (shared_delta + routed_delta)


def _build_task(task: str, seed: int, device: torch.device):
    if task == "condition":
        config, model, train, validation = _build_condition(seed, "v5b", device)
        return config, model, train, validation, evaluate_condition
    if task == "composition":
        config, model, train, validation = _build_composition(seed, "v5b", device)
        return config, model, train, validation, evaluate_composition
    if task == "language":
        config, model, train, validation = _build_language(seed, "v5b", device)
        return config, model, train, validation, evaluate_language
    raise ValueError(f"unknown C65 task: {task}")


def _task_loss(task: str, model, train, indices: torch.Tensor, device: torch.device):
    if task == "condition":
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        candidates = train.candidates[indices].to(device)
        targets = train.targets[indices].to(device)
        logits = model(initial_values, operations, candidates)
        return F.cross_entropy(logits.flatten(0, 1), targets.flatten())

    if task == "composition":
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(model.parameters()).dtype) / float(
            model.config.state_scale
        )
        predicted = model(initial_values, operations, operands)
        return F.mse_loss(predicted, target_values)

    if task == "language":
        tokens = train.tokens[indices].to(device)
        tasks = train.tasks[indices].to(device)
        targets = train.targets[indices].to(device)
        logits = model(tokens, tasks)
        return F.cross_entropy(logits, targets)

    raise ValueError(f"unknown C65 task: {task}")


def _score(task: str, model, evaluator, validation) -> float:
    score_name = str(TASK_SPECS[task]["score_name"])
    return float(evaluator(model, validation)[score_name])


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
    common_lr = float(spec["common_lr"])
    batch_size = int(spec["batch_size"])
    marks = _progress_marks(steps)

    if factorized:
        if not isinstance(model.core, JointTrainSharedBasisCore):
            raise TypeError("factorized C65 model must use JointTrainSharedBasisCore")
        factor_params = list(model.core.factor_parameters())
        factor_ids = {id(parameter) for parameter in factor_params}
        common_params = [
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad and id(parameter) not in factor_ids
        ]
        optimizer = torch.optim.AdamW(
            [
                {"params": common_params, "lr": common_lr},
                {"params": factor_params, "lr": FACTOR_LR},
            ],
            weight_decay=0.0,
        )
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=common_lr, weight_decay=0.0)

    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    initial_loss = None
    final_loss = None
    phase = "factor" if factorized else "dense"

    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"C65 task={task} seed={seed} phase={phase} produced non-finite loss"
            )
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().item())
        if initial_loss is None:
            initial_loss = loss_value
        final_loss = loss_value
        if step in marks:
            print(
                f"[C65] task={task} seed={seed} {phase} step={step}/{steps} "
                f"loss={loss_value:.8f}",
                flush=True,
            )

    score = _score(task, model, evaluator, validation)
    return {
        "score": score,
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
    tasks = {}
    for task in TASKS:
        rows = [row for row in records if row["task"] == task]
        deltas = [float(row["direct_score_delta"]) for row in rows]
        tasks[task] = {
            "runs": len(rows),
            "rank": int(rows[0]["rank"]),
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


def run(*, protected_result_path: Path, c64_summary_path: Path, output_dir: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("C65 requires CUDA")

    c64 = json.loads(c64_summary_path.read_text(encoding="utf-8"))
    if c64.get("experiment_id") != "C64-shared-basis-language-rank-checkpoint-frontier":
        raise RuntimeError("C65 requires accepted C64 summary")
    if c64.get("status") != "PASS":
        raise RuntimeError("C64 summary is not PASS")
    if int(c64.get("summary", {}).get("minimum_rank_all_final_meet_dense", -1)) != 4:
        raise RuntimeError("C65 requires accepted C64 stable-final language rank4 frontier")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    records = []
    total = len(TASKS) * len(SEEDS)
    completed = 0

    for task in TASKS:
        spec = TASK_SPECS[task]
        rank = int(spec["rank"])
        for seed in SEEDS:
            print(
                f"[C65] task={task} seed={seed} start ({completed + 1}/{total}) rank={rank}",
                flush=True,
            )
            _config, initial_model, train, validation, evaluator = _build_task(task, seed, device)
            if not isinstance(initial_model.core, HighPrecisionFixedRoutingCore):
                raise TypeError("C65 initial core must be HighPrecisionFixedRoutingCore")

            dense_model = copy.deepcopy(initial_model).to(device)
            direct_model = copy.deepcopy(initial_model).to(device)
            direct_model.core = JointTrainSharedBasisCore(initial_model.core, rank).to(device)
            direct_model = direct_model.to(device)

            width = int(initial_model.core.config.width)
            hidden = width * int(initial_model.core.config.hidden_mult)
            storage = _storage(width=width, hidden=hidden, rank=rank)
            if not bool(storage["below_dense_weight_bytes"]):
                raise RuntimeError(f"C65 task={task} selected rank is not sub-dense")

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
                **storage,
                "dense_score": float(dense_result["score"]),
                "direct_score": float(direct_result["score"]),
                "direct_score_delta": float(direct_result["score"]) - float(dense_result["score"]),
                "dense_initial_training_loss": dense_result["initial_training_loss"],
                "dense_final_training_loss": dense_result["final_training_loss"],
                "direct_initial_training_loss": direct_result["initial_training_loss"],
                "direct_final_training_loss": direct_result["final_training_loss"],
                "dense_trainable_parameters": dense_result["trainable_parameters"],
                "direct_trainable_parameters": direct_result["trainable_parameters"],
                "direct_parameter_ratio": (
                    direct_result["trainable_parameters"] / dense_result["trainable_parameters"]
                ),
            }
            records.append(record)
            completed += 1
            print(
                f"[C65] task={task} seed={seed} done ({completed}/{total}) "
                f"rank={rank} dense={record['dense_score']:.6f} "
                f"direct={record['direct_score']:.6f} "
                f"delta={record['direct_score_delta']:+.6f} "
                f"storage={record['representation_weight_ratio']:.6f}",
                flush=True,
            )
            del initial_model, dense_model, direct_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C65")

    summary = _summarize(records)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "direct from-initialization joint training feasibility for the shared-basis candidate",
        "tasks": list(TASKS),
        "seeds": list(SEEDS),
        "task_specs": TASK_SPECS,
        "factor_learning_rate": FACTOR_LR,
        "records": records,
        "summary": summary,
        "C64_summary_sha256": _sha256(c64_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "joint_training_from_untrained_shared_basis_initialization",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C65 covers only the three existing small Gate-B tasks and three deterministic seeds",
            "factorized initialization is a truncated SVD of the untrained dense routed weights, not an independently sampled factor initializer",
            "task-specific ranks are selected from prior diagnostics rather than searched inside C65",
            "C65 tests training feasibility, not production factorized runtime or recurrence stability",
            "C65 alone cannot establish Gate C pass",
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
    parser.add_argument("--c64-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c64_summary_path=args.c64_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C65 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
