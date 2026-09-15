from __future__ import annotations

import copy
from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import inspect
import json
from pathlib import Path
import tempfile
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c142_color_alignment as c142
from fold_lm.v05_benchmarks import gate_e_c142_cli as cli


def rows():
    return [dict(key="q0", descriptor="red round metal", split="TRAIN_COMBINATION",
                 train=["ruby curved steel", "crimson circular alloy"], validation="ruby circular steel"),
            dict(key="q1", descriptor="blue square wood", split="TRAIN_COMBINATION",
                 train=["azure boxy timber", "navy angular lumber"], validation="navy boxy timber"),
            dict(key="q2", descriptor="red square wood", split="UNSEEN_COMBINATION",
                 train=[], validation="ruby angular lumber")]


def prior():
    s = dict(replay_seeds=list(range(20261601, 20261613)), fresh_seed_count=0, feature_dim=49,
             baseline_cases=144, intervention_cases=144, baseline_replay_match_rate=1.0,
             frozen_weights_preserved_rate=1.0, evaluation_oov_count=0,
             baseline_failure_count=4, rescued_failure_count=4, baseline_success_count=140,
             preserved_success_count=140, new_error_count=0, color_alias_localization_gate_passed=True)
    for k in ("canonical_known_accuracy", "canonical_unseen_accuracy",
              "canonical_scenario_accuracy", "canonical_positive_margin_rate"):
        s[k] = dict(min=1.0)
    records = []
    errors = {(20261602, 10): 2, (20261604, 11): 1, (20261606, 11): 1, (20261612, 10): 2}
    for seed in s["replay_seeds"]:
        base = []
        treated = []
        for i in range(12):
            for target, prediction in ((base, errors.get((seed, i), i)), (treated, i)):
                target.append(dict(key=f"q{i}", expected_address=i, predicted_address=prediction,
                                   passed=prediction == i, provenance_ok=True, commit_count=1,
                                   initial_action=2, final_action=0))
        records.append(dict(seed=seed, baseline_cases=base, canonical_color_cases=treated,
                            canonical_color_margins=[dict(key=f"q{i}", expected_margin=0.1) for i in range(12)]))
    return dict(experiment_id=c142.C141_ID, status="PASS", diagnostic_execution_valid=True,
                production_runtime_modified=False, gate_e_candidate=False, commit_sha=c142.C141_COMMIT,
                C140_summary_sha256=c142.C140_SUMMARY_SHA, C37_result_sha256_before=c142.C37_SHA,
                C37_result_sha256_after=c142.C37_SHA, fixture_sha256_before=c142.FIXTURE_SHA,
                fixture_sha256_after=c142.FIXTURE_SHA,
                input_sha256={"M:\\f\\c137_content_records.json": c142.CORPUS_SHA,
                              "M:\\f\\c138_compositional_alias_queries.json": c142.QUERIES_SHA},
                summary=s, records=records)


