"""V5-A storage and execution accounting references.

The reference deliberately distinguishes independent continuous scalars,
theoretical discrete-code bits, actual serialized bytes, active computation,
internal-step count, and measured wall-clock.  It is not a V5-C production
format or profiler; it exists so later implementations cannot hide storage or
execution costs behind decoded/effective parameter counts.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
import time
from typing import Callable, Iterable

import numpy as np

from .compression import AdditiveCodebookWeight
from .core import ReferenceLinearCore, reference_internal_step
from .state import BudgetState, EvidenceState, WorkingState


_MAGIC = b"F05A"
_VERSION = 1
_HEADER = struct.Struct("<4sBIII")


@dataclass(frozen=True)
class StorageAccounting:
    independent_continuous_scalars: int
    continuous_payload_bytes: int
    discrete_code_bits: int
    discrete_code_bytes: int
    metadata_bytes: int
    serialized_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "independent_continuous_scalars",
            "continuous_payload_bytes",
            "discrete_code_bits",
            "discrete_code_bytes",
            "metadata_bytes",
            "serialized_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.serialized_bytes != (
            self.continuous_payload_bytes + self.discrete_code_bytes + self.metadata_bytes
        ):
            raise ValueError("serialized byte accounting does not sum exactly")


@dataclass(frozen=True)
class ExecutionAccounting:
    """Measured execution costs for one V5-A reference sequence."""

    internal_steps: int
    active_module_invocations: int
    max_active_modules_per_step: int
    wall_clock_seconds: float

    def __post_init__(self) -> None:
        for name in (
            "internal_steps",
            "active_module_invocations",
            "max_active_modules_per_step",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not isinstance(self.wall_clock_seconds, (int, float)):
            raise TypeError("wall_clock_seconds must be numeric")
        wall = float(self.wall_clock_seconds)
        if not math.isfinite(wall) or wall < 0.0:
            raise ValueError("wall_clock_seconds must be finite and nonnegative")
        if self.internal_steps == 0:
            if self.active_module_invocations != 0 or self.max_active_modules_per_step != 0:
                raise ValueError("zero steps cannot report active modules")
        else:
            if self.active_module_invocations < self.internal_steps:
                raise ValueError("each V5-A reference step must invoke at least one active module")
            if self.max_active_modules_per_step <= 0:
                raise ValueError("nonzero steps require an active module")
        object.__setattr__(self, "wall_clock_seconds", wall)


def code_bits_per_index(entries_per_codebook: int) -> int:
    if type(entries_per_codebook) is not int or entries_per_codebook <= 0:
        raise ValueError("entries_per_codebook must be a positive integer")
    if entries_per_codebook == 1:
        return 0
    return int(math.ceil(math.log2(entries_per_codebook)))


def _pack_codes(codes: np.ndarray, bits_per_code: int) -> bytes:
    if bits_per_code == 0:
        return b""
    accumulator = 0
    used_bits = 0
    out = bytearray()
    for code in codes:
        accumulator |= int(code) << used_bits
        used_bits += bits_per_code
        while used_bits >= 8:
            out.append(accumulator & 0xFF)
            accumulator >>= 8
            used_bits -= 8
    if used_bits:
        out.append(accumulator & 0xFF)
    return bytes(out)


def accounting_for(weight: AdditiveCodebookWeight) -> StorageAccounting:
    if not isinstance(weight, AdditiveCodebookWeight):
        raise TypeError("weight must be AdditiveCodebookWeight")

    continuous_scalars = int(weight.base.size + weight.codebook.size)
    continuous_bytes = continuous_scalars * np.dtype("<f8").itemsize
    bits_per_code = code_bits_per_index(weight.entries_per_codebook)
    code_bits = weight.codebook_count * bits_per_code
    code_bytes = (code_bits + 7) // 8
    metadata_bytes = _HEADER.size
    return StorageAccounting(
        independent_continuous_scalars=continuous_scalars,
        continuous_payload_bytes=continuous_bytes,
        discrete_code_bits=code_bits,
        discrete_code_bytes=code_bytes,
        metadata_bytes=metadata_bytes,
        serialized_bytes=continuous_bytes + code_bytes + metadata_bytes,
    )


def serialize_additive_codebook(weight: AdditiveCodebookWeight) -> bytes:
    """Serialize the V5-A reference in one deterministic little-endian format."""
    if not isinstance(weight, AdditiveCodebookWeight):
        raise TypeError("weight must be AdditiveCodebookWeight")

    width = weight.width
    q_count = weight.codebook_count
    entries = weight.entries_per_codebook
    header = _HEADER.pack(_MAGIC, _VERSION, width, q_count, entries)
    base_bytes = np.asarray(weight.base, dtype="<f8").tobytes(order="C")
    codebook_bytes = np.asarray(weight.codebook, dtype="<f8").tobytes(order="C")
    bits_per_code = code_bits_per_index(entries)
    code_bytes = _pack_codes(weight.codes, bits_per_code)

    blob = header + base_bytes + codebook_bytes + code_bytes
    expected = accounting_for(weight).serialized_bytes
    if len(blob) != expected:
        raise RuntimeError("serializer/accounting byte count mismatch")
    return blob


def measure_reference_steps(
    evidence: EvidenceState,
    working: WorkingState,
    budget: BudgetState,
    core: ReferenceLinearCore,
    contexts: Iterable[np.ndarray],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[EvidenceState, WorkingState, BudgetState, ExecutionAccounting]:
    """Run and account a sequence of V5-A reference internal steps.

    The single V5-A reference core counts as one active module invocation per
    internal step.  Later routing stages may report more or fewer active modules,
    but they must not reinterpret this baseline accounting retroactively.
    """

    if not callable(clock):
        raise TypeError("clock must be callable")
    context_list = list(contexts)
    started = float(clock())
    if not math.isfinite(started):
        raise ValueError("clock returned a non-finite start time")

    current_evidence = evidence
    current_working = working
    current_budget = budget
    for context in context_list:
        current_evidence, current_working, current_budget = reference_internal_step(
            current_evidence,
            current_working,
            current_budget,
            core,
            context,
        )

    ended = float(clock())
    if not math.isfinite(ended) or ended < started:
        raise ValueError("clock must return finite monotonic values")
    steps = len(context_list)
    accounting = ExecutionAccounting(
        internal_steps=steps,
        active_module_invocations=steps,
        max_active_modules_per_step=1 if steps else 0,
        wall_clock_seconds=ended - started,
    )
    return current_evidence, current_working, current_budget, accounting
