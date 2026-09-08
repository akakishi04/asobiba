"""Reproducible algebra checks, not a language-model or throughput benchmark."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import numpy as np

from fold_memory import QuadraticMemory


def chain_relations() -> QuadraticMemory:
    return (QuadraticMemory.zeros(("A", "B", "C"))
            .add_factor({"B": 1, "A": -1}, 2)
            .add_factor({"C": 1, "B": -1}, 3))


def run(seed: int = 20260909, trials: int = 100) -> dict:
    if trials <= 0:
        raise ValueError("trials must be positive.")
    rng = np.random.default_rng(seed)
    relations = chain_relations()
    summary = relations.fold(("A", "C"))
    initial = relations.add_factor({"A": 1}, 1)
    initial_folded = summary.add_factor({"A": 1}, 1)
    # Separate query contexts: replace the anchor, do NOT accumulate both.
    changed = relations.add_factor({"A": 1}, 4)
    changed_folded = summary.add_factor({"A": 1}, 4)

    names = tuple(f"x{i}" for i in range(10))
    boundary = ("x8", "x1", "x6")  # Noncanonical order tests indexing.
    boundary_indices = [names.index(name) for name in boundary]
    boundary_error = energy_error = 0.0
    for _ in range(trials):
        a = rng.normal(size=(14, 10))
        memory = QuadraticMemory(names, a.T @ a + np.eye(10),
                                 rng.normal(size=10), float(rng.normal()))
        folded = memory.fold(boundary)
        coefficients = dict(zip(boundary, rng.normal(size=3)))
        target, weight = float(rng.normal()), float(rng.uniform(0.1, 3))
        full_update = memory.add_factor(coefficients, target, weight)
        fold_update = folded.add_factor(coefficients, target, weight)
        boundary_error = max(boundary_error, float(np.max(np.abs(
            full_update.solve()[boundary_indices] - fold_update.solve()))))
        values = rng.normal(size=3)
        reconstructed = memory.conditional_state(boundary, values)
        energy_error = max(energy_error, abs(
            memory.energy(reconstructed) - folded.energy(values)))

    # Expected failure: an update to removed B changes the true boundary.
    anchored = relations.add_factor({"A": 1}, 1)
    stale = anchored.fold(("A", "C"))
    internal_update = anchored.add_factor({"B": 1}, 20, weight=2)
    interior_gap = float(np.max(np.abs(
        internal_update.solve()[[0, 2]] - stale.solve())))
    rejected = False
    try:
        stale.add_factor({"B": 1}, 20, weight=2)
    except KeyError:
        rejected = True

    # A star becomes a boundary clique: exact sparse storage can grow.
    leaves = tuple(f"leaf{i}" for i in range(8))
    star = QuadraticMemory.zeros(("hub",) + leaves)
    for leaf in leaves:
        star = star.add_factor({leaf: 1, "hub": -1}, 0)
    star = star.add_factor({"hub": 1}, 0)
    folded_star = star.fold(leaves)
    sparse_before = star.storage_stats()["J_nonzeros_exact"]
    sparse_after = folded_star.storage_stats()["J_nonzeros_exact"]

    checks = {
        "chain_initial": bool(np.allclose(initial_folded.solve(), [1, 6])),
        "chain_anchor_replacement": bool(np.allclose(changed_folded.solve(), [4, 9])),
        "random_boundary_error_below_1e-10": boundary_error < 1e-10,
        "random_energy_error_below_1e-10": energy_error < 1e-10,
        "removed_variable_update_rejected": rejected,
        "stale_summary_counterexample_detected": interior_gap > 1,
        "star_fill_in_detected": sparse_after > sparse_before,
    }
    return {
        "schema_version": 1,
        "scope": "quadratic-memory algebra only; no learned architecture or LLM comparison",
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "seed": seed,
        "trials": trials,
        "chain": {
            "initial_full": initial.solution(),
            "initial_folded": initial_folded.solution(),
            "replacement_full": changed.solution(),
            "replacement_folded": changed_folded.solution(),
            "relations_folded_J": summary.J.tolist(),
            "relations_folded_eta": summary.eta.tolist(),
            "relations_folded_c": summary.c,
            "full_storage": initial.storage_stats(),
            "folded_storage": initial_folded.storage_stats(),
        },
        "randomized": {
            "max_boundary_solution_abs_error": boundary_error,
            "max_profile_energy_abs_error": energy_error,
        },
        "interior_update_counterexample": {
            "updated_full_boundary": internal_update.solve()[[0, 2]].tolist(),
            "stale_folded_boundary": stale.solve().tolist(),
            "max_abs_gap": interior_gap,
            "folded_update_raises_key_error": rejected,
        },
        "fill_in_counterexample": {
            "full_storage": star.storage_stats(),
            "folded_storage": folded_star.storage_stats(),
            "note": "Dense payload shrinks here, but nonzero J entries increase.",
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.trials <= 0 or args.seed < 0:
        parser.error("--trials must be positive; --seed must be nonnegative")
    report = run(args.seed, args.trials)
    text = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
