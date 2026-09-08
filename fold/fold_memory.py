"""FOLD's dense float64 reference kernel; not a trained language model."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _names(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("Pass a sequence of variable names, not a string.")
    result = tuple(values)
    if not result or any(not isinstance(x, str) or not x for x in result):
        raise ValueError("At least one nonempty variable name is required.")
    if len(set(result)) != len(result):
        raise ValueError("Variable names must be unique.")
    return result


def _array(value: ArrayLike, shape: tuple[int, ...], label: str) -> FloatArray:
    result = np.array(value, dtype=np.float64, copy=True)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{label} must be finite with shape {shape}.")
    return result


def _solve_spd(matrix: FloatArray, rhs: FloatArray) -> FloatArray:
    """Reject singular/indefinite systems rather than silently adding jitter."""
    try:
        lower = np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "A positive-definite system is required; add explicit anchors "
            "or regularization before this operation."
        ) from exc
    return np.linalg.solve(lower.T, np.linalg.solve(lower, rhs))


@dataclass(frozen=True, eq=False)
class QuadraticMemory:
    """E(z) = 0.5*z.T@J@z - eta.T@z + c, in the order given by names.

    Inputs are copied. Public arrays are read-only against accidental writes.
    Construction permits singular matrices while relations are assembled;
    solve() requires J positive definite and fold() requires J_II positive
    definite. No original factors or eliminated-variable recovery tape are kept.
    """

    names: tuple[str, ...]
    J: FloatArray
    eta: FloatArray
    c: float = 0.0

    def __post_init__(self) -> None:
        names = _names(self.names)
        n = len(names)
        matrix = _array(self.J, (n, n), "J")
        vector = _array(self.eta, (n,), "eta")
        constant = float(self.c)
        if not np.isfinite(constant):
            raise ValueError("c must be finite.")
        if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-12):
            raise ValueError("J must be symmetric.")
        # Remove roundoff asymmetry only; this is not sparsification.
        matrix = matrix * 0.5 + matrix.T * 0.5
        matrix.flags.writeable = False
        vector.flags.writeable = False
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "J", matrix)
        object.__setattr__(self, "eta", vector)
        object.__setattr__(self, "c", constant)

    @classmethod
    def zeros(cls, names: Sequence[str]) -> QuadraticMemory:
        ordered = _names(names)
        return cls(ordered, np.zeros((len(ordered), len(ordered))),
                   np.zeros(len(ordered)))

    def add_factor(
        self, coefficients: Mapping[str, float], target: float,
        weight: float = 1.0,
    ) -> QuadraticMemory:
        """Return a new memory with 0.5*weight*(a@z-target)**2 added.

        Adding another observation does NOT replace an earlier observation.
        Unknown/eliminated variables raise KeyError, rather than being ignored.
        """
        target, weight = float(target), float(weight)
        if not np.isfinite(target) or not np.isfinite(weight) or weight <= 0:
            raise ValueError("target must be finite and weight finite and positive.")
        if not coefficients:
            raise ValueError("A nonzero factor coefficient is required.")
        index = {name: i for i, name in enumerate(self.names)}
        a = np.zeros(len(self.names), dtype=np.float64)
        for name, coefficient in coefficients.items():
            if name not in index:
                raise KeyError(f"Unknown or eliminated variable: {name}")
            coefficient = float(coefficient)
            if not np.isfinite(coefficient):
                raise ValueError("Factor coefficients must be finite.")
            a[index[name]] = coefficient
        if not np.any(a):
            raise ValueError("A nonzero factor coefficient is required.")
        return QuadraticMemory(
            self.names, self.J + weight * np.outer(a, a),
            self.eta + weight * target * a,
            self.c + 0.5 * weight * target * target,
        )

    def solve(self) -> FloatArray:
        """Return the unique minimizer. No hard-constraint semantics are implied."""
        return _solve_spd(self.J, self.eta)

    def solution(self) -> dict[str, float]:
        return dict(zip(self.names, map(float, self.solve())))

    def energy(self, values: ArrayLike) -> float:
        z = _array(values, (len(self.names),), "values")
        return float(0.5 * z @ self.J @ z - self.eta @ z + self.c)

    def _partition(self, boundary: Sequence[str]) -> tuple[tuple[str, ...], list[int], list[int]]:
        ordered = _names(boundary)
        lookup = {name: i for i, name in enumerate(self.names)}
        unknown = set(ordered) - lookup.keys()
        if unknown:
            raise KeyError(f"Unknown boundary variables: {sorted(unknown)}")
        b = [lookup[name] for name in ordered]
        selected = set(b)
        interior = [i for i in range(len(self.names)) if i not in selected]
        return ordered, b, interior

    def fold(self, boundary: Sequence[str]) -> QuadraticMemory:
        """Minimize over the interior, preserving the requested boundary order.

        The returned energy equals min_interior E at every boundary point,
        up to floating-point error. Only future boundary-only additions preserve
        this equivalence. Dense fill-in is retained; no approximate pruning.
        """
        ordered, b, interior = self._partition(boundary)
        bb = np.ix_(b, b)
        if not interior:
            return QuadraticMemory(ordered, self.J[bb], self.eta[b], self.c)
        ii, ib, bi = (np.ix_(interior, interior), np.ix_(interior, b),
                      np.ix_(b, interior))
        # A single block RHS avoids explicitly forming an inverse.
        rhs = np.column_stack((self.J[ib], self.eta[interior]))
        solved = _solve_spd(self.J[ii], rhs)
        response, offset = solved[:, :-1], solved[:, -1]
        return QuadraticMemory(
            ordered, self.J[bb] - self.J[bi] @ response,
            self.eta[b] - self.J[bi] @ offset,
            self.c - 0.5 * float(self.eta[interior] @ offset),
        )

    def conditional_state(self, boundary: Sequence[str], values: ArrayLike) -> FloatArray:
        """Reference oracle using THIS original memory, not a folded-only read.

        Return argmin_interior E with the boundary clamped to values. Holding
        this object for recovery consumes original-memory storage and must be
        counted in any end-to-end memory benchmark.
        """
        ordered, b, interior = self._partition(boundary)
        z = np.zeros(len(self.names), dtype=np.float64)
        z[b] = _array(values, (len(ordered),), "boundary values")
        if interior:
            rhs = self.eta[interior] - self.J[np.ix_(interior, b)] @ z[b]
            z[interior] = _solve_spd(self.J[np.ix_(interior, interior)], rhs)
        return z

    def residual_norm(self, values: ArrayLike) -> float:
        z = _array(values, (len(self.names),), "values")
        return float(np.linalg.norm(self.J @ z - self.eta))

    def storage_stats(self) -> dict[str, int]:
        """Numeric payload only, NOT process RSS, peak memory, or speed."""
        return {
            "variables": len(self.names),
            "dense_numeric_scalars": int(self.J.size + self.eta.size + 1),
            "numeric_payload_bytes": int(self.J.nbytes + self.eta.nbytes + 8),
            "J_nonzeros_exact": int(np.count_nonzero(self.J)),
        }
