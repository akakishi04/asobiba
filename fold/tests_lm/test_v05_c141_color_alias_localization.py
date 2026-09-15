from __future__ import annotations

import copy
import unittest

import torch

from fold_lm.v05_benchmarks import gate_e_c141_color_alias_localization as c141


def fixture():
    return [
        dict(key="q0", descriptor="green triangular metal", split="TRAIN_COMBINATION",
             train=["emerald pointed alloy", "jade triangle steel"], validation="jade pointed steel"),
        dict(key="q1", descriptor="blue round stone", split="TRAIN_COMBINATION",
             train=["azure circular rocky"], validation="azure circular rocky"),
        dict(key="q2", descriptor="green round stone", split="UNSEEN_COMBINATION",
             train=[], validation="emerald circular rocky"),
    ]


def case(key, passed, split):
    return dict(key=key, passed=passed, split=split)


class V05C141ColorAliasLocalizationTests(unittest.TestCase):
    def test_training_map_ignores_unseen_rows_and_validation_labels(self):
        rows = fixture()
        expected = c141._training_color_map(rows)
        rows[-1]["descriptor"] = "invented invalid descriptor"
        rows[-1]["train"] = ["emerald circular glass"]
        rows[0]["validation"] = "unseen irrelevant query"
        self.assertEqual(c141._training_color_map(rows), expected)
        self.assertEqual(expected["emerald"], "green")

    def test_ambiguous_training_alias_is_rejected(self):
        rows = fixture()
        rows[1]["train"] = ["emerald circular rocky"]
        with self.assertRaises(ValueError):
            c141._training_color_map(rows)

    def test_only_color_changes_and_source_rows_are_not_mutated(self):
        rows = fixture()
        saved = copy.deepcopy(rows)
        changed = c141._canonical_color_rows(rows, c141._training_color_map(rows))
        self.assertEqual(rows, saved)
        self.assertEqual(changed[-1]["validation"], "green circular rocky")
        for old, new in zip(rows, changed, strict=True):
            self.assertEqual(old["validation"].split(maxsplit=1)[1], new["validation"].split(maxsplit=1)[1])
            for field in ("key", "split", "descriptor", "train"):
                self.assertEqual(old[field], new[field])

    def test_uncovered_alias_is_rejected(self):
        rows = fixture()
        mapping = c141._training_color_map(rows)
        rows[-1]["validation"] = "unknown circular rocky"
        with self.assertRaises(ValueError):
            c141._canonical_color_rows(rows, mapping)

    def test_training_pair_audit_excludes_heldout_combinations(self):
        report = c141._color_redundancy_audit(fixture())
        self.assertEqual(report["training_rows"], 2)
        self.assertEqual(report["distinct_training_shape_material_pairs"], 2)
        self.assertTrue(report["training_records_identifiable_without_color"])

    def test_rescuing_a_failure_does_not_hide_a_new_error(self):
        before = [case("a", True, "TRAIN_COMBINATION"), case("b", False, "UNSEEN_COMBINATION")]
        after = [case("a", False, "TRAIN_COMBINATION"), case("b", True, "UNSEEN_COMBINATION")]
        result = c141._pair_metrics(before, after)
        self.assertEqual(result["rescued_failure_count"], 1)
        self.assertEqual(result["new_error_count"], 1)
        self.assertEqual(result["preserved_success_count"], 0)

    def test_misaligned_pairs_are_rejected(self):
        with self.assertRaises(ValueError):
            c141._pair_metrics([case("a", True, "TRAIN_COMBINATION")],
                               [case("b", True, "TRAIN_COMBINATION")])

    def test_replay_accepts_equal_data_but_rejects_changed_prediction(self):
        cases = [dict(key="q0", predicted_address=0)]
        margins = [dict(key="q0", predicted_address=0, best_other_address=1, correct=True,
                        expected_score=0.9, best_other_score=0.8, expected_margin=0.1)]
        prior = dict(cases=copy.deepcopy(cases), margins=copy.deepcopy(margins))
        c141._check_replay(cases, margins, prior)
        cases[0]["predicted_address"] = 1
        with self.assertRaises(RuntimeError):
            c141._check_replay(cases, margins, prior)

    def test_replay_rejects_score_drift_and_nan(self):
        cases = [dict(key="q0")]
        margins = [dict(key="q0", predicted_address=0, best_other_address=1, correct=True,
                        expected_score=0.9, best_other_score=0.8, expected_margin=0.1)]
        prior = dict(cases=copy.deepcopy(cases), margins=copy.deepcopy(margins))
        for value in (0.1 + 2*c141.MARGIN_ATOL, float("nan")):
            margins[0]["expected_margin"] = value
            with self.assertRaises(RuntimeError):
                c141._check_replay(cases, margins, prior)

    def test_prerequisite_rejects_wrong_experiment_and_console_only_payload(self):
        with self.assertRaises(ValueError):
            c141._validate_prior(dict(experiment_id="C139", status="FAIL"))
        data = dict(experiment_id=c141.C140_ID, status="FAIL", production_runtime_modified=False,
                    gate_e_candidate=False, C37_result_sha256_before=c141.C37_SHA256,
                    C37_result_sha256_after=c141.C37_SHA256,
                    summary=dict(collision_free_multiseed_robustness_gate_passed=False,
                                 fresh_seeds=list(c141.SEEDS), full_seed_pass_count=8,
                                 known_combination_accuracy={"min": 1.0}, feature_dim=49),
                    records="omitted; see summary.json")
        data["summary"].update({field: {"min": 1.0} for field in c141.AUTHORITY_RATES})
        with self.assertRaisesRegex(ValueError, "Full C140 records"):
            c141._validate_prior(data)

    def test_weight_fingerprint_detects_mutation(self):
        head = torch.nn.Linear(2, 2)
        original = c141._head_sha(head)
        self.assertEqual(c141._head_sha(head), original)
        with torch.no_grad():
            head.weight[0, 0] += 1
        self.assertNotEqual(c141._head_sha(head), original)

    def test_seeds_are_exactly_the_c140_replay_set(self):
        self.assertEqual(c141.SEEDS, tuple(range(20261601, 20261613)))
        self.assertEqual(len(c141.SEEDS), 12)


if __name__ == "__main__":
    unittest.main()
