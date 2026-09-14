from __future__ import annotations

import unittest

import torch

from fold_lm.v05.retrieval_query import RetrievalAddressHead, address_to_structure, hashed_text_features


class V05RetrievalQueryTests(unittest.TestCase):
    def test_hashed_text_features_are_deterministic(self):
        a = hashed_text_features(["bring back cobalt evidence"], feature_dim=64)
        b = hashed_text_features(["bring back cobalt evidence"], feature_dim=64)
        self.assertTrue(torch.equal(a, b))
        self.assertEqual(tuple(a.shape), (1, 64))
        self.assertAlmostEqual(float(a.norm(dim=-1).item()), 1.0, places=6)

    def test_address_head_returns_expected_shape(self):
        head = RetrievalAddressHead(feature_dim=64, hidden_dim=32, address_count=8)
        x = hashed_text_features(["cobalt", "saffron"], feature_dim=64)
        y = head(x)
        self.assertEqual(tuple(y.shape), (2, 8))

    def test_address_to_structure_is_one_hot(self):
        self.assertEqual(address_to_structure(3, address_count=8), (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            address_to_structure(8, address_count=8)


if __name__ == "__main__":
    unittest.main()
