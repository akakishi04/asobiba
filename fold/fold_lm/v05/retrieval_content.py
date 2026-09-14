from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class SharedRetrievalContentHead(nn.Module):
    """Shared query/record encoder for content-addressed retrieval selection.

    The head does not have a fixed output class count. Query features and an
    arbitrary candidate set of record-descriptor features are encoded by the
    same residual network, then compared by cosine-equivalent dot product.
    """

    def __init__(
        self,
        *,
        feature_dim: int = 128,
        hidden_dim: int = 32,
        residual_scale: float = 0.25,
    ) -> None:
        super().__init__()
        if type(feature_dim) is not int or feature_dim <= 0:
            raise ValueError("feature_dim must be a positive integer")
        if type(hidden_dim) is not int or hidden_dim <= 0:
            raise ValueError("hidden_dim must be a positive integer")
        residual_scale = float(residual_scale)
        if not 0.0 <= residual_scale <= 1.0:
            raise ValueError("residual_scale must be in [0, 1]")
        self.feature_dim = feature_dim
        self.residual_scale = residual_scale
        self.network = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, feature_dim),
        )

    def encode(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 2 or features.shape[-1] != self.feature_dim:
            raise ValueError("features must have shape [batch, feature_dim]")
        mixed = features + self.residual_scale * self.network(features)
        return F.normalize(mixed, dim=-1)

    def scores(self, query_features: torch.Tensor, record_features: torch.Tensor) -> torch.Tensor:
        if query_features.device != record_features.device:
            raise ValueError("query and record features must share a device")
        query = self.encode(query_features)
        records = self.encode(record_features)
        return query @ records.transpose(0, 1)

    def select(self, query_features: torch.Tensor, record_features: torch.Tensor) -> torch.Tensor:
        """Return candidate indices for each query; candidate count is dynamic."""
        return self.scores(query_features, record_features).argmax(dim=-1)
