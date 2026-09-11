"""V5-C recurrence perturbation measurement for compressed module weights.

This stage compares the high-precision V5-B core with its V5-C compressed
counterpart over repeated state updates.  Both paths start from the same working
state, receive the same fixed context, and use the same fixed route.  Measurements
are recorded exactly at 1 / 2 / 4 / 8 internal steps.

No pass/fail stability threshold is imposed here.  Gate C must combine these
numerical perturbations with downstream task quality before deciding what level
of recurrence amplification is acceptable.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch

from .compressed_runtime import CompressedFixedRoutingCore
from .modules import HighPrecisionFixedRoutingCore


DEFAULT_CHECKPOINTS = (1, 2, 4, 8)


@dataclass(frozen=True)
class RecurrencePerturbation:
    steps: int
    rmse: float
    max_abs_error: float
    relative_l2_error: float
    dense_state_rms: float
    compressed_state_rms: float
    amplification_vs_step1: float

    def __post_init__(self) -> None:
        if type(self.steps) is not int or self.steps <= 0:
            raise ValueError("steps must be a positive integer")
        for name in (
            "rmse",
            "max_abs_error",
            "relative_l2_error",
            "dense_state_rms",
            "compressed_state_rms",
            "amplification_vs_step1",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class RecurrenceStabilityReport:
    checkpoints: tuple[int, ...]
    measurements: tuple[RecurrencePerturbation, ...]

    def __post_init__(self) -> None:
        if not self.checkpoints:
            raise ValueError("checkpoints must be non-empty")
        if tuple(sorted(self.checkpoints)) != self.checkpoints:
            raise ValueError("checkpoints must be strictly increasing")
        if len(set(self.checkpoints)) != len(self.checkpoints):
            raise ValueError("checkpoints must be distinct")
        if any(type(step) is not int or step <= 0 for step in self.checkpoints):
            raise ValueError("checkpoints must contain positive integers")
        if len(self.measurements) != len(self.checkpoints):
            raise ValueError("measurements must match checkpoints")
        if tuple(item.steps for item in self.measurements) != self.checkpoints:
            raise ValueError("measurement steps must match checkpoints")

    @property
    def max_amplification(self) -> float:
        return max(item.amplification_vs_step1 for item in self.measurements)

    @property
    def final(self) -> RecurrencePerturbation:
        return self.measurements[-1]


def _validate_state_pair(
    source: HighPrecisionFixedRoutingCore,
    compressed: CompressedFixedRoutingCore,
    working: torch.Tensor,
    context: torch.Tensor,
    route_index: int,
) -> None:
    if not isinstance(source, HighPrecisionFixedRoutingCore):
        raise TypeError("source must be HighPrecisionFixedRoutingCore")
    if not isinstance(compressed, CompressedFixedRoutingCore):
        raise TypeError("compressed must be CompressedFixedRoutingCore")
    if source.config != compressed.config:
        raise ValueError("source and compressed core configs must match")
    if type(route_index) is not int or not 0 <= route_index < source.config.modules:
        raise ValueError("route_index out of range")
    if not isinstance(working, torch.Tensor) or not isinstance(context, torch.Tensor):
        raise TypeError("working and context must be torch.Tensor")
    expected_tail = (source.config.slots, source.config.width)
    if working.ndim != 3 or tuple(working.shape[1:]) != expected_tail:
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


def _validate_checkpoints(checkpoints: tuple[int, ...]) -> tuple[int, ...]:
    checkpoints = tuple(checkpoints)
    if not checkpoints:
        raise ValueError("checkpoints must be non-empty")
    if any(type(step) is not int or step <= 0 for step in checkpoints):
        raise ValueError("checkpoints must contain positive integers")
    if tuple(sorted(checkpoints)) != checkpoints or len(set(checkpoints)) != len(checkpoints):
        raise ValueError("checkpoints must be strictly increasing and distinct")
    return checkpoints


def _rms(value: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(value.double() * value.double())).item())


@torch.inference_mode()
def measure_recurrence_stability(
    source: HighPrecisionFixedRoutingCore,
    compressed: CompressedFixedRoutingCore,
    working: torch.Tensor,
    context: torch.Tensor,
    *,
    route_index: int,
    checkpoints: tuple[int, ...] = DEFAULT_CHECKPOINTS,
) -> RecurrenceStabilityReport:
    """Measure compressed-state drift at fixed recurrence checkpoints."""
    checkpoints = _validate_checkpoints(checkpoints)
    _validate_state_pair(source, compressed, working, context, route_index)

    dense_state = working.clone()
    compressed_state = working.clone()
    measurements: list[RecurrencePerturbation] = []
    first_rmse: float | None = None
    max_step = checkpoints[-1]
    checkpoint_set = set(checkpoints)

    for step in range(1, max_step + 1):
        dense_state = source(dense_state, context, route_index=route_index)
        compressed_state = compressed(
            compressed_state, context, route_index=route_index
        )
        if step not in checkpoint_set:
            continue

        difference = compressed_state - dense_state
        rmse = _rms(difference)
        max_abs_error = float(difference.abs().max().item())
        dense_norm = float(torch.linalg.vector_norm(dense_state.double()).item())
        diff_norm = float(torch.linalg.vector_norm(difference.double()).item())
        relative_l2 = diff_norm / max(dense_norm, 1e-12)
        dense_rms = _rms(dense_state)
        compressed_rms = _rms(compressed_state)

        if first_rmse is None:
            first_rmse = rmse
            amplification = 1.0 if rmse > 0.0 else 0.0
        elif first_rmse > 0.0:
            amplification = rmse / first_rmse
        else:
            amplification = 0.0 if rmse == 0.0 else float("inf")

        if not math.isfinite(amplification):
            raise ValueError("recurrence perturbation became non-finite")
        measurements.append(
            RecurrencePerturbation(
                steps=step,
                rmse=rmse,
                max_abs_error=max_abs_error,
                relative_l2_error=relative_l2,
                dense_state_rms=dense_rms,
                compressed_state_rms=compressed_rms,
                amplification_vs_step1=amplification,
            )
        )

    return RecurrenceStabilityReport(
        checkpoints=checkpoints,
        measurements=tuple(measurements),
    )
