"""V5-A storage accounting and deterministic serialization reference.

The reference deliberately distinguishes independent continuous scalars,
theoretical discrete-code bits, and actual serialized bytes.  It is not a V5-C
production format; it exists so later formats cannot hide code, metadata, or
float payload costs.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

import numpy as np

from .compression import AdditiveCodebookWeight


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
