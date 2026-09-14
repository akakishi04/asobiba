from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

import torch
from torch import nn

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def hashed_text_features(
    texts: Sequence[str],
    *,
    feature_dim: int = 64,
    device: torch.device | str | None = None,
) -> torch.Tensor:
    """Deterministic signed feature hashing for small retrieval-query text.

    This is a lightweight text front end for the V5-E query-address head. It is
    not a general language encoder and does not contain corpus evidence values.
    """
    if type(feature_dim) is not int or feature_dim <= 0:
        raise ValueError("feature_dim must be a positive integer")
    if isinstance(texts, (str, bytes)):
        raise TypeError("texts must be a sequence of strings")
    rows: list[list[float]] = []
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("query text must be a non-empty string")
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            raise ValueError("query text must contain alphanumeric tokens")
        row = [0.0] * feature_dim
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % feature_dim
            sign = -1.0 if (digest[4] & 1) else 1.0
            row[index] += sign
        scale = math.sqrt(sum(value * value for value in row))
        if scale == 0.0:
            raise RuntimeError("hashed query feature norm is zero")
        rows.append([value / scale for value in row])
    return torch.tensor(rows, dtype=torch.float32, device=device)


class RetrievalAddressHead(nn.Module):
    """Small learned head mapping query features to a discrete retrieval address."""

    def __init__(self, *, feature_dim: int = 64, hidden_dim: int = 32, address_count: int = 8):
        super().__init__()
        for name, value in (
            ("feature_dim", feature_dim),
            ("hidden_dim", hidden_dim),
            ("address_count", address_count),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.feature_dim = feature_dim
        self.address_count = address_count
        self.network = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, address_count),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 2 or features.shape[-1] != self.feature_dim:
            raise ValueError("features must have shape [batch, feature_dim]")
        return self.network(features)


def address_to_structure(address: int, *, address_count: int = 8) -> tuple[float, ...]:
    if type(address_count) is not int or address_count <= 0:
        raise ValueError("address_count must be a positive integer")
    if type(address) is not int or not 0 <= address < address_count:
        raise ValueError("address is out of range")
    return tuple(1.0 if i == address else 0.0 for i in range(address_count))
