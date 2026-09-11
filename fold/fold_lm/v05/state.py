"""V5-A reference state and provenance contracts.

This module deliberately contains no learned controller, compression, memory
routing, or vision logic.  It fixes only the evidence/internal-step boundary,
provenance separation, immutable float64 working slots, and bounded budgets.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class ProvenanceKind(str, Enum):
    OBSERVED = "observed"
    HYPOTHESIS = "hypothesis"


@dataclass(frozen=True)
class Provenance:
    source_id: str
    kind: ProvenanceKind
    revision: int
    evidence_time: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be a non-empty string")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        if type(self.evidence_time) is not int or self.evidence_time < 0:
            raise ValueError("evidence_time must be a nonnegative integer")
        if not isinstance(self.kind, ProvenanceKind):
            raise TypeError("kind must be ProvenanceKind")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance")


@dataclass(frozen=True)
class EvidenceState:
    """Authoritative external evidence visible at evidence time ``t``.

    Hypotheses are intentionally rejected here.  They may live in later
    working/goal state, but they are not silently promoted to observations.
    """

    evidence_time: int
    revision: int
    observations: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if type(self.evidence_time) is not int or self.evidence_time < 0:
            raise ValueError("evidence_time must be a nonnegative integer")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        if not isinstance(self.observations, tuple):
            raise TypeError("observations must be a tuple")

        seen: set[str] = set()
        for ref in self.observations:
            if not isinstance(ref, EvidenceRef):
                raise TypeError("observations must contain EvidenceRef values")
            if ref.evidence_id in seen:
                raise ValueError(f"duplicate evidence_id: {ref.evidence_id}")
            seen.add(ref.evidence_id)
            provenance = ref.provenance
            if provenance.kind is not ProvenanceKind.OBSERVED:
                raise ValueError("hypothesis provenance cannot enter EvidenceState")
            if provenance.evidence_time > self.evidence_time:
                raise ValueError("evidence provenance is from a future evidence time")
            if provenance.revision > self.revision:
                raise ValueError("evidence provenance is from a future revision")


@dataclass(frozen=True)
class WorkingState:
    """Small float64 reference working area for internal step ``k``."""

    evidence_time: int
    internal_step: int
    slots: np.ndarray

    def __post_init__(self) -> None:
        if type(self.evidence_time) is not int or self.evidence_time < 0:
            raise ValueError("evidence_time must be a nonnegative integer")
        if type(self.internal_step) is not int or self.internal_step < 0:
            raise ValueError("internal_step must be a nonnegative integer")

        slots = np.array(self.slots, dtype=np.float64, copy=True)
        if slots.ndim != 2 or slots.shape[0] <= 0 or slots.shape[1] <= 0:
            raise ValueError("slots must be a non-empty rank-2 array")
        if not np.isfinite(slots).all():
            raise ValueError("slots must contain only finite values")
        slots.setflags(write=False)
        object.__setattr__(self, "slots", slots)

    def next_internal(self, slots: np.ndarray | None = None) -> "WorkingState":
        return WorkingState(
            evidence_time=self.evidence_time,
            internal_step=self.internal_step + 1,
            slots=self.slots if slots is None else slots,
        )


@dataclass(frozen=True)
class BudgetState:
    internal_steps_remaining: int
    acquisitions_remaining: int

    def __post_init__(self) -> None:
        for name in ("internal_steps_remaining", "acquisitions_remaining"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")

    def consume_internal_step(self) -> "BudgetState":
        if self.internal_steps_remaining <= 0:
            raise ValueError("internal-step budget exhausted")
        return BudgetState(
            internal_steps_remaining=self.internal_steps_remaining - 1,
            acquisitions_remaining=self.acquisitions_remaining,
        )


def advance_internal(
    evidence: EvidenceState,
    working: WorkingState,
    budget: BudgetState,
    *,
    slots: np.ndarray | None = None,
) -> tuple[EvidenceState, WorkingState, BudgetState]:
    """Advance internal step ``k`` without advancing evidence time/revision."""

    if not isinstance(evidence, EvidenceState):
        raise TypeError("evidence must be EvidenceState")
    if not isinstance(working, WorkingState):
        raise TypeError("working must be WorkingState")
    if not isinstance(budget, BudgetState):
        raise TypeError("budget must be BudgetState")
    if working.evidence_time != evidence.evidence_time:
        raise ValueError("working state evidence_time does not match EvidenceState")

    return evidence, working.next_internal(slots), budget.consume_internal_step()
