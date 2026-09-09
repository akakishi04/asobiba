"""Differentiable fixed-port response capsules (no explicit matrix inverse)."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from torch import Tensor


@dataclass
class ResponseCapsule:
    """Only port-coordinate updates are accepted; port selection is external.

    The four tensors preserve Q (J+UWU.T)^-1 (eta+Ub), not arbitrary reads.
    The compiler requires J SPD and U full column rank. Signed W is supported
    when the updated full system remains SPD. No implicit jitter or forgetting.
    """
    y0: Tensor
    g: Tensor
    V: Tensor
    K: Tensor

    def response(self, W: Tensor, b: Tensor, *, check: bool = True) -> Tensor:
        r = self.K.shape[-1]
        if W.ndim < 2 or b.ndim < 1 or W.shape[-2:] != (r, r) or b.shape[-1] != r:
            raise ValueError("OUT_OF_SCOPE: update must use the compiled port dimensions")
        eye = torch.eye(r, dtype=W.dtype, device=W.device)
        if check:
            if not all(torch.isfinite(t).all() for t in (W, b)):
                raise ValueError("NUMERIC_UNSAFE: nonfinite update")
            if not torch.allclose(W, W.mT):
                raise ValueError("NUMERIC_UNSAFE: W must be symmetric")
            L = torch.linalg.cholesky(self.K)
            # J+UWU.T is SPD iff I+L.T@W@L is SPD for full-rank U.
            _, info = torch.linalg.cholesky_ex(eye + L.mT @ W @ L)
            if torch.any(info != 0):
                raise ValueError("NUMERIC_UNSAFE: update would destroy positive definiteness")
        rhs = b.unsqueeze(-1) - W @ self.g.unsqueeze(-1)
        correction = torch.linalg.solve(eye + W @ self.K, rhs)
        return self.y0 + (self.V @ correction).squeeze(-1)


def compile_capsule(J: Tensor, eta: Tensor, Q: Tensor, U: Tensor,
                    *, check: bool = True) -> ResponseCapsule:
    """Compile shared/batched matrices. Autograd traverses both solves."""
    if J.ndim < 2 or eta.ndim < 1 or Q.ndim < 2 or U.ndim < 2:
        raise ValueError("Invalid tensor ranks")
    n = J.shape[-1]
    if (J.shape[-2:] != (n, n) or eta.shape[-1] != n
            or Q.shape[-1] != n or U.shape[-2] != n):
        raise ValueError("Invalid J/eta/Q/U dimensions")
    if check:
        if not all(torch.isfinite(t).all() for t in (J, eta, Q, U)):
            raise ValueError("NUMERIC_UNSAFE: nonfinite compiler input")
        if not torch.allclose(J, J.mT):
            raise ValueError("J must be symmetric")
        torch.linalg.cholesky(J)  # Deliberate failure, never silently regularize.
    mean = torch.linalg.solve(J, eta.unsqueeze(-1))
    transfer = torch.linalg.solve(J, U)
    capsule = ResponseCapsule(
        (Q @ mean).squeeze(-1), (U.mT @ mean).squeeze(-1),
        Q @ transfer, U.mT @ transfer,
    )
    if check:
        torch.linalg.cholesky(capsule.K)  # Full-column-rank U contract.
    return capsule