class V05C142ColorAlignmentTests(unittest.TestCase):
    def make_training(self):
        torch.manual_seed(314159)  # Synthetic helper seed, not a registered experiment seed.
        h = SharedRetrievalContentHead(feature_dim=4, hidden_dim=3, residual_scale=1.0)
        main = (F.normalize(torch.randn(3, 4), dim=-1), F.normalize(torch.randn(2, 4), dim=-1),
                torch.tensor([0, 1, 0]))
        auxiliary = (torch.eye(4)[:2], torch.eye(4)[2:], torch.tensor([0, 1]))
        return h, main, auxiliary

    def test_training_spec_ignores_validation_and_heldout_fields(self):
        data = rows()
        expected = c142._training_spec(data)
        for r in data:
            r["validation"] = "poisoned validation"
        data[-1]["descriptor"] = "invalid"
        data[-1]["train"] = ["ruby invalid invalid"]
        self.assertEqual(c142._training_spec(data), expected)

    def test_training_spec_does_not_mutate_rows(self):
        data = rows()
        original = copy.deepcopy(data)
        c142._training_spec(data)
        self.assertEqual(data, original)

    def test_color_pairs_are_deduplicated_sorted_and_labeled(self):
        data = rows()
        data[0]["train"].append(data[0]["train"][0])
        spec = c142._training_spec(data)
        self.assertEqual(spec.color_aliases, ("azure", "crimson", "navy", "ruby"))
        self.assertEqual(spec.canonical_colors, ("blue", "red"))
        self.assertEqual(spec.color_targets, (0, 1, 0, 1))
        self.assertEqual(len(spec.queries), 5)
        self.assertEqual(len(spec.descriptors), 2)

    def test_conflicting_training_alias_is_rejected(self):
        data = rows()
        data[1]["train"] = ["ruby boxy timber"]
        with self.assertRaises(ValueError):
            c142._training_spec(data)

    def test_empty_or_invalid_training_split_is_rejected(self):
        for data in ([], [rows()[-1]], [dict(split="TRAIN_COMBINATION", descriptor="red", train=["ruby"])]):
            with self.assertRaises(ValueError):
                c142._training_spec(data)

    def test_zero_weight_does_not_read_auxiliary_input(self):
        h, main, _ = self.make_training()
        total, primary, auxiliary = c142._objective(h, main, None, weight=0.0, logit_scale=12.0)
        self.assertTrue(torch.equal(total, primary))
        self.assertEqual(auxiliary.item(), 0.0)

    def test_auxiliary_objective_is_preregistered_weighted_sum(self):
        h, main, aux = self.make_training()
        total, primary, extra = c142._objective(h, main, aux, weight=1.0, logit_scale=12.0)
        manual = F.cross_entropy(h.scores(aux[0], aux[1]) * 12.0, aux[2])
        self.assertTrue(torch.equal(extra, manual))
        self.assertTrue(torch.equal(total, primary + manual))

    def test_bad_weight_and_scale_are_rejected(self):
        h, main, aux = self.make_training()
        for weight, scale in ((-1, 12), (float("nan"), 12), (1, 0), (1, float("inf"))):
            with self.assertRaises(ValueError):
                c142._objective(h, main, aux, weight=weight, logit_scale=scale)

    def test_nonfinite_loss_is_rejected(self):
        h, main, aux = self.make_training()
        main[0][0, 0] = float("nan")
        with self.assertRaises(RuntimeError):
            c142._objective(h, main, aux, weight=1.0, logit_scale=12.0)

    def test_zero_aux_training_matches_c139_reference_update_arithmetic(self):
        h, main, aux = self.make_training()
        reference = copy.deepcopy(h)
        c142._train(h, main, aux, weight=0, steps=3, lr=0.002, logit_scale=12.0)
        optimizer = torch.optim.AdamW(reference.parameters(), lr=0.002, weight_decay=0.0)
        for _ in range(3):
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(reference.scores(main[0], main[1]) * 12.0, main[2])
            loss.backward()
            optimizer.step()
        self.assertEqual(c142._head_sha(h), c142._head_sha(reference))

    def test_paired_copies_start_equal_and_auxiliary_changes_updates(self):
        h, main, aux = self.make_training()
        control, treatment = copy.deepcopy(h), copy.deepcopy(h)
        initial = c142._head_sha(h)
        self.assertEqual(c142._head_sha(control), initial)
        self.assertEqual(c142._head_sha(treatment), initial)
        c142._train(control, main, aux, weight=0, steps=2, lr=0.002, logit_scale=12.0)
        c142._train(treatment, main, aux, weight=1, steps=2, lr=0.002, logit_scale=12.0)
        self.assertNotEqual(c142._head_sha(control), c142._head_sha(treatment))
        self.assertEqual(c142._head_sha(h), initial)

    def test_rescue_counts_do_not_hide_new_errors(self):
        before = [dict(seed=1, key="q0", passed=False), dict(seed=1, key="q1", passed=True)]
        after = [dict(seed=1, key="q0", passed=True), dict(seed=1, key="q1", passed=False)]
        result = c142._paired_outcomes(before, after)
        self.assertEqual(result["rescued_failure_count"], 1)
        self.assertEqual(result["new_error_count"], 1)
        self.assertEqual(result["preserved_success_count"], 0)
        with self.assertRaises(ValueError):
            c142._paired_outcomes(before, list(reversed(after)))

    def test_pass_requires_success_and_strictly_positive_finite_margins(self):
        self.assertTrue(c142._treatment_passed([dict(passed=True, expected_margin=0.01)]))
        for value in (0.0, -0.01, float("nan"), float("inf")):
            self.assertFalse(c142._treatment_passed([dict(passed=True, expected_margin=value)]))
        self.assertFalse(c142._treatment_passed([dict(passed=False, expected_margin=0.1)]))
        self.assertFalse(c142._treatment_passed([]))

    def test_accepted_full_prerequisite_is_validated(self):
        c142._validate_prior(prior())

    def test_prerequisite_rejects_aggregate_only_wrong_source_and_fail(self):
        for field, value in (("records", "omitted; see summary.json"), ("commit_sha", "wrong"),
                             ("status", "FAIL"), ("C37_result_sha256_after", "wrong")):
            data = prior()
            data[field] = value
            with self.assertRaises(ValueError):
                c142._validate_prior(data)

    def test_prerequisite_rejects_bad_case_and_margin(self):
        data = prior()
        data["records"][0]["canonical_color_cases"][0]["passed"] = False
        with self.assertRaises(ValueError):
            c142._validate_prior(data)
        data = prior()
        data["records"][0]["canonical_color_margins"][0]["expected_margin"] = float("nan")
        with self.assertRaises(ValueError):
            c142._validate_prior(data)

    def test_prerequisite_selector_skips_invalid_files(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            good = root / "c141-good" / "summary.json"
            bad = root / "c141-bad" / "summary.json"
            good.parent.mkdir()
            bad.parent.mkdir()
            good.write_text(json.dumps(prior()), encoding="utf-8")
            bad.write_text("not json", encoding="utf-8")
            self.assertEqual(cli._latest_accepted_c141(root), good)

    def test_checkpoint_is_weights_only_loadable_and_reconstructible(self):
        h, _, _ = self.make_training()
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "head.pt"
            record = c142._save_head(path, h, vocabulary=("a", "b", "c", "d"),
                                     config=dict(feature_dim=4, hidden_dim=3, residual_scale=1.0))
            state = torch.load(path, weights_only=True)
            clone = SharedRetrievalContentHead(**state["config"])
            clone.load_state_dict(state["state_dict"])
            self.assertEqual(c142._head_sha(clone), c142._head_sha(h))
            self.assertEqual(record["sha256"], c142._sha(path))
            self.assertGreater(record["serialized_bytes"], 0)

    def test_fresh_seed_set_and_fixed_auxiliary_weight(self):
        self.assertEqual(c142.SEEDS, tuple(range(20261621, 20261633)))
        previous = set(range(20261581, 20261584)) | set(range(20261591, 20261594)) | set(range(20261601, 20261613))
        self.assertFalse(set(c142.SEEDS) & previous)
        self.assertEqual(c142.AUX_WEIGHT, 1.0)

    def make_eval(self, *, bad_source=False):
        data = [dict(key=f"q{i}", split="TRAIN_COMBINATION" if i < 8 else "UNSEEN_COMBINATION",
                     descriptor=f"record{i}", validation=f"alias{i}") for i in range(12)]
        seen_texts = []
        def features(texts, vocabulary, *, device):
            seen_texts.append(list(texts))
            indices = [int(t.removeprefix("record").removeprefix("alias")) for t in texts]
            return torch.eye(12, device=device)[indices]
        class Head(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.dummy = torch.nn.Parameter(torch.zeros(1))
            def scores(self, q, d):
                return q @ d.T
            def select(self, q, d):
                return self.scores(q, d).argmax(-1)
        class Adapter:
            source_sha256 = "source"
            index_fingerprint = "index"
            def retrieve(self, index, semantics, *, schema, exact):
                evidence = SimpleNamespace(domain="c137", schema="schema", operations=("READ_EVIDENCE",),
                                           source_sha256="wrong" if bad_source else "source",
                                           index_fingerprint="index", key=f"q{index}", evidence_value=index)
                return evidence, dict(source_sha256="source", index_fingerprint="index", mode="exact", vectors_scored=12)
        c113 = SimpleNamespace(_predict=lambda router, **kw: 0 if kw["evidence_present"] else 2)
        c137 = SimpleNamespace(SEMANTICS="semantics", SCHEMA="schema")
        c139 = SimpleNamespace(_collision_free_text_features=features,
                              _corpus_values=lambda: {f"q{i}": i for i in range(12)})
        kwargs = dict(seed=1, seed_index=1, arm="UNIT_TEST", deps=(c113, c137, c139, lambda n, **kw: n))
        return Head(), data, seen_texts, Adapter(), kwargs

    def test_evaluation_uses_original_text_and_adapter_result(self):
        head, data, seen_texts, adapter, kwargs = self.make_eval()
        original = copy.deepcopy(data)
        with redirect_stdout(io.StringIO()):
            cases = c142._evaluate(head, None, data, (), adapter, **kwargs)
        self.assertEqual(data, original)
        self.assertEqual(seen_texts[1], [r["validation"] for r in original])
        self.assertTrue(all(c["passed"] for c in cases))
        self.assertTrue(all(c["expected_margin"] == 1.0 for c in cases))
        self.assertEqual([c["hit_key"] for c in cases], [r["key"] for r in data])

    def test_wrong_provenance_is_execution_error_not_scientific_failure(self):
        head, data, _, adapter, kwargs = self.make_eval(bad_source=True)
        with self.assertRaisesRegex(RuntimeError, "authority control"):
            c142._evaluate(head, None, data, (), adapter, **kwargs)

    def test_evaluation_interface_has_no_alias_map(self):
        self.assertNotIn("mapping", inspect.signature(c142._evaluate).parameters)
        self.assertNotIn("color_map", inspect.signature(c142._evaluate).parameters)
        spec = c142._training_spec(rows())
        self.assertEqual(spec.queries, tuple(q for r in rows()[:2] for q in r["train"]))


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
