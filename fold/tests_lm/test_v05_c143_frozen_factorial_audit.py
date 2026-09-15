from __future__ import annotations

from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest

import torch

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143


def fixture():
    path = Path(c143.__file__).parent / "fixtures" / "c138_compositional_alias_queries.json"
    return json.loads(path.read_text(encoding="utf-8"))["queries"]


def synthetic_prior():
    rows = fixture()
    errors = {(20261622, "q9"): 2, (20261623, "q11"): 1, (20261625, "q10"): 2,
              (20261628, "q11"): 1, (20261629, "q10"): 2, (20261629, "q11"): 1,
              (20261631, "q10"): 2, (20261631, "q11"): 1, (20261632, "q11"): 1}
    records = []
    for seed in c143.SEEDS:
        arms = {}
        for arm in c143.ARMS:
            cases = []
            for i, row in enumerate(rows):
                prediction = errors.get((seed, row["key"]), i) if arm == "BASELINE" else i
                cases.append(dict(seed=seed, key=row["key"], split=row["split"], query_text=row["validation"],
                                  expected_address=i, predicted_address=prediction, passed=prediction == i,
                                  provenance_ok=True, initial_action=2, final_action=0, commit_count=1,
                                  expected_score=0.9, best_other_score=0.8,
                                  expected_margin=0.1 if prediction == i else -0.1))
            arms[arm] = dict(cases=cases, training=dict(optimizer_steps=600),
                             initial_head_sha256="a"*64, final_head_sha256="b"*64)
        records.append(dict(seed=seed, arms=arms))
    summary = dict(fresh_seeds=list(c143.SEEDS), color_alignment_gate_passed=True, inference_oracle_used=False,
                   unique_fresh_seed_count=12, trained_heads=24, **c143.CONFIG, train_steps=600,
                   auxiliary_weight=1.0, baseline_cases=144, treatment_cases=144, baseline_failure_count=9,
                   rescued_failure_count=9, baseline_success_count=135, preserved_success_count=135,
                   new_error_count=0, evaluation_oov_count=0, zero_paired_lexical_overlap_rate=1.0,
                   paired_initial_weights_equal_rate=1.0, evaluation_weights_preserved_rate=1.0)
    return dict(experiment_id=c143.C142_ID, status="PASS", diagnostic_execution_valid=True,
                commit_sha=c143.C142_COMMIT, production_runtime_modified=False, gate_e_candidate=False,
                C141_summary_sha256=c143.C141_SHA, C37_result_sha256_before=c143.C37_SHA,
                C37_result_sha256_after=c143.C37_SHA, fixture_sha256_before=c143.FIXTURE_SHA,
                fixture_sha256_after=c143.FIXTURE_SHA, summary=summary, records=records)


class DotHead(torch.nn.Module):
    def scores(self, q, d):
        return q @ d.T


