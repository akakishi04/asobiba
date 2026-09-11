"""Exact V5-C serialization and resident-tensor accounting.

Earlier V5-C stages reported an estimated module-weight payload.  Gate C also
needs measured serialized bytes and an explicit view of resident representation
costs.  This module defines one deterministic little-endian reference format for
``CompressedModuleInitializations`` and keeps three quantities separate:

- serialized bytes: the actual ``len(blob)`` including format metadata;
- compact resident tensor bytes: float32 continuous values, minimally sized
  unpacked integer codes, uint32 correction coordinates, float32 corrections;
- current reference runtime tensor bytes: the tensors held by
  ``DirectCompressedLinearBank`` today (int64 codes/coordinates).

Python object overhead is deliberately not called resident tensor storage.  The
reference-runtime count is instead an exact dtype/element accounting for tensors
owned by the compressed Linear banks.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

import numpy as np

from .accounting import code_bits_per_index
from .compressed_runtime import CompressedModuleInitializations
from .compression_init import (
    CompressionInitialization,
    InitializationAccounting,
    ReconstructionMetrics,
)
from .compression_v5c import BlockCodebookTemplate, EncodedBlockWeight


_ROLE_MAGIC = b"F5CR"
_PAIR_MAGIC = b"F5CP"
_VERSION = 1
_ROLE_HEADER = struct.Struct("<4sB3xIIIIIII")
_PAIR_HEADER = struct.Struct("<4sB3xII")
_MODULE_META = struct.Struct("<IIf")
_CORRECTION_ENTRY = struct.Struct("<IIf")


@dataclass(frozen=True)
class RoleSerializationAccounting:
    dense_float32_bytes: int
    continuous_payload_bytes: int
    discrete_code_bits: int
    discrete_code_bytes: int
    correction_payload_bytes: int
    metadata_bytes: int
    serialized_bytes: int
    compact_resident_tensor_bytes: int
    reference_runtime_tensor_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "dense_float32_bytes",
            "continuous_payload_bytes",
            "discrete_code_bits",
            "discrete_code_bytes",
            "correction_payload_bytes",
            "metadata_bytes",
            "serialized_bytes",
            "compact_resident_tensor_bytes",
            "reference_runtime_tensor_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.dense_float32_bytes <= 0:
            raise ValueError("dense_float32_bytes must be positive")
        if self.serialized_bytes != (
            self.continuous_payload_bytes
            + self.discrete_code_bytes
            + self.correction_payload_bytes
            + self.metadata_bytes
        ):
            raise ValueError("serialized byte accounting does not sum exactly")

    @property
    def serialized_ratio(self) -> float:
        return self.serialized_bytes / self.dense_float32_bytes

    @property
    def compact_resident_ratio(self) -> float:
        return self.compact_resident_tensor_bytes / self.dense_float32_bytes

    @property
    def reference_runtime_resident_ratio(self) -> float:
        return self.reference_runtime_tensor_bytes / self.dense_float32_bytes


@dataclass(frozen=True)
class ModuleSerializationAccounting:
    up: RoleSerializationAccounting
    down: RoleSerializationAccounting
    pair_metadata_bytes: int
    dense_float32_bytes: int
    serialized_bytes: int
    compact_resident_tensor_bytes: int
    reference_runtime_tensor_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.up, RoleSerializationAccounting) or not isinstance(
            self.down, RoleSerializationAccounting
        ):
            raise TypeError("up/down must be RoleSerializationAccounting")
        if type(self.pair_metadata_bytes) is not int or self.pair_metadata_bytes < 0:
            raise ValueError("pair_metadata_bytes must be nonnegative")
        expected_dense = self.up.dense_float32_bytes + self.down.dense_float32_bytes
        expected_serialized = (
            self.pair_metadata_bytes + self.up.serialized_bytes + self.down.serialized_bytes
        )
        expected_compact = (
            self.up.compact_resident_tensor_bytes + self.down.compact_resident_tensor_bytes
        )
        expected_reference = (
            self.up.reference_runtime_tensor_bytes + self.down.reference_runtime_tensor_bytes
        )
        if self.dense_float32_bytes != expected_dense:
            raise ValueError("dense module byte accounting mismatch")
        if self.serialized_bytes != expected_serialized:
            raise ValueError("serialized module byte accounting mismatch")
        if self.compact_resident_tensor_bytes != expected_compact:
            raise ValueError("compact resident byte accounting mismatch")
        if self.reference_runtime_tensor_bytes != expected_reference:
            raise ValueError("reference runtime resident byte accounting mismatch")

    @property
    def serialized_ratio(self) -> float:
        return self.serialized_bytes / self.dense_float32_bytes

    @property
    def compact_resident_ratio(self) -> float:
        return self.compact_resident_tensor_bytes / self.dense_float32_bytes

    @property
    def reference_runtime_resident_ratio(self) -> float:
        return self.reference_runtime_tensor_bytes / self.dense_float32_bytes


def _validate_role(initialization: CompressionInitialization) -> None:
    if not isinstance(initialization, CompressionInitialization):
        raise TypeError("initialization must be CompressionInitialization")
    template = initialization.template
    module_count = len(initialization.encoded_weights)
    if module_count <= 0:
        raise ValueError("role must contain at least one module")
    for encoded in initialization.encoded_weights:
        if encoded.template is not template:
            raise ValueError("all encoded weights must share one template")
        if template.output_width > 0xFFFFFFFF or template.input_width > 0xFFFFFFFF:
            raise ValueError("matrix dimensions exceed uint32 serialization limits")
        if encoded.max_correction_entries > 0xFFFFFFFF:
            raise ValueError("max_correction_entries exceeds uint32 serialization limit")
        if encoded.correction_nnz > 0xFFFFFFFF:
            raise ValueError("correction count exceeds uint32 serialization limit")
        if not math.isfinite(float(encoded.max_abs_correction)):
            raise ValueError("max_abs_correction must be finite")
        if encoded.correction_indices.size:
            if np.max(encoded.correction_indices) > 0xFFFFFFFF:
                raise ValueError("correction coordinate exceeds uint32 serialization limit")


def _pack_codes(codes: np.ndarray, bits_per_code: int) -> bytes:
    flat = np.asarray(codes, dtype=np.int64).reshape(-1)
    if bits_per_code == 0:
        if np.any(flat != 0):
            raise ValueError("zero-bit codebooks can only encode code zero")
        return b""
    accumulator = 0
    used_bits = 0
    output = bytearray()
    for code in flat:
        accumulator |= int(code) << used_bits
        used_bits += bits_per_code
        while used_bits >= 8:
            output.append(accumulator & 0xFF)
            accumulator >>= 8
            used_bits -= 8
    if used_bits:
        output.append(accumulator & 0xFF)
    return bytes(output)


def _unpack_codes(blob: memoryview, count: int, bits_per_code: int) -> np.ndarray:
    if type(count) is not int or count < 0:
        raise ValueError("code count must be nonnegative")
    if bits_per_code == 0:
        return np.zeros((count,), dtype=np.int64)
    mask = (1 << bits_per_code) - 1
    result = np.empty((count,), dtype=np.int64)
    accumulator = 0
    available = 0
    byte_index = 0
    for index in range(count):
        while available < bits_per_code:
            if byte_index >= len(blob):
                raise ValueError("truncated packed code stream")
            accumulator |= int(blob[byte_index]) << available
            available += 8
            byte_index += 1
        result[index] = accumulator & mask
        accumulator >>= bits_per_code
        available -= bits_per_code
    return result


def _compact_code_itemsize(entries: int) -> int:
    if entries <= 0:
        raise ValueError("entries must be positive")
    if entries <= 0x100:
        return 1
    if entries <= 0x10000:
        return 2
    if entries <= 0x100000000:
        return 4
    raise ValueError("entries exceed uint32 compact resident limit")


def accounting_for_role(initialization: CompressionInitialization) -> RoleSerializationAccounting:
    _validate_role(initialization)
    template = initialization.template
    modules = len(initialization.encoded_weights)
    continuous_scalars = int(template.base.size + template.codebooks.size)
    continuous_bytes = continuous_scalars * 4
    code_count = int(
        modules
        * template.grid_rows
        * template.grid_cols
        * template.codebook_count
    )
    bits_per_code = code_bits_per_index(template.entries_per_codebook)
    code_bits = code_count * bits_per_code
    code_bytes = (code_bits + 7) // 8
    correction_nnz = sum(item.correction_nnz for item in initialization.encoded_weights)
    correction_bytes = correction_nnz * _CORRECTION_ENTRY.size
    metadata_bytes = _ROLE_HEADER.size + modules * _MODULE_META.size
    serialized_bytes = continuous_bytes + code_bytes + correction_bytes + metadata_bytes

    compact_codes = code_count * _compact_code_itemsize(template.entries_per_codebook)
    compact_corrections = correction_nnz * (4 + 4 + 4)
    compact_resident = continuous_bytes + compact_codes + compact_corrections

    # DirectCompressedLinearBank currently stores codes and coordinates as
    # torch.int64 while base/codebooks/correction values are float32.
    reference_codes = code_count * 8
    reference_corrections = correction_nnz * (8 + 8 + 4)
    reference_resident = continuous_bytes + reference_codes + reference_corrections

    return RoleSerializationAccounting(
        dense_float32_bytes=int(
            modules * template.output_width * template.input_width * 4
        ),
        continuous_payload_bytes=continuous_bytes,
        discrete_code_bits=code_bits,
        discrete_code_bytes=code_bytes,
        correction_payload_bytes=correction_bytes,
        metadata_bytes=metadata_bytes,
        serialized_bytes=serialized_bytes,
        compact_resident_tensor_bytes=compact_resident,
        reference_runtime_tensor_bytes=reference_resident,
    )


def serialize_role(initialization: CompressionInitialization) -> bytes:
    """Serialize one same-role module bank in a deterministic compact format."""
    _validate_role(initialization)
    template = initialization.template
    modules = len(initialization.encoded_weights)
    header = _ROLE_HEADER.pack(
        _ROLE_MAGIC,
        _VERSION,
        template.output_width,
        template.input_width,
        template.block_rows,
        template.block_cols,
        template.codebook_count,
        template.entries_per_codebook,
        modules,
    )
    module_meta = bytearray()
    for encoded in initialization.encoded_weights:
        module_meta.extend(
            _MODULE_META.pack(
                encoded.correction_nnz,
                encoded.max_correction_entries,
                float(encoded.max_abs_correction),
            )
        )
    base_bytes = np.asarray(template.base, dtype="<f4").tobytes(order="C")
    codebook_bytes = np.asarray(template.codebooks, dtype="<f4").tobytes(order="C")
    codes = np.stack([item.codes for item in initialization.encoded_weights], axis=0)
    bits_per_code = code_bits_per_index(template.entries_per_codebook)
    code_bytes = _pack_codes(codes, bits_per_code)

    corrections = bytearray()
    for encoded in initialization.encoded_weights:
        for (row, col), value in zip(
            encoded.correction_indices, encoded.correction_values
        ):
            corrections.extend(
                _CORRECTION_ENTRY.pack(int(row), int(col), float(value))
            )

    blob = bytes(header + module_meta + base_bytes + codebook_bytes + code_bytes + corrections)
    expected = accounting_for_role(initialization).serialized_bytes
    if len(blob) != expected:
        raise RuntimeError("V5-C role serializer/accounting byte count mismatch")
    return blob


def deserialize_role(blob: bytes) -> CompressionInitialization:
    """Deserialize a role blob and reconstruct the runtime-neutral representation."""
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        raise TypeError("blob must be bytes-like")
    view = memoryview(blob)
    if len(view) < _ROLE_HEADER.size:
        raise ValueError("truncated V5-C role header")
    (
        magic,
        version,
        output_width,
        input_width,
        block_rows,
        block_cols,
        q_count,
        entries,
        modules,
    ) = _ROLE_HEADER.unpack(view[: _ROLE_HEADER.size])
    if magic != _ROLE_MAGIC or version != _VERSION:
        raise ValueError("unsupported V5-C role serialization format")
    if any(value <= 0 for value in (output_width, input_width, block_rows, block_cols, q_count, entries, modules)):
        raise ValueError("serialized dimensions must be positive")
    if output_width % block_rows or input_width % block_cols:
        raise ValueError("serialized block shape does not divide matrix shape")

    offset = _ROLE_HEADER.size
    metas: list[tuple[int, int, float]] = []
    for _ in range(modules):
        end = offset + _MODULE_META.size
        if end > len(view):
            raise ValueError("truncated V5-C module metadata")
        nnz, max_entries, max_abs = _MODULE_META.unpack(view[offset:end])
        if not math.isfinite(float(max_abs)) or max_abs < 0.0:
            raise ValueError("invalid serialized correction bound")
        metas.append((int(nnz), int(max_entries), float(max_abs)))
        offset = end

    base_count = output_width * input_width
    base_bytes = base_count * 4
    end = offset + base_bytes
    if end > len(view):
        raise ValueError("truncated V5-C base payload")
    base = np.frombuffer(view[offset:end], dtype="<f4").astype(np.float64).reshape(
        output_width, input_width
    )
    offset = end

    codebook_count = q_count * entries * block_rows * block_cols
    codebook_bytes = codebook_count * 4
    end = offset + codebook_bytes
    if end > len(view):
        raise ValueError("truncated V5-C codebook payload")
    codebooks = np.frombuffer(view[offset:end], dtype="<f4").astype(np.float64).reshape(
        q_count, entries, block_rows, block_cols
    )
    offset = end

    grid_rows = output_width // block_rows
    grid_cols = input_width // block_cols
    total_codes = modules * grid_rows * grid_cols * q_count
    bits_per_code = code_bits_per_index(entries)
    packed_code_bytes = (total_codes * bits_per_code + 7) // 8
    end = offset + packed_code_bytes
    if end > len(view):
        raise ValueError("truncated V5-C packed codes")
    flat_codes = _unpack_codes(view[offset:end], total_codes, bits_per_code)
    if np.any(flat_codes >= entries):
        raise ValueError("serialized code index out of range")
    codes = flat_codes.reshape(modules, grid_rows, grid_cols, q_count)
    offset = end

    template = BlockCodebookTemplate(
        base=base,
        codebooks=codebooks,
        block_rows=block_rows,
        block_cols=block_cols,
    )
    encoded_weights: list[EncodedBlockWeight] = []
    total_nnz = 0
    for module_index, (nnz, max_entries, max_abs) in enumerate(metas):
        indices = np.empty((nnz, 2), dtype=np.int64)
        values = np.empty((nnz,), dtype=np.float64)
        for entry in range(nnz):
            end = offset + _CORRECTION_ENTRY.size
            if end > len(view):
                raise ValueError("truncated V5-C correction payload")
            row, col, value = _CORRECTION_ENTRY.unpack(view[offset:end])
            indices[entry] = (int(row), int(col))
            values[entry] = float(value)
            offset = end
        encoded_weights.append(
            EncodedBlockWeight(
                template=template,
                codes=codes[module_index],
                correction_indices=indices,
                correction_values=values,
                max_correction_entries=max_entries,
                max_abs_correction=max_abs,
            )
        )
        total_nnz += nnz
    if offset != len(view):
        raise ValueError("unexpected trailing bytes in V5-C role blob")

    dense_bytes = modules * output_width * input_width * 4
    shared_bytes = int((template.base.size + template.codebooks.size) * 4)
    code_bits = total_codes * bits_per_code
    code_bytes = (code_bits + 7) // 8
    correction_bytes = total_nnz * _CORRECTION_ENTRY.size
    accounting = InitializationAccounting(
        dense_float32_bytes=dense_bytes,
        shared_continuous_float32_bytes=shared_bytes,
        discrete_code_bits=code_bits,
        discrete_code_bytes=code_bytes,
        correction_payload_bytes=correction_bytes,
        estimated_encoded_payload_bytes=shared_bytes + code_bytes + correction_bytes,
    )
    metrics = tuple(
        ReconstructionMetrics(
            rmse=0.0,
            max_abs_error=0.0,
            correction_nnz=item.correction_nnz,
            correction_density=item.correction_density,
        )
        for item in encoded_weights
    )
    result = CompressionInitialization(
        template=template,
        encoded_weights=tuple(encoded_weights),
        metrics=metrics,
        accounting=accounting,
    )
    # Ensures parser interpretation and actual blob length agree exactly.
    if accounting_for_role(result).serialized_bytes != len(view):
        raise ValueError("serialized role byte count is inconsistent with decoded metadata")
    return result


def accounting_for_modules(
    initializations: CompressedModuleInitializations,
) -> ModuleSerializationAccounting:
    if not isinstance(initializations, CompressedModuleInitializations):
        raise TypeError("initializations must be CompressedModuleInitializations")
    up = accounting_for_role(initializations.up)
    down = accounting_for_role(initializations.down)
    return ModuleSerializationAccounting(
        up=up,
        down=down,
        pair_metadata_bytes=_PAIR_HEADER.size,
        dense_float32_bytes=up.dense_float32_bytes + down.dense_float32_bytes,
        serialized_bytes=_PAIR_HEADER.size + up.serialized_bytes + down.serialized_bytes,
        compact_resident_tensor_bytes=(
            up.compact_resident_tensor_bytes + down.compact_resident_tensor_bytes
        ),
        reference_runtime_tensor_bytes=(
            up.reference_runtime_tensor_bytes + down.reference_runtime_tensor_bytes
        ),
    )


def serialize_module_initializations(initializations: CompressedModuleInitializations) -> bytes:
    if not isinstance(initializations, CompressedModuleInitializations):
        raise TypeError("initializations must be CompressedModuleInitializations")
    up_blob = serialize_role(initializations.up)
    down_blob = serialize_role(initializations.down)
    header = _PAIR_HEADER.pack(_PAIR_MAGIC, _VERSION, len(up_blob), len(down_blob))
    blob = header + up_blob + down_blob
    expected = accounting_for_modules(initializations).serialized_bytes
    if len(blob) != expected:
        raise RuntimeError("V5-C module serializer/accounting byte count mismatch")
    return blob


def deserialize_module_initializations(blob: bytes) -> CompressedModuleInitializations:
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        raise TypeError("blob must be bytes-like")
    view = memoryview(blob)
    if len(view) < _PAIR_HEADER.size:
        raise ValueError("truncated V5-C module header")
    magic, version, up_size, down_size = _PAIR_HEADER.unpack(view[: _PAIR_HEADER.size])
    if magic != _PAIR_MAGIC or version != _VERSION:
        raise ValueError("unsupported V5-C module serialization format")
    expected = _PAIR_HEADER.size + up_size + down_size
    if expected != len(view):
        raise ValueError("V5-C module blob length does not match header")
    offset = _PAIR_HEADER.size
    up = deserialize_role(view[offset : offset + up_size])
    offset += up_size
    down = deserialize_role(view[offset : offset + down_size])
    return CompressedModuleInitializations(up=up, down=down)
