from __future__ import annotations

import unittest

import torch

from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139


class V05C139HashCollisionDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = c138._load_fixture()
        self.vocabulary = c139._training_vocabulary(self.rows)

    def test_c138_training_vocabulary_reproduces_amber_red_hash_collision(self):
        collisions = c139._hash_collision_buckets(self.rows)
        self.assertTrue(
            any({"amber", "red"}.issubset(set(tokens)) for tokens in collisions.values())
        )

    def test_training_vocabulary_covers_all_validation_and_descriptor_tokens(self):
        self.assertEqual(c139._fixture_oov_count(self.rows, self.vocabulary), 0)

    def test_collision_free_features_distinguish_amber_and_red(self):
        features = c139._collision_free_text_features(
            ["amber", "red"],
            self.vocabulary,
            device=torch.device("cpu"),
        )
        self.assertFalse(torch.equal(features[0], features[1]))
        self.assertAlmostEqual(float(features[0].norm().item()), 1.0, places=6)
        self.assertAlmostEqual(float(features[1].norm().item()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