class V05C143FrozenFactorialAuditTests(unittest.TestCase):
    def test_full_factor_product_and_alias_counts(self):
        suite = c143._build_suite(fixture())
        self.assertEqual(len(suite["descriptors"]), 64)
        self.assertEqual(len(suite["queries"]), 1728)
        self.assertEqual(Counter(q["bucket"] for q in suite["queries"]),
                         {"TRAIN_COMBINATION": 216, "PRIOR_HELDOUT_COMBINATION": 108, "NEW_COMBINATION": 1404})
        self.assertEqual(set(Counter(q["expected_address"] for q in suite["queries"]).values()), {27})

    def test_original_catalog_order_is_preserved(self):
        rows = fixture()
        self.assertEqual(c143._build_suite(rows)["descriptors"][:12], [r["descriptor"] for r in rows])

    def test_original_training_and_validation_queries_are_flagged(self):
        queries = c143._build_suite(fixture())["queries"]
        self.assertEqual(sum(q["original_training_query"] for q in queries), 24)
        self.assertEqual(sum(q["original_validation_query"] for q in queries), 12)

    def test_generated_query_target_has_zero_lexical_overlap(self):
        suite = c143._build_suite(fixture())
        for q in suite["queries"]:
            self.assertFalse(set(c143.TOKEN_RE.findall(q["text"])) &
                             set(c143.TOKEN_RE.findall(suite["descriptors"][q["expected_address"]])))

    def test_suite_is_deterministic_and_input_is_not_mutated(self):
        rows = fixture()
        saved = copy.deepcopy(rows)
        first = c143._build_suite(rows)
        self.assertEqual(c143._json_sha(first), c143._json_sha(c143._build_suite(rows)))
        self.assertEqual(rows, saved)

    def test_heldout_training_fields_do_not_contribute_aliases(self):
        rows = fixture()
        expected = c143._build_suite(rows)
        rows[-1]["train"] = ["invented forbidden supervision"]
        self.assertEqual(c143._build_suite(rows), expected)

    def test_ambiguous_training_alias_is_rejected(self):
        rows = fixture()
        rows[2]["train"][0] = "crimson circular rocky"
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            c143._build_suite(rows)

    def test_wrong_factor_cardinality_is_rejected(self):
        rows = fixture()
        rows[0]["train"][0] = "newalias circular metallic"
        with self.assertRaises(ValueError):
            c143._build_suite(rows)

    def test_candidate_scorer_accepts_dynamic_catalog_size(self):
        q = torch.eye(4)
        self.assertEqual(len(c143._score(DotHead(), q, q[:2], [0, 1, 0, 1])), 4)
        self.assertEqual(len(c143._score(DotHead(), q, torch.cat((q, q[:1])), [0, 1, 2, 3])), 4)

    def test_expected_labels_cannot_change_model_predictions(self):
        q = torch.eye(4)
        a = c143._score(DotHead(), q, q, [0, 1, 2, 3])
        b = c143._score(DotHead(), q, q, [1, 2, 3, 0])
        self.assertEqual([r["predicted_address"] for r in a], [r["predicted_address"] for r in b])
        self.assertTrue(all(r["correct"] for r in a))
        self.assertFalse(any(r["correct"] for r in b))

    def test_margins_handle_correct_incorrect_and_tie(self):
        d = torch.eye(2)
        r = c143._score(DotHead(), torch.tensor([[1., 0.], [0., 1.], [0., 0.]]), d, [0, 0, 0])
        self.assertEqual([x["expected_margin"] for x in r], [1., -1., 0.])
        self.assertFalse(c143._passed(r))

    def test_nonfinite_scores_and_bad_labels_are_rejected(self):
        with self.assertRaises(RuntimeError):
            c143._score(DotHead(), torch.tensor([[float("nan"), 0.]]), torch.eye(2), [0])
        with self.assertRaises(ValueError):
            c143._score(DotHead(), torch.eye(2), torch.eye(2), [0, 2])

    def test_replay_checks_prediction_and_score_drift(self):
        result = c143._score(DotHead(), torch.eye(2), torch.eye(2), [0, 1])
        reference = [dict(r, passed=r["correct"]) for r in result]
        c143._check_replay(result, reference)
        for key, value in (("predicted_address", 1), ("expected_margin", 0.8)):
            changed = copy.deepcopy(result)
            changed[0][key] = value
            with self.assertRaises(RuntimeError):
                c143._check_replay(changed, reference)

    def test_pass_requires_every_case_and_positive_finite_margin(self):
        self.assertTrue(c143._passed([dict(correct=True, expected_margin=0.01)]))
        for margin in (0., -1., float("nan"), float("inf")):
            self.assertFalse(c143._passed([dict(correct=True, expected_margin=margin)]))
        self.assertFalse(c143._passed([]))
        self.assertFalse(c143._passed([dict(correct=False, expected_margin=0.1)]))

    def test_group_metrics_do_not_hide_new_combination_errors(self):
        suite = c143._build_suite(fixture())
        results = [dict(correct=True, expected_margin=0.1) for q in suite["queries"]]
        results[-1] = dict(correct=False, expected_margin=-0.1)
        metrics = c143._group_metrics(suite, results)
        self.assertEqual(metrics["ALL"]["correct_count"], 1727)
        self.assertEqual(metrics["NEW_COMBINATION"]["correct_count"], 1403)
        self.assertEqual(metrics["TRAIN_COMBINATION"]["accuracy"], 1.)
        self.assertEqual(metrics["ORIGINAL_VALIDATION_IN_64"]["case_count"], 12)

    def test_accepted_full_prerequisite_profile(self):
        self.assertEqual(len(c143._validate_prior(synthetic_prior(), fixture())), 12)

    def test_prerequisite_rejects_console_only_and_wrong_commit(self):
        for key, value in (("records", "omitted"), ("commit_sha", "other"), ("status", "FAIL")):
            data = synthetic_prior()
            data[key] = value
            with self.assertRaises(ValueError):
                c143._validate_prior(data, fixture())

    def test_prerequisite_rejects_changed_treatment_or_query(self):
        data = synthetic_prior()
        data["records"][0]["arms"]["COLOR_AUX"]["cases"][0]["expected_margin"] = 0
        with self.assertRaises(ValueError):
            c143._validate_prior(data, fixture())
        data = synthetic_prior()
        data["records"][0]["arms"]["BASELINE"]["cases"][0]["query_text"] = "changed"
        with self.assertRaises(ValueError):
            c143._validate_prior(data, fixture())

    def checkpoint(self, root):
        torch.manual_seed(777)  # Synthetic unit-test initialization, not an experiment head.
        head = SharedRetrievalContentHead(**c143.CONFIG)
        vocab = tuple(f"token{i}" for i in range(49))
        path = root / "seed-20261621-baseline.pt"
        torch.save(dict(config=c143.CONFIG, vocabulary=list(vocab), state_dict=head.state_dict()), path)
        entry = dict(final_head_sha256=c143._head_sha(head),
                     checkpoint=dict(path=f"runs\\synthetic\\{path.name}", sha256=c143._sha(path),
                                     serialized_bytes=path.stat().st_size))
        return vocab, path, entry

    def test_checkpoint_reconstruction_is_frozen_and_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab, path, entry = self.checkpoint(root)
            loaded, used_path = c143._load_head(root, 20261621, "BASELINE", entry, vocab, "cpu")
            self.assertEqual(used_path, path)
            self.assertEqual(c143._head_sha(loaded), entry["final_head_sha256"])
            self.assertFalse(loaded.training)
            self.assertFalse(any(p.requires_grad for p in loaded.parameters()))

    def test_checkpoint_tampering_vocab_and_fingerprint_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab, path, entry = self.checkpoint(root)
            with self.assertRaises(ValueError):
                c143._load_head(root, 20261621, "BASELINE", entry, tuple(reversed(vocab)), "cpu")
            bad = copy.deepcopy(entry)
            bad["final_head_sha256"] = "f"*64
            with self.assertRaises(ValueError):
                c143._load_head(root, 20261621, "BASELINE", bad, vocab, "cpu")
            path.write_bytes(path.read_bytes()+b"tampered")
            with self.assertRaises(ValueError):
                c143._load_head(root, 20261621, "BASELINE", entry, vocab, "cpu")

    def test_checkpoint_path_metadata_cannot_redirect_file_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab, path, entry = self.checkpoint(root)
            entry["checkpoint"]["path"] = "../../elsewhere/" + path.name
            _, used_path = c143._load_head(root, 20261621, "BASELINE", entry, vocab, "cpu")
            self.assertEqual(used_path, path)
            entry["checkpoint"]["path"] = "../../elsewhere/other.pt"
            with self.assertRaises(ValueError):
                c143._load_head(root, 20261621, "BASELINE", entry, vocab, "cpu")

    def test_seed_set_reuses_all_c142_heads(self):
        self.assertEqual(c143.SEEDS, tuple(range(20261621, 20261633)))
        self.assertEqual(c143.ARMS, ("BASELINE", "COLOR_AUX"))
        self.assertEqual(c143.CONFIG, dict(feature_dim=49, hidden_dim=64, residual_scale=1.))


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
