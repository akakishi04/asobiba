"""C60: task-aware recovery for sub-dense shared-basis routed weights.

C58 showed that the GPU-native shared-basis family scales well at large widths.
C59 showed that post-hoc truncated-SVD fitting does not preserve the trusted
composition fixture at any sub-dense rank.  C60 asks the remaining bounded
question before rejecting the family:

    can the same fixed-rank shared-basis representation recover task quality
    when its factors are optimized directly for the task loss?

Only routed Up/Down shared-basis factors are trainable.  Shared core parameters,
module LayerNorms, biases, gate, and the surrounding task model are frozen.
Storage accounting is fixed by rank and cannot grow during tuning.

This is a representation/task-quality diagnostic.  The training forward
materializes differentiable factorized routed weights for clarity; C58 already
covers the intended factorized inference runtime family.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import time

import torch
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05.composition_task import make_composition_splits
from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture
from fold_lm.v05_benchmarks.gate_c_shared_basis_quality_frontier import _fit_role


EXPERIMENT_ID = "C60-shared-basis-task-aware-recovery"
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
RANKS = (2, 4, 8, 12, 14)
MODULES = 2
STEPS = 300
BATCH_SIZE = 64
LEARNING_RATE = 0.002
PROGRESS_MARKS = (75, 150, 225, 300)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _storage(*, width: int, hidden: int, rank: int) -> dict[str, int | float | bool]:
    dense_floats = MODULES * hidden * width + MODULES * width * hidden
    up_floats = hidden * width + rank * width + MODULES * hidden * rank
    down_floats = width * hidden + rank * hidden + MODULES * width * rank
    representation_floats = up_floats + down_floats
    dense_bytes = dense_floats * 4
    representation_bytes = representation_floats * 4
    return {
        "dense_weight_bytes": dense_bytes,
        "representation_weight_bytes": representation_bytes,
        "representation_weight_ratio": representation_bytes / dense_bytes,
        "below_dense_weight_bytes": representation_bytes < dense_bytes,
    }


class TaskTunableSharedBasisCore(nn.Module):
    """V5-B core with trainable shared-basis routed Up/Down weights only."""

    def __init__(self, source: HighPrecisionFixedRoutingCore, rank: int) -> None:
        super().__init__()
        if not isinstance(source, HighPrecisionFixedRoutingCore):
            raise TypeError("source must be HighPrecisionFixedRoutingCore")
        if type(rank) is not int or rank <= 0:
            raise ValueError("rank must be positive")
        if source.config.modules != MODULES:
            raise ValueError("C60 expects exactly two routed modules")

        self.config: LearnedCoreConfig = source.config
        self.rank = rank
        self.shared = copy.deepcopy(source.shared)
        self.shared.requires_grad_(False)
        self.norms = nn.ModuleList([copy.deepcopy(module.norm) for module in source.module_set])
        self.norms.requires_grad_(False)
        self.register_buffer("gate_logits", source.gate_logits.detach().clone())
        self.register_buffer(
            "up_biases",
            torch.stack([module.up.bias.detach().clone() for module in source.module_set], dim=0),
        )
        self.register_buffer(
            "down_biases",
            torch.stack([module.down.bias.detach().clone() for module in source.module_set], dim=0),
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

    def factor_parameters(self) -> list[nn.Parameter]:
        return [
            self.up_base,
            self.up_basis,
            self.up_coeff,
            self.down_base,
            self.down_basis,
            self.down_coeff,
        ]

    def _weight_pair(self, route_index: int) -> tuple[torch.Tensor, torch.Tensor]:
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
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index out of range")
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


def _freeze_except_factors(model: nn.Module, core: TaskTunableSharedBasisCore) -> None:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in core.factor_parameters():
        parameter.requires_grad_(True)


@torch.inference_mode()
def _score(model, evaluator, validation, score_name: str) -> float:
    was_training = model.training
    model.eval()
    value = float(evaluator(model, validation)[score_name])
    if was_training:
        model.train()
    return value


def run(
    *,
    fixture_path: Path,
    protected_result_path: Path,
    c59_summary_path: Path,
    output_dir: Path,
) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C60 requires CUDA")

    c59 = json.loads(c59_summary_path.read_text(encoding="utf-8"))
    if c59.get("experiment_id") != "C59-shared-basis-real-fixture-quality-frontier":
        raise RuntimeError("C60 requires C59 summary")
    if c59.get("status") != "PASS":
        raise RuntimeError("C59 summary is not PASS")

    protected_before = _sha256(protected_result_path)
    fixture_hash = _sha256(fixture_path)
    fixture = load_runtime_fixture(fixture_path, device="cuda")
    dense_model = fixture["models"]["dense"]
    if not isinstance(dense_model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("fixture dense core must be HighPrecisionFixedRoutingCore")
    if dense_model.core.config.width != 32 or dense_model.core.config.modules != MODULES:
        raise RuntimeError("unexpected C60 fixture core")

    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    evaluator = fixture["evaluator"]
    validation = fixture["validation"]
    score_name = str(fixture["score_name"])
    dense_score = _score(dense_model, evaluator, validation, score_name)
    train, _ = make_composition_splits(dense_model.config)
    width = int(dense_model.core.config.width)
    hidden = width * int(dense_model.core.config.hidden_mult)

    records: list[dict] = []
    total_ranks = len(RANKS)
    for rank_index, rank in enumerate(RANKS, start=1):
        storage = _storage(width=width, hidden=hidden, rank=rank)
        candidate = copy.deepcopy(dense_model)
        tunable_core = TaskTunableSharedBasisCore(dense_model.core, rank).to(device)
        candidate.core = tunable_core
        candidate = candidate.to(device)
        _freeze_except_factors(candidate, tunable_core)

        pre_score = _score(candidate, evaluator, validation, score_name)
        optimizer = torch.optim.AdamW(
            tunable_core.factor_parameters(),
            lr=LEARNING_RATE,
            weight_decay=0.0,
        )
        sampler = torch.Generator(device="cpu").manual_seed(int(fixture["seed"]) + 700)
        candidate.train()
        initial_loss = None
        final_loss = None

        for step in range(1, STEPS + 1):
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
                raise RuntimeError(f"C60 rank={rank} produced non-finite loss")
            loss.backward()
            optimizer.step()

            loss_value = float(loss.detach().item())
            if initial_loss is None:
                initial_loss = loss_value
            final_loss = loss_value
            if step in PROGRESS_MARKS:
                print(
                    f"[C60] rank={rank} ({rank_index}/{total_ranks}) "
                    f"step={step}/{STEPS} loss={loss_value:.8f}",
                    flush=True,
                )

        post_score = _score(candidate, evaluator, validation, score_name)
        records.append(
            {
                "rank": rank,
                **storage,
                "dense_score": dense_score,
                "pre_task_tuning_score": pre_score,
                "post_task_tuning_score": post_score,
                "pre_delta": pre_score - dense_score,
                "post_delta": post_score - dense_score,
                "recovered_score": post_score - pre_score,
                "initial_training_loss": float(initial_loss),
                "final_training_loss": float(final_loss),
                "steps": STEPS,
                "learning_rate": LEARNING_RATE,
                "batch_size": BATCH_SIZE,
            }
        )
        print(
            f"[C60] rank={rank} done ({rank_index}/{total_ranks}) "
            f"storage_ratio={storage['representation_weight_ratio']:.6f} "
            f"pre={pre_score:.6f} post={post_score:.6f}",
            flush=True,
        )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C60")

    preserving = [
        record for record in records
        if bool(record["below_dense_weight_bytes"])
        and abs(float(record["post_task_tuning_score"]) - dense_score) <= 1e-7
    ]
    best_rank = min((int(record["rank"]) for record in preserving), default=None)
    best_score = max(float(record["post_task_tuning_score"]) for record in records)

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "real composition fixture task-aware shared-basis recovery diagnostic",
        "task": fixture["task"],
        "fixture_seed": int(fixture["seed"]),
        "score_name": score_name,
        "dense_score": dense_score,
        "ranks": list(RANKS),
        "steps": STEPS,
        "learning_rate": LEARNING_RATE,
        "batch_size": BATCH_SIZE,
        "records": records,
        "best_sub_dense_rank_preserving_dense_score": best_rank,
        "best_post_task_tuning_score": best_score,
        "fixture_sha256": fixture_hash,
        "C59_summary_sha256": _sha256(c59_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "task_aware_factor_tuning_only",
        "non_factor_parameters_frozen": True,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C60 evaluates one trusted composition fixture only",
            "300 tuning steps are a bounded recovery test, not exhaustive hyperparameter search",
            "training uses differentiable materialized factorized routed weights; C58 covers factorized inference runtime feasibility",
            "C60 alone cannot establish Gate C pass",
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
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c59-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        fixture_path=args.fixture,
        protected_result_path=args.protected_result,
        c59_summary_path=args.c59_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C60 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
