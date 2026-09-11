"""V5-C diagnostic: task-aware recovery with fixed compressed structure.

C9 showed that making the codebook representation progressively more faithful
improves the recurrent composition task, but even the high-fidelity profile
remains far below the high-precision model.  Weight reconstruction MSE also did
not predict task quality reliably.

This benchmark therefore changes only the optimization objective:

- start from the same high-fidelity post-training compression candidate;
- keep block codes fixed;
- keep sparse-correction coordinates fixed;
- keep payload/accounting fixed;
- keep every non-compressed model parameter frozen;
- tune only shared compressed base/codebook values and bounded correction values
  using the original composition task loss.

The training path materializes differentiable compressed weights for clarity.
It is a diagnostic for representation/objective adequacy, not a runtime path.
If task quality recovers without changing codes or payload, reconstruction MSE
was the wrong final objective.  If it does not, the representation itself still
lacks sufficient capacity for composition-sensitive weights.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import json
import math
import sys

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.compressed_runtime import CompressedModuleInitializations
from fold_lm.v05.compression_tuning import FixedCodeContinuousCompression
from fold_lm.v05.modules import HighPrecisionFixedRoutingCore, LearnedCoreConfig
from fold_lm.v05.composition_task import evaluate_composition, make_composition_splits
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS
from fold_lm.v05_benchmarks.gate_c_composition_frontier import PROFILES
from fold_lm.v05_benchmarks.gate_c_task_quality import (
    CompressionProfile,
    _compress_role,
    _stack_role_weights,
    _train_high_precision,
)


PROFILE_NAME = "high_fidelity"
DEFAULT_PROFILE = PROFILES[PROFILE_NAME]


class TaskTunableCompressedCore(nn.Module):
    """V5-B core whose compressed module weights remain differentiable.

    Only ``up`` and ``down`` compressed continuous values are trainable.  Shared
    core parameters, module LayerNorms, biases, gate, codes, and correction
    coordinates are fixed.
    """

    def __init__(
        self,
        source: HighPrecisionFixedRoutingCore,
        initializations: CompressedModuleInitializations,
    ) -> None:
        super().__init__()
        if not isinstance(source, HighPrecisionFixedRoutingCore):
            raise TypeError("source must be HighPrecisionFixedRoutingCore")
        if not isinstance(initializations, CompressedModuleInitializations):
            raise TypeError("initializations must be CompressedModuleInitializations")
        if len(initializations.up.encoded_weights) != source.config.modules:
            raise ValueError("compressed module count must match source core")

        self.config: LearnedCoreConfig = source.config
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
        self.up = FixedCodeContinuousCompression(initializations.up)
        self.down = FixedCodeContinuousCompression(initializations.down)

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        parameter = next(self.up.parameters())
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=parameter.device if device is None else device,
            dtype=parameter.dtype if dtype is None else dtype,
        )

    def _validate(self, working: torch.Tensor, context: torch.Tensor, route_index: int) -> None:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index is out of range")
        if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
            raise TypeError("working and context must be torch.Tensor")
        if working.ndim != 3 or tuple(working.shape[1:]) != (
            self.config.slots,
            self.config.width,
        ):
            raise ValueError("working shape does not match configured slots/width")
        if context.shape != working.shape:
            raise ValueError("context shape must match working")
        if not working.is_floating_point() or not context.is_floating_point():
            raise TypeError("working and context must use floating dtypes")
        if working.dtype != context.dtype:
            raise TypeError("working and context dtypes must match")
        if working.device != context.device:
            raise ValueError("working and context must be on the same device")
        if not torch.isfinite(working).all() or not torch.isfinite(context).all():
            raise ValueError("working and context must contain only finite values")

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        self._validate(working, context, route_index)
        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        up_weight = self.up.materialized_weight(route_index).to(
            dtype=z.dtype, device=z.device
        )
        down_weight = self.down.materialized_weight(route_index).to(
            dtype=z.dtype, device=z.device
        )
        hidden = F.linear(normalized, up_weight, self.up_biases[route_index])
        hidden = F.gelu(hidden)
        routed_delta = F.linear(hidden, down_weight, self.down_biases[route_index])
        gate = torch.sigmoid(self.gate_logits).to(dtype=z.dtype, device=z.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("task-tunable compressed core produced non-finite values")
        return updated

    def compressed_trainable_parameters(self) -> list[nn.Parameter]:
        return [
            parameter
            for module in (self.up, self.down)
            for parameter in module.parameters()
            if parameter.requires_grad
        ]

    def export_initializations(self) -> CompressedModuleInitializations:
        return CompressedModuleInitializations(
            up=self.up.export(),
            down=self.down.export(),
        )


@dataclass(frozen=True)
class TaskAwareRecoveryResult:
    high_precision_score: float
    pre_task_tuning_score: float
    post_task_tuning_score: float
    module_payload_ratio: float
    max_observed_abs_correction: float
    steps: int

    def __post_init__(self) -> None:
        for name in (
            "high_precision_score",
            "pre_task_tuning_score",
            "post_task_tuning_score",
            "module_payload_ratio",
            "max_observed_abs_correction",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if type(self.steps) is not int or self.steps <= 0:
            raise ValueError("steps must be positive")


def _initializations_from_core(
    core: HighPrecisionFixedRoutingCore,
    profile: CompressionProfile,
    *,
    device: torch.device,
) -> tuple[CompressedModuleInitializations, dict]:
    if not isinstance(core, HighPrecisionFixedRoutingCore):
        raise TypeError("core must be HighPrecisionFixedRoutingCore")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    up_weights = _stack_role_weights(core, "up")
    down_weights = _stack_role_weights(core, "down")
    up, up_diag = _compress_role(up_weights, profile, device=device)
    down, down_diag = _compress_role(down_weights, profile, device=device)
    dense_bytes = up_diag.dense_float32_bytes + down_diag.dense_float32_bytes
    encoded_bytes = up_diag.encoded_payload_bytes + down_diag.encoded_payload_bytes
    return CompressedModuleInitializations(up=up, down=down), {
        "module_dense_float32_bytes": dense_bytes,
        "module_estimated_encoded_payload_bytes": encoded_bytes,
        "module_payload_ratio": encoded_bytes / dense_bytes,
        "up": up_diag.__dict__,
        "down": down_diag.__dict__,
    }


def _max_abs_correction(core: TaskTunableCompressedCore) -> float:
    values: list[float] = []
    for bank in (core.up, core.down):
        for correction in bank.corrections:
            current = correction.values().detach()
            if current.numel():
                values.append(float(current.abs().max().item()))
    return max(values, default=0.0)


def _freeze_except_compressed(model, core: TaskTunableCompressedCore) -> None:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in core.up.parameters():
        parameter.requires_grad_(True)
    for parameter in core.down.parameters():
        parameter.requires_grad_(True)


def run_seed(
    seed: int,
    *,
    profile: CompressionProfile = DEFAULT_PROFILE,
    steps: int = 300,
    learning_rate: float = 0.002,
    batch_size: int = 64,
    device: str | torch.device = "cpu",
) -> dict:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    if type(steps) is not int or steps <= 0:
        raise ValueError("steps must be positive")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(float(learning_rate)) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be positive")

    device = torch.device(device)
    model, validation, evaluator, score_name = _train_high_precision(
        "composition", seed, device
    )
    if not isinstance(model.core, HighPrecisionFixedRoutingCore):
        raise TypeError("trained composition core must remain HighPrecisionFixedRoutingCore")
    high_score = float(evaluator(model, validation)[score_name])

    initializations, diagnostics = _initializations_from_core(
        model.core, profile, device=device
    )
    initial_codes_up = np.stack([item.codes for item in initializations.up.encoded_weights], axis=0)
    initial_codes_down = np.stack([item.codes for item in initializations.down.encoded_weights], axis=0)
    initial_indices_up = tuple(item.correction_indices.copy() for item in initializations.up.encoded_weights)
    initial_indices_down = tuple(item.correction_indices.copy() for item in initializations.down.encoded_weights)

    tuned_model = copy.deepcopy(model)
    tunable_core = TaskTunableCompressedCore(model.core, initializations).to(device)
    tuned_model.core = tunable_core
    tuned_model = tuned_model.to(device)
    _freeze_except_compressed(tuned_model, tunable_core)

    pre_score = float(evaluator(tuned_model, validation)[score_name])
    train, _ = make_composition_splits(tuned_model.config)
    optimizer = torch.optim.AdamW(
        tunable_core.compressed_trainable_parameters(),
        lr=float(learning_rate),
        weight_decay=0.0,
    )
    sampler = torch.Generator(device="cpu").manual_seed(seed + 700)
    tuned_model.train()
    for _ in range(steps):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        initial_values = train.initial_values[indices].to(device)
        operations = train.operations[indices].to(device)
        operands = train.operands[indices].to(device)
        targets = train.targets[indices].to(device)
        target_values = targets.to(dtype=next(tuned_model.parameters()).dtype) / float(
            tuned_model.config.state_scale
        )
        optimizer.zero_grad(set_to_none=True)
        predicted = tuned_model(initial_values, operations, operands)
        loss = F.mse_loss(predicted, target_values)
        if not torch.isfinite(loss):
            raise ValueError("task-aware compressed tuning produced non-finite loss")
        loss.backward()
        optimizer.step()

    post_score = float(evaluator(tuned_model, validation)[score_name])
    exported = tunable_core.export_initializations()
    exported_codes_up = np.stack([item.codes for item in exported.up.encoded_weights], axis=0)
    exported_codes_down = np.stack([item.codes for item in exported.down.encoded_weights], axis=0)
    if not np.array_equal(initial_codes_up, exported_codes_up) or not np.array_equal(
        initial_codes_down, exported_codes_down
    ):
        raise RuntimeError("task-aware tuning changed fixed codes")
    for before, after in zip(initial_indices_up, exported.up.encoded_weights):
        if not np.array_equal(before, after.correction_indices):
            raise RuntimeError("task-aware tuning changed up correction coordinates")
    for before, after in zip(initial_indices_down, exported.down.encoded_weights):
        if not np.array_equal(before, after.correction_indices):
            raise RuntimeError("task-aware tuning changed down correction coordinates")
    if exported.up.accounting != initializations.up.accounting or exported.down.accounting != initializations.down.accounting:
        raise RuntimeError("task-aware tuning changed compressed payload accounting")

    result = TaskAwareRecoveryResult(
        high_precision_score=high_score,
        pre_task_tuning_score=pre_score,
        post_task_tuning_score=post_score,
        module_payload_ratio=float(diagnostics["module_payload_ratio"]),
        max_observed_abs_correction=_max_abs_correction(tunable_core),
        steps=steps,
    )
    return {
        "seed": seed,
        "profile": PROFILE_NAME,
        "score_name": score_name,
        **result.__dict__,
        "pre_delta": result.pre_task_tuning_score - result.high_precision_score,
        "post_delta": result.post_task_tuning_score - result.high_precision_score,
        "recovered_score": result.post_task_tuning_score - result.pre_task_tuning_score,
        "payload_unchanged": True,
        "codes_unchanged": True,
        "correction_coordinates_unchanged": True,
    }


def summarize(records: list[dict]) -> dict:
    if not records:
        raise ValueError("records must be non-empty")
    return {
        "runs": len(records),
        "mean_high_precision_score": sum(float(row["high_precision_score"]) for row in records) / len(records),
        "mean_pre_task_tuning_score": sum(float(row["pre_task_tuning_score"]) for row in records) / len(records),
        "mean_post_task_tuning_score": sum(float(row["post_task_tuning_score"]) for row in records) / len(records),
        "min_post_task_tuning_score": min(float(row["post_task_tuning_score"]) for row in records),
        "mean_recovered_score": sum(float(row["recovered_score"]) for row in records) / len(records),
        "worst_post_delta": min(float(row["post_delta"]) for row in records),
        "mean_module_payload_ratio": sum(float(row["module_payload_ratio"]) for row in records) / len(records),
        "max_observed_abs_correction": max(float(row["max_observed_abs_correction"]) for row in records),
        "all_payload_unchanged": all(bool(row["payload_unchanged"]) for row in records),
        "all_codes_unchanged": all(bool(row["codes_unchanged"]) for row in records),
        "all_correction_coordinates_unchanged": all(bool(row["correction_coordinates_unchanged"]) for row in records),
    }


def run_benchmark(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    profile: CompressionProfile = DEFAULT_PROFILE,
    steps: int = 300,
    learning_rate: float = 0.002,
    batch_size: int = 64,
    device: str | torch.device = "cpu",
) -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("seeds must be distinct nonnegative integers")
    if not isinstance(profile, CompressionProfile):
        raise TypeError("profile must be CompressionProfile")
    records: list[dict] = []
    for index, seed in enumerate(seeds, start=1):
        print(
            f"[gate-c-task-aware] start composition seed={seed} ({index}/{len(seeds)})",
            file=sys.stderr,
            flush=True,
        )
        record = run_seed(
            seed,
            profile=profile,
            steps=steps,
            learning_rate=learning_rate,
            batch_size=batch_size,
            device=device,
        )
        records.append(record)
        print(
            f"[gate-c-task-aware] done seed={seed} pre={record['pre_task_tuning_score']:.6f} "
            f"post={record['post_task_tuning_score']:.6f} payload={record['module_payload_ratio']:.6f}",
            file=sys.stderr,
            flush=True,
        )
    return {
        "schema": "fold-v05-gate-c-task-aware-recovery-v1",
        "device": str(torch.device(device)),
        "seeds": list(seeds),
        "profile": PROFILE_NAME,
        "steps": steps,
        "learning_rate": float(learning_rate),
        "batch_size": batch_size,
        "records": records,
        "summary": summarize(records),
        "diagnostic_only": True,
        "runtime_path": "differentiable materialized compressed weights",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    result = run_benchmark(
        seeds=tuple(args.seeds),
        steps=args.steps,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
