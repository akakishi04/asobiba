"""V5-A float64 reference state-update core.

This is deliberately a small, explicit reference computation.  It is not the
V5-B learned core and contains no routing, compression, memory lookup, or
information acquisition.  Its purpose is to give later optimized/compressed
paths a deterministic materialized calculation to match.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import BudgetState, EvidenceState, WorkingState, advance_internal


def _readonly_float64(value: np.ndarray, *, name: str, ndim: int) -> np.ndarray:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.ndim != ndim:
        raise ValueError(f"{name} must be rank-{ndim}")
    if any(size <= 0 for size in array.shape):
        raise ValueError(f"{name} dimensions must be non-empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ReferenceLinearCore:
    """Materialized residual state update used by V5-A reference tests.

    For working slots ``H`` and an already prepared same-shape context ``C``::

        mixed = H + C
        delta = mixed @ W.T + b
        H_next = H + gate * delta

    ``gate`` is feature-wise and constrained to [0, 1].  Keeping the operation
    explicit makes later direct-decoded/compressed implementations comparable to
    one unambiguous float64 path.
    """

    weight: np.ndarray
    bias: np.ndarray
    gate: np.ndarray

    def __post_init__(self) -> None:
        weight = _readonly_float64(self.weight, name="weight", ndim=2)
        if weight.shape[0] != weight.shape[1]:
            raise ValueError("weight must be square")
        width = weight.shape[0]

        bias = _readonly_float64(self.bias, name="bias", ndim=1)
        gate = _readonly_float64(self.gate, name="gate", ndim=1)
        if bias.shape != (width,):
            raise ValueError("bias width must match weight")
        if gate.shape != (width,):
            raise ValueError("gate width must match weight")
        if np.any(gate < 0.0) or np.any(gate > 1.0):
            raise ValueError("gate values must be in [0, 1]")

        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "bias", bias)
        object.__setattr__(self, "gate", gate)

    @property
    def width(self) -> int:
        return int(self.weight.shape[0])

    def compute_slots(self, working: WorkingState, context: np.ndarray) -> np.ndarray:
        if not isinstance(working, WorkingState):
            raise TypeError("working must be WorkingState")
        if working.slots.shape[1] != self.width:
            raise ValueError("working-state width does not match core width")

        context_array = np.array(context, dtype=np.float64, copy=True)
        if context_array.shape != working.slots.shape:
            raise ValueError("context shape must match working slots")
        if not np.isfinite(context_array).all():
            raise ValueError("context must contain only finite values")

        mixed = working.slots + context_array
        delta = mixed @ self.weight.T + self.bias
        updated = working.slots + self.gate * delta
        if not np.isfinite(updated).all():
            raise ValueError("reference state update produced non-finite values")
        return updated


def reference_internal_step(
    evidence: EvidenceState,
    working: WorkingState,
    budget: BudgetState,
    core: ReferenceLinearCore,
    context: np.ndarray,
) -> tuple[EvidenceState, WorkingState, BudgetState]:
    """Run one V5-A reference computation without advancing evidence time."""

    if not isinstance(core, ReferenceLinearCore):
        raise TypeError("core must be ReferenceLinearCore")
    slots = core.compute_slots(working, context)
    return advance_internal(evidence, working, budget, slots=slots)
