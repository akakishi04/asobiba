from __future__ import annotations

import unittest

import torch

from fold_lm.v05.autograd_reference import fixed_code_loss, materialize_fixed_codes


class V05AutogradReferenceTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.base = torch.tensor(
            [[0.20, -0.10], [0.05, 0.30]], dtype=torch.float64, requires_grad=True
        )
        self.codebook = torch.tensor(
            [
                [
                    [[0.01, 0.02], [-0.03, 0.04]],
                    [[-0.02, 0.01], [0.02, -0.01]],
                ],
                [
                    [[0.03, -0.01], [0.00, 0.02]],
                    [[-0.01, -0.02], [0.01, 0.03]],
                ],
            ],
            dtype=torch.float64,
            requires_grad=True,
        )
        self.codes = torch.tensor([1, 0], dtype=torch.int64)
        self.inputs = torch.tensor([[1.0, 2.0], [-0.5, 0.25]], dtype=torch.float64)
        self.target = torch.tensor([[0.1, -0.2], [0.3, 0.4]], dtype=torch.float64)

    def _finite_difference(self, tensor: torch.Tensor, index: tuple[int, ...], eps: float = 1e-6) -> float:
        with torch.no_grad():
            original = float(tensor[index])
            tensor[index] = original + eps
        plus = float(fixed_code_loss(self.base, self.codebook, self.codes, self.inputs, self.target))
        with torch.no_grad():
            tensor[index] = original - eps
        minus = float(fixed_code_loss(self.base, self.codebook, self.codes, self.inputs, self.target))
        with torch.no_grad():
            tensor[index] = original
        return (plus - minus) / (2.0 * eps)

    def test_materialize_matches_manual_fixed_code_sum(self):
        decoded = materialize_fixed_codes(self.base, self.codebook, self.codes)
        expected = self.base + self.codebook[0, 1] + self.codebook[1, 0]
        torch.testing.assert_close(decoded, expected, rtol=0.0, atol=0.0)

    def test_autograd_matches_finite_difference_for_base(self):
        loss = fixed_code_loss(self.base, self.codebook, self.codes, self.inputs, self.target)
        loss.backward()
        analytic = float(self.base.grad[0, 1])
        numeric = self._finite_difference(self.base, (0, 1))
        self.assertAlmostEqual(analytic, numeric, places=8)

    def test_autograd_matches_finite_difference_for_selected_codebook_entry(self):
        loss = fixed_code_loss(self.base, self.codebook, self.codes, self.inputs, self.target)
        loss.backward()
        analytic = float(self.codebook.grad[1, 0, 1, 1])
        numeric = self._finite_difference(self.codebook, (1, 0, 1, 1))
        self.assertAlmostEqual(analytic, numeric, places=8)

    def test_unselected_codebook_entry_has_zero_gradient(self):
        loss = fixed_code_loss(self.base, self.codebook, self.codes, self.inputs, self.target)
        loss.backward()
        self.assertEqual(float(self.codebook.grad[0, 0].abs().max()), 0.0)
        self.assertEqual(float(self.codebook.grad[1, 1].abs().max()), 0.0)

    def test_rejects_invalid_dtype_shape_code_and_nonfinite(self):
        with self.assertRaises(TypeError):
            materialize_fixed_codes(self.base.float(), self.codebook, self.codes)
        with self.assertRaises(ValueError):
            materialize_fixed_codes(self.base, self.codebook[:, :, :, :1], self.codes)
        with self.assertRaises(ValueError):
            materialize_fixed_codes(self.base, self.codebook, torch.tensor([9, 0], dtype=torch.int64))
        bad = self.base.detach().clone()
        bad[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            materialize_fixed_codes(bad, self.codebook, self.codes)


if __name__ == "__main__":
    unittest.main()
