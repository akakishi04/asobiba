from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147


class V05C147CompositionOrderTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(1234)  # Toy helper seed, never a registered model seed.
        self.head = SharedRetrievalContentHead(feature_dim=4, hidden_dim=3, residual_scale=1.0).eval()
        self.words = {word: i for i, word in enumerate(("a", "b", "c", "six-sided"))}

    def features(self, texts):
        result = torch.zeros(len(texts), 4)
        for i, text in enumerate(texts):
            for word in text.split():
                result[i, self.words[word]] += 1
        return F.normalize(result, dim=-1)

    def test_unit_order_is_invariant_and_repetitions_preserved(self):
        self.assertEqual(c147._units("b a a"), ("a", "a", "b"))
        a, _ = c147._compose(self.head, ["b a a", "a b a"], self.features)
        self.assertTrue(torch.equal(a[0], a[1]))

    def test_single_expression_matches_original_encoder(self):
        a, _ = c147._compose(self.head, ["a"], self.features)
        with torch.inference_mode():
            b = self.head.encode(self.features(["a"]))
        torch.testing.assert_close(a, b)

    def test_composition_equals_normalized_sum_of_unit_encodings(self):
        actual, cost = c147._compose(self.head, ["b a c"], self.features)
        with torch.inference_mode():
            expected = F.normalize(self.head.encode(self.features(["a", "b", "c"])).sum(0), dim=-1)
        torch.testing.assert_close(actual[0], expected)
        self.assertEqual(cost["unique_encoded_units"], 3)
        self.assertEqual(cost["unit_occurrences"], 3)

    def test_hyphenated_expression_is_passed_intact_to_feature_function(self):
        seen = []
        def features(texts):
            seen.extend(texts)
            return self.features(texts)
        c147._compose(self.head, ["a six-sided b"], features)
        self.assertIn("six-sided", seen)
        self.assertNotIn("sided", seen)

    def test_no_typed_factor_or_expected_label_in_encoder_interface(self):
        self.assertEqual(tuple(inspect.signature(c147._compose).parameters), ("head", "texts", "features"))
        self.assertNotIn("mapping", inspect.signature(c147._compose).parameters)

    def test_empty_units_and_undefined_normalization_rejected(self):
        for text in ("", "  ", None):
            with self.assertRaises(ValueError):
                c147._units(text)
        class Identity:
            def encode(self, value):
                return value
        with self.assertRaisesRegex(ValueError, "Undefined"):
            c147._compose(Identity(), ["a b"], lambda texts: torch.tensor([[1., 0.], [-1., 0.]]))
        with self.assertRaises(ValueError):
            c147._compose(self.head, [], self.features)

    def test_compose_does_not_mutate_head_or_texts(self):
        texts = ["a b", "c a"]
        saved = list(texts)
        before = c147._fingerprint(self.head)
        c147._compose(self.head, texts, self.features)
        self.assertEqual(texts, saved)
        self.assertEqual(before, c147._fingerprint(self.head))

    def test_compose_uses_one_unique_unit_encoding_batch(self):
        seen = []
        def features(texts):
            seen.append(list(texts))
            return self.features(texts)
        _, cost = c147._compose(self.head, ["a b", "b a", "b b"], features)
        self.assertEqual(seen, [["a", "b"]])
        self.assertEqual(cost["unit_occurrences"], 6)

    def test_labels_cannot_change_predictions(self):
        scores = torch.tensor([[0.2, 0.8], [0.9, 0.1]])
        original = scores.clone()
        a = c147._rank(scores, [0, 0])
        b = c147._rank(scores, [1, 1])
        self.assertEqual([r["predicted_address"] for r in a], [r["predicted_address"] for r in b])
        self.assertTrue(torch.equal(original, scores))

    def test_rank_rejects_nan_shapes_and_invalid_indices(self):
        for matrix, expected in ((torch.tensor([[float("nan"), 0.]]), [0]),
                                  (torch.zeros(2, 1), [0, 0]), (torch.zeros(1, 2), [2]),
                                  (torch.zeros(1, 2), [True]), (torch.zeros(2), [0])):
            with self.assertRaises(ValueError):
                c147._rank(matrix, expected)

    def test_strict_positive_margin_gate_and_ties(self):
        correct = c147._rank(torch.tensor([[1., 0.]]), [0])
        self.assertTrue(c147._perfect(correct))
        self.assertFalse(c147._perfect(c147._rank(torch.ones(1, 2), [0])))
        self.assertFalse(c147._perfect(c147._rank(torch.tensor([[0., 1.]]), [0])))
        self.assertFalse(c147._perfect([]))

    def test_replay_rejects_rank_score_and_numeric_changes(self):
        prior = c147._rank(torch.tensor([[0.9, 0.2]]), [0])
        c147._replay(copy.deepcopy(prior), prior)
        for key, value in (("predicted_address", 1), ("best_other_address", 0),
                           ("expected_margin", prior[0]["expected_margin"] + 0.001),
                           ("expected_score", float("nan"))):
            changed = copy.deepcopy(prior)
            changed[0][key] = value
            with self.assertRaises(ValueError):
                c147._replay(changed, prior)

    def test_pair_does_not_hide_new_errors(self):
        a = [dict(correct=False), dict(correct=True), dict(correct=False), dict(correct=True)]
        b = [dict(correct=True), dict(correct=False), dict(correct=False), dict(correct=True)]
        self.assertEqual(c147._paired(a, b), dict(rescued_errors=1, new_errors=1, both_wrong=1, both_correct=1))
        with self.assertRaises(ValueError):
            c147._paired(a, b[:2])

    def test_source_seed_set_includes_all_successes_and_failures(self):
        self.assertEqual(c147.SEEDS, tuple(range(20261661, 20261673)))
        self.assertEqual(sum(c147.PRIOR_ERRORS[c147.SOURCE_ARM]), 11)
        self.assertEqual(sum(x == 0 for x in c147.PRIOR_ERRORS[c147.SOURCE_ARM]), 8)
        self.assertEqual(c147.SOURCE_ARM, "ALL_FACTOR_AUX")

    def test_rejects_wrong_prerequisite_before_auditing(self):
        with self.assertRaises(ValueError):
            c147._validate_prior({"experiment_id": "C145"}, {}, lambda *a: self.fail("Unexpected auditor call"))

    def test_error_details_include_query_target_and_both_predictions(self):
        suite = dict(descriptors=["red round metal", "blue round metal"],
                     queries=[dict(case_id="x", text="ruby curved steel", bucket="NEW_COMBINATION", expected_address=0)])
        before = c147._rank(torch.tensor([[0.1, 0.9]]), [0])
        after = c147._rank(torch.tensor([[0.9, 0.1]]), [0])
        detail = c147._details(suite, before, after)[0]
        self.assertEqual(detail["expected"], "red round metal")
        self.assertEqual(detail["pooled_prediction"], "blue round metal")
        self.assertTrue(detail["composed_correct"])

    def checkpoint(self, root):
        head = SharedRetrievalContentHead(**c147.CONFIG)
        vocab = tuple(f"u{i}" for i in range(49))
        seed = c147.SEEDS[0]
        path = root / f"seed-{seed}-{c147.SOURCE_ARM.lower()}.pt"
        torch.save(dict(state_dict=head.state_dict(), config=c147.CONFIG, vocabulary=list(vocab)), path)
        entry = dict(final_head_sha256=c147._fingerprint(head),
                     checkpoint=dict(path=str(path), sha256=c147._sha(path), serialized_bytes=path.stat().st_size))
        return seed, vocab, path, entry

    def test_checkpoint_is_reconstructed_frozen_with_exact_fingerprint(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            seed, vocab, path, entry = self.checkpoint(root)
            head, selected = c147._load_head(root, seed, entry, vocab, torch.device("cpu"))
            self.assertEqual(path, selected)
            self.assertEqual(entry["final_head_sha256"], c147._fingerprint(head))
            self.assertFalse(any(p.requires_grad for p in head.parameters()))

    def test_checkpoint_wrong_name_hash_vocabulary_and_weights_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            seed, vocab, _, entry = self.checkpoint(root)
            for kind in ("name", "hash", "vocabulary", "weights"):
                changed = copy.deepcopy(entry)
                supplied_vocab = vocab
                if kind == "name": changed["checkpoint"]["path"] = "wrong.pt"
                if kind == "hash": changed["checkpoint"]["sha256"] = "0"*64
                if kind == "vocabulary": supplied_vocab = tuple(reversed(vocab))
                if kind == "weights": changed["final_head_sha256"] = "0"*64
                with self.assertRaises(ValueError):
                    c147._load_head(root, seed, changed, supplied_vocab, torch.device("cpu"))


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
