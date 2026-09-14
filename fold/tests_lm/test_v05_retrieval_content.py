from __future__ import annotations

import unittest

import torch

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05.retrieval_query import hashed_text_features


class V05RetrievalContentTests(unittest.TestCase):
    def test_encode_returns_unit_norm_vectors(self):
        head = SharedRetrievalContentHead(feature_dim=32, hidden_dim=8)
        x = hashed_text_features(["alpha record", "beta record"], feature_dim=32)
        encoded = head.encode(x)
        self.assertEqual(tuple(encoded.shape), (2, 32))
        self.assertTrue(torch.allclose(encoded.norm(dim=-1), torch.ones(2), atol=1e-6))

    def test_scores_accept_dynamic_candidate_count(self):
        head = SharedRetrievalContentHead(feature_dim=32, hidden_dim=8)
        q = hashed_text_features(["alpha query"], feature_dim=32)
        for count in (3, 7, 12):
            records = hashed_text_features([f"record {i}" for i in range(count)], feature_dim=32)
            self.assertEqual(tuple(head.scores(q, records).shape), (1, count))

    def test_select_returns_candidate_index_without_fixed_address_count(self):
        torch.manual_seed(7)
        head = SharedRetrievalContentHead(feature_dim=64, hidden_dim=16, residual_scale=0.0)
        query = hashed_text_features(["archive cobalt evidence"], feature_dim=64)
        records = hashed_text_features(
            ["archive saffron evidence", "archive cobalt evidence", "archive quartz evidence"],
            feature_dim=64,
        )
        self.assertEqual(int(head.select(query, records).item()), 1)


if __name__ == "__main__":
    unittest.main()
