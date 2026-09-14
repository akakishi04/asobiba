from __future__ import annotations

import json
import re
from pathlib import Path
import unittest

import torch

from fold_lm.v05.retrieval_query import hashed_text_features


FIXTURE = Path(__file__).resolve().parents[1] / "fold_lm" / "v05_benchmarks" / "fixtures" / "c138_compositional_alias_queries.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _rows():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload["queries"]


class V05C138CompositionalAliasFixtureTests(unittest.TestCase):
    def test_validation_and_descriptor_share_no_tokens(self):
        for row in _rows():
            query_tokens = set(TOKEN_RE.findall(row["validation"].lower()))
            descriptor_tokens = set(TOKEN_RE.findall(row["descriptor"].lower()))
            self.assertFalse(query_tokens & descriptor_tokens, row["key"])

    def test_unseen_combination_alias_tokens_are_seen_during_training(self):
        rows = _rows()
        train_tokens = set()
        for row in rows:
            for text in row["train"]:
                train_tokens.update(TOKEN_RE.findall(text.lower()))
        unseen = [row for row in rows if row["split"] == "UNSEEN_COMBINATION"]
        self.assertEqual(len(unseen), 4)
        for row in unseen:
            validation_tokens = set(TOKEN_RE.findall(row["validation"].lower()))
            self.assertTrue(validation_tokens <= train_tokens, row["key"])

    def test_raw_hashed_features_do_not_solve_unseen_combinations(self):
        rows = _rows()
        descriptors = hashed_text_features([row["descriptor"] for row in rows], feature_dim=128)
        queries = hashed_text_features([row["validation"] for row in rows], feature_dim=128)
        predicted = (queries @ descriptors.transpose(0, 1)).argmax(dim=-1)
        expected = torch.arange(len(rows))
        unseen_indices = [i for i, row in enumerate(rows) if row["split"] == "UNSEEN_COMBINATION"]
        unseen_accuracy = (predicted[unseen_indices] == expected[unseen_indices]).float().mean().item()
        self.assertLess(unseen_accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()
