"""Tests for the independently published retrieval/capsule components."""
import unittest
import numpy as np
import torch
from fold_reasoning.index import Record, StructuralIndex, unit
from fold_lm.capsule import compile_capsule


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            Record("near", "factory", "chain", (1, 0), (1, 0), ("shift",)),
            Record("far", "rhythm", "chain", (1, 0), (0, 1), ("shift",)),
            Record("incompatible", "rhythm", "queue", (1, 0), (-1, 0), ("shift",)),
        ]
        self.index = StructuralIndex(self.records)

    def test_structure_gate_before_novelty(self):
        hits, _ = self.index.search((1, 0), (1, 0), schema="chain")
        self.assertEqual([h.record.key for h in hits], ["far", "near"])

    def test_scan_cap(self):
        _, stats = self.index.search((1, 0), (1, 0), schema="chain", scan_limit=1)
        self.assertLessEqual(stats["bucket_entries_visited"], 1)
        self.assertLessEqual(stats["vectors_scored"], 1)

    def test_exact_counts_all_records(self):
        _, stats = self.index.search((1, 0), (1, 0), schema="chain", exact=True, scan_limit=1)
        self.assertEqual(stats["vectors_scored"], 3)

    def test_no_implicit_full_scan(self):
        hits, stats = self.index.search((-1, 0), (1, 0), schema="chain", probes=1)
        self.assertEqual(hits, [])
        self.assertEqual(stats["vectors_scored"], 0)

    def test_invalid_signatures(self):
        for a in ([0, 0], [1, np.nan], [], [[1, 0]]):
            with self.subTest(a=a), self.assertRaises(ValueError):
                unit(a)

    def test_mixed_dimensions_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            StructuralIndex([self.records[0], self.records[0]])
        with self.assertRaises(ValueError):
            self.index.search((1, 0, 0), (1, 0), schema="chain")

    def test_deterministic_build(self):
        other = StructuralIndex(self.records)
        self.assertEqual(other.fingerprint, self.index.fingerprint)

    def test_invalid_budget(self):
        with self.assertRaises(ValueError):
            self.index.search((1, 0), (1, 0), schema="chain", scan_limit=0)


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        g = torch.Generator().manual_seed(12)
        A = torch.randn(6, 6, generator=g, dtype=torch.float64)
        self.J = A.mT @ A + torch.eye(6, dtype=torch.float64)
        self.eta = torch.randn(6, generator=g, dtype=torch.float64)
        self.Q = torch.eye(6, dtype=torch.float64)[-2:]
        self.U = torch.eye(6, dtype=torch.float64)[:, :2]
        self.cap = compile_capsule(self.J, self.eta, self.Q, self.U)

    def test_batch_matches_full_system(self):
        W = torch.stack([torch.eye(2, dtype=torch.float64) * w for w in (0, .5, -.1)])
        b = torch.tensor([[1., 0], [0, 1], [-1, 2]], dtype=torch.float64)
        actual = self.cap.response(W, b)
        expected = torch.stack([self.Q @ torch.linalg.solve(
            self.J + self.U @ w @ self.U.mT, self.eta + self.U @ d) for w, d in zip(W, b)])
        torch.testing.assert_close(actual, expected, rtol=1e-10, atol=1e-10)

    def test_out_of_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "OUT_OF_SCOPE"):
            self.cap.response(torch.zeros(3, 3), torch.zeros(3))

    def test_unsafe_signed_update_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NUMERIC_UNSAFE"):
            self.cap.response(-100 * torch.eye(2, dtype=torch.float64), torch.zeros(2, dtype=torch.float64))

    def test_nonfinite_update_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NUMERIC_UNSAFE"):
            self.cap.response(torch.eye(2, dtype=torch.float64), torch.tensor([float("nan"), 0]))

    def test_autograd(self):
        eta = self.eta.clone().requires_grad_()
        W = torch.eye(2, dtype=torch.float64) * .1
        b = torch.ones(2, dtype=torch.float64)
        self.assertTrue(torch.autograd.gradcheck(
            lambda e: compile_capsule(self.J, e, self.Q, self.U).response(W, b), (eta,)))


if __name__ == "__main__":
    unittest.main()
