"""Positive properties and explicit limits of the quadratic reference kernel."""
from __future__ import annotations

import unittest

import numpy as np
from numpy.testing import assert_allclose

from demo import chain_relations, run
from fold_memory import QuadraticMemory


class FoldMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.relations = chain_relations()
        self.anchored = self.relations.add_factor({"A": 1}, 1)

    def test_factor_energy_matches_original_residuals(self) -> None:
        z = np.array([2.0, -1.0, 8.0])
        expected = 0.5 * ((z[1] - z[0] - 2) ** 2
                          + (z[2] - z[1] - 3) ** 2 + (z[0] - 1) ** 2)
        self.assertAlmostEqual(self.anchored.energy(z), expected)

    def test_chain_solution(self) -> None:
        assert_allclose(self.anchored.solve(), [1, 3, 6], atol=1e-12)
        self.assertEqual(tuple(self.anchored.solution()), ("A", "B", "C"))

    def test_fold_preserves_relation_weight_and_constant(self) -> None:
        folded = self.relations.fold(("A", "C"))
        assert_allclose(folded.J, [[0.5, -0.5], [-0.5, 0.5]], atol=1e-12)
        assert_allclose(folded.eta, [-2.5, 2.5], atol=1e-12)
        self.assertAlmostEqual(folded.c, 6.25)
        self.assertAlmostEqual(folded.energy([2, 10]), 0.25 * (10 - 2 - 5) ** 2)

    def test_folded_solution_matches_full(self) -> None:
        assert_allclose(self.anchored.fold(("A", "C")).solve(),
                        self.anchored.solve()[[0, 2]], atol=1e-12)

    def test_anchor_replacement_uses_separate_context(self) -> None:
        folded = self.relations.fold(("A", "C"))
        assert_allclose(folded.add_factor({"A": 1}, 1).solve(), [1, 6], atol=1e-12)
        assert_allclose(folded.add_factor({"A": 1}, 4).solve(), [4, 9], atol=1e-12)
        # Adding an anchor to the already anchored graph accumulates evidence.
        assert_allclose(self.anchored.add_factor({"A": 1}, 4).solve(),
                        [2.5, 4.5, 7.5], atol=1e-12)

    def test_boundary_update_equivalence_random(self) -> None:
        rng = np.random.default_rng(729)
        names = tuple(f"x{i}" for i in range(8))
        boundary = ("x6", "x1", "x4")
        for _ in range(100):
            a = rng.normal(size=(10, 8))
            original = QuadraticMemory(names, a.T @ a + np.eye(8), rng.normal(size=8))
            coefficients = dict(zip(boundary, rng.normal(size=3)))
            target = float(rng.normal())
            weight = float(rng.uniform(0.1, 4))
            full = original.add_factor(coefficients, target, weight)
            folded = original.fold(boundary).add_factor(coefficients, target, weight)
            assert_allclose(folded.solve(), full.solve()[[6, 1, 4]], rtol=1e-10, atol=1e-10)

    def test_profile_energy_for_arbitrary_boundary_values(self) -> None:
        rng = np.random.default_rng(16)
        a = rng.normal(size=(9, 6))
        original = QuadraticMemory(tuple("abcdef"), a.T @ a + np.eye(6),
                                   rng.normal(size=6), c=3.7)
        folded = original.fold(("e", "b"))
        for _ in range(50):
            values = rng.normal(size=2)
            z = original.conditional_state(("e", "b"), values)
            self.assertAlmostEqual(folded.energy(values), original.energy(z), places=10)

    def test_conditional_state_is_original_memory_oracle(self) -> None:
        assert_allclose(self.anchored.conditional_state(("A", "C"), [1, 7]),
                        [1, 3.5, 7], atol=1e-12)

    def test_elimination_associativity(self) -> None:
        rng = np.random.default_rng(2026)
        a = rng.normal(size=(10, 6))
        memory = QuadraticMemory(tuple("abcdef"), a.T @ a + np.eye(6),
                                 rng.normal(size=6), c=7.0)
        direct = memory.fold(("f", "b"))
        staged = memory.fold(("b", "d", "f", "a")).fold(("f", "b"))
        assert_allclose(staged.J, direct.J, atol=1e-12)
        assert_allclose(staged.eta, direct.eta, atol=1e-12)
        self.assertAlmostEqual(staged.c, direct.c)

    def test_boundary_permutation(self) -> None:
        folded = self.anchored.fold(("C", "A"))
        self.assertEqual(folded.names, ("C", "A"))
        assert_allclose(folded.solve(), [6, 1], atol=1e-12)

    def test_keep_all_and_reorder(self) -> None:
        folded = self.anchored.fold(("C", "B", "A"))
        assert_allclose(folded.solve(), [6, 3, 1], atol=1e-12)
        self.assertAlmostEqual(folded.c, self.anchored.c)

    def test_keep_one(self) -> None:
        folded = self.anchored.fold(("C",))
        assert_allclose(folded.solve(), [6], atol=1e-12)

    def test_invalid_boundary_rejected(self) -> None:
        for bad in ((), ("A", "A"), "AC"):
            with self.subTest(boundary=bad), self.assertRaises(ValueError):
                self.anchored.fold(bad)
        with self.assertRaises(KeyError):
            self.anchored.fold(("missing",))

    def test_singular_solve_rejected(self) -> None:
        with self.assertRaises(ValueError):
            QuadraticMemory.zeros(("A",)).solve()

    def test_singular_interior_rejected(self) -> None:
        with self.assertRaises(ValueError):
            QuadraticMemory.zeros(("A", "B")).fold(("A",))

    def test_indefinite_solve_rejected(self) -> None:
        with self.assertRaises(ValueError):
            QuadraticMemory(("A", "B"), np.diag([1.0, -1.0]), np.zeros(2)).solve()

    def test_invalid_matrix_shapes_symmetry_and_finiteness(self) -> None:
        for matrix, eta, c in (
            (np.eye(3), np.zeros(2), 0),
            ([[1, 2], [0, 1]], np.zeros(2), 0),
            ([[1, 0], [0, np.nan]], np.zeros(2), 0),
            (np.eye(2), [0, np.inf], 0),
            (np.eye(2), np.zeros(2), np.inf),
        ):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                QuadraticMemory(("A", "B"), matrix, eta, c)

    def test_invalid_names(self) -> None:
        for names in ((), ("A", "A"), ("",), (1,), "AB"):
            with self.subTest(names=names), self.assertRaises(ValueError):
                QuadraticMemory.zeros(names)

    def test_invalid_factors(self) -> None:
        for weight in (0, -1, np.inf, np.nan):
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                self.anchored.add_factor({"A": 1}, 0, weight)
        for coefficients, target in (({}, 0), ({"A": 0}, 0),
                                     ({"A": np.nan}, 0), ({"A": 1}, np.inf)):
            with self.subTest(coefficients=coefficients), self.assertRaises(ValueError):
                self.anchored.add_factor(coefficients, target)

    def test_eliminated_variable_write_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self.anchored.fold(("A", "C")).add_factor({"B": 1}, 20)

    def test_interior_update_invalidates_stale_summary(self) -> None:
        stale = self.anchored.fold(("A", "C"))
        changed = self.anchored.add_factor({"B": 1}, 20, weight=2)
        self.assertGreater(float(np.max(np.abs(changed.solve()[[0, 2]] - stale.solve()))), 1)

    def test_fill_in_can_increase_nonzero_count(self) -> None:
        leaves = tuple(f"l{i}" for i in range(8))
        star = QuadraticMemory.zeros(("hub",) + leaves)
        for leaf in leaves:
            star = star.add_factor({leaf: 1, "hub": -1}, 0)
        star = star.add_factor({"hub": 1}, 0)
        folded = star.fold(leaves)
        self.assertEqual(star.storage_stats()["J_nonzeros_exact"], 25)
        self.assertEqual(folded.storage_stats()["J_nonzeros_exact"], 64)

    def test_no_hidden_original_graph_in_folded_memory(self) -> None:
        folded = self.anchored.fold(("A", "C"))
        self.assertEqual(set(vars(folded)), {"names", "J", "eta", "c"})
        self.assertEqual(folded.storage_stats()["numeric_payload_bytes"], 56)

    def test_inputs_are_copied_and_arrays_read_only(self) -> None:
        matrix, eta = np.eye(2), np.ones(2)
        memory = QuadraticMemory(("A", "B"), matrix, eta)
        matrix[0, 0] = 10
        eta[0] = 10
        assert_allclose(memory.solve(), [1, 1])
        with self.assertRaises(ValueError):
            memory.J[0, 0] = 2
        old = self.anchored.J.copy()
        self.anchored.add_factor({"A": 1}, 3)
        self.anchored.fold(("A", "C"))
        assert_allclose(self.anchored.J, old)

    def test_invalid_query_shapes_and_values(self) -> None:
        with self.assertRaises(ValueError):
            self.anchored.energy([1, 2])
        with self.assertRaises(ValueError):
            self.anchored.conditional_state(("A", "C"), [1, np.nan])
        with self.assertRaises(ValueError):
            self.anchored.residual_norm([1, np.nan, 2])

    def test_implicit_response_matches_finite_difference(self) -> None:
        rng = np.random.default_rng(30)
        a = rng.normal(size=(4, 4))
        j = a.T @ a + 2 * np.eye(4)
        eta, deta = rng.normal(size=4), rng.normal(size=4)
        direction = rng.normal(size=(4, 4))
        dj = (direction + direction.T) / 2
        memory = QuadraticMemory(tuple("abcd"), j, eta)
        expected = np.linalg.solve(j, deta - dj @ memory.solve())
        eps = 1e-5
        plus = QuadraticMemory(memory.names, j + eps * dj, eta + eps * deta)
        minus = QuadraticMemory(memory.names, j - eps * dj, eta - eps * deta)
        assert_allclose((plus.solve() - minus.solve()) / (2 * eps), expected,
                        rtol=1e-7, atol=1e-8)

    def test_residual_bound_with_known_spectral_floor(self) -> None:
        memory = QuadraticMemory(("A", "B"), np.diag([2.0, 5.0]), [3.0, 7.0])
        estimate = np.array([-1.0, 2.0])
        error = float(np.linalg.norm(estimate - memory.solve()))
        self.assertLessEqual(error, memory.residual_norm(estimate) / 2.0 + 1e-12)

    def test_demo_report_contract(self) -> None:
        report = run(seed=42, trials=10)
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["checks"].values()))
        with self.assertRaises(ValueError):
            run(trials=0)


if __name__ == "__main__":
    unittest.main()
