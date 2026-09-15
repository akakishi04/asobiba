from __future__ import annotations

import copy
import inspect
import json
import math
from pathlib import Path
import tempfile
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c150_global_negatives as c150


def specs():
    return dict(COLOR=(("ruby", "azure"), ("red", "blue"), (0, 1)),
                SHAPE=(("curved", "boxy"), ("round", "square"), (0, 1)),
                MATERIAL=(("alloy", "timber"), ("metal", "wood"), (0, 1)))


def summarize(cases):
    # Synthetic accounting contract, not an integration with the C149 module.
    wrong = [r for r in cases if not r["correct"]]
    return dict(cases=len(cases), errors=len(wrong),
                max_reconstruction_error=max((r["reconstruction_error"] for r in cases), default=0.0),
                error_term_means={k: (sum(r[k] for r in wrong)/len(wrong) if wrong else None) for k in c150.PARTS},
                positive_same_factor_errors=sum(r["same_factor"] > 1e-5 for r in wrong),
                negative_cross_factor_errors=sum(r["cross_factor"] < -1e-5 for r in wrong),
                negative_candidate_norm_errors=sum(r["candidate_norm"] < -1e-5 for r in wrong))


def synthetic_prior():
    source_records, records = [], []
    suite = dict(queries=[dict(case_id=f"case-{i}", bucket="TEST") for i in range(1728)])
    source_arms = ("POOLED_TRAIN", "COMPOSED_TRAIN")
    source_pairs = dict(rescued_errors=0, new_errors=1, both_correct=20724, both_wrong=11)
    for seed in range(20261681, 20261693):
        entries = {}
        for arm in source_arms:
            n = (5 if arm == source_arms[0] else 6) if seed == 20261683 else 6 if seed == 20261692 else 0
            cases = []
            for i, query in enumerate(suite["queries"]):
                correct = i >= n
                same, cross, norm = (0.3, -0.5, 0.1) if not correct else (0.3, 0.0, 0.1)
                margin = same + cross + norm
                cases.append(dict(**query, correct=correct, predicted_address=0 if correct else 1,
                                  best_other_address=1, expected_margin=margin, reconstructed_margin=margin,
                                  reconstruction_error=0.0, same_factor=same, cross_factor=cross, candidate_norm=norm))
            entries[arm] = dict(results=[{k: c[k] for k in ("correct", "predicted_address", "best_other_address", "expected_margin")} for c in cases],
                checkpoint=dict(sha256="checkpoint"), final_head_sha256="fingerprint",
                training=dict(training_alignment_accuracy=dict.fromkeys(c150.AXES, 1.0)))
            records.append(dict(seed=seed, arm=arm, cases=cases,
                error_details=[dict(**c, text="alias text", expected="expected", selected="selected") for c in cases if not c["correct"]],
                checkpoint_sha256="checkpoint", frozen_head_sha256="fingerprint",
                source_singleton_fit=dict.fromkeys(c150.AXES, 1.0), accounting=summarize(cases)))
        source_records.append(dict(seed=seed, arms=entries))
    source = dict(records=source_records, summary=dict(paired=source_pairs))
    compact = [dict(seed=r["seed"], arm=r["arm"], **{k: d[k] for k in
               ("text", "expected", "selected", "expected_margin") + c150.PARTS}) for r in records for d in r["error_details"]]
    s = dict(analysis_only=True, loaded_checkpoints=24, fresh_seed_count=0, additional_training_steps=0,
             scoring_rule_changed=False, runtime_path_exercised=False, full_replay_cases=41472, original12_replay_cases=288,
             full_replay_match_rate=1.0, frozen_weights_preserved_rate=1.0, accounting_complete=True, reconstruction_atol=1e-5,
             source_paired=source_pairs, residual_case_details=compact,
             arms={arm: summarize([c for r in records if r["arm"] == arm for c in r["cases"]]) for arm in source_arms})
    data = dict(experiment_id=c150.C149_ID, commit_sha=c150.C149_COMMIT, status="PASS", diagnostic_execution_valid=True,
                production_runtime_modified=False, gate_e_candidate=False, C148_summary_sha256=c150.C148_SHA,
                evaluation_manifest_sha256=c150.MANIFEST_SHA, summary=s, records=records)
    return data, source, suite


class V05C150GlobalNegativesTests(unittest.TestCase):
    def make_tensors(self):
        torch.manual_seed(73019)  # Toy helper initialization, not a C150 registered seed.
        pairs = specs()
        words = sorted({s for q, d, _ in pairs.values() for s in q+d})
        def features(strings):
            return torch.eye(len(words))[[words.index(s) for s in strings]]
        def encode(pair):
            return features(pair[0]), features(pair[1]), torch.tensor(pair[2])
        scopes = {scope: {a: encode(s) for a, s in c150._candidate_specs(pairs, scope).items()} for scope in c150.ARMS}
        h = SharedRetrievalContentHead(feature_dim=len(words), hidden_dim=5, residual_scale=1.0)
        main = (F.normalize(torch.randn(4, len(words)), dim=-1),
                F.normalize(torch.randn(2, len(words)), dim=-1), torch.tensor([0, 1, 0, 1]))
        return h, main, scopes

    def test_within_factor_spec_is_unchanged(self):
        self.assertEqual(c150._candidate_specs(specs(), "WITHIN_FACTOR"), specs())

    def test_global_pool_preserves_positive_pairs(self):
        original = specs()
        combined = c150._candidate_specs(original, "GLOBAL_CONCEPT")
        for axis in c150.AXES:
            q, d, y = combined[axis]
            a, b, t = original[axis]
            self.assertEqual(q, a)
            self.assertEqual([d[i] for i in y], [b[i] for i in t])
            self.assertEqual(d, tuple(sorted(s for _, words, _ in original.values() for s in words)))

    def test_global_candidates_include_all_other_axes(self):
        original = specs()
        expanded = c150._candidate_specs(original, "GLOBAL_CONCEPT")
        for axis in c150.AXES:
            old = set(original[axis][1])
            self.assertTrue(old < set(expanded[axis][1]))
            self.assertEqual(len(set(expanded[axis][1]) - old), 4)

    def test_candidate_build_does_not_mutate_training_specs(self):
        original = specs()
        snapshot = copy.deepcopy(original)
        c150._candidate_specs(original, "GLOBAL_CONCEPT")
        self.assertEqual(snapshot, original)

    def test_scope_and_factor_set_are_validated(self):
        with self.assertRaises(ValueError):
            c150._candidate_specs(specs(), "AUTOTUNE")
        p = specs(); p.pop("COLOR")
        with self.assertRaises(ValueError):
            c150._candidate_specs(p, "GLOBAL_CONCEPT")

    def test_duplicate_canonical_names_are_rejected(self):
        p = specs(); p["SHAPE"] = (p["SHAPE"][0], ("red", "square"), (0, 1))
        with self.assertRaisesRegex(ValueError, "disjoint"):
            c150._candidate_specs(p, "GLOBAL_CONCEPT")

    def test_ambiguous_alias_across_axes_is_rejected(self):
        p = specs(); p["SHAPE"] = (("ruby", "boxy"), p["SHAPE"][1], (0, 1))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            c150._candidate_specs(p, "GLOBAL_CONCEPT")

    def test_invalid_labels_and_empty_pairs_are_rejected(self):
        for labels in ((2, 0), (True, 0), (0,), ()):
            p = specs(); p["COLOR"] = (p["COLOR"][0], p["COLOR"][1], labels)
            with self.assertRaises(ValueError):
                c150._candidate_specs(p, "WITHIN_FACTOR")

    def test_candidate_order_is_deterministic(self):
        original = specs()
        reversed_keys = dict(reversed(list(original.items())))
        self.assertEqual(c150._candidate_specs(original, "GLOBAL_CONCEPT"),
                         c150._candidate_specs(reversed_keys, "GLOBAL_CONCEPT"))

    def test_main_loss_is_identical_and_only_auxiliary_candidates_change(self):
        h, main, scopes = self.make_tensors()
        a = c150._objective(h, main, scopes[c150.ARMS[0]])
        b = c150._objective(h, main, scopes[c150.ARMS[1]])
        self.assertTrue(torch.equal(a[1], b[1]))
        self.assertGreater(b[0].item(), a[0].item())
        # More denominator terms for identical positives must raise each CE.
        self.assertTrue(all(y.item() > x.item() for x, y in zip(a[2:], b[2:])))

    def test_sum_of_three_means_has_no_factor_of_three_weight_drop(self):
        h, main, scopes = self.make_tensors()
        aux = scopes["GLOBAL_CONCEPT"]
        values = c150._objective(h, main, aux)
        q = torch.cat([aux[a][0] for a in c150.LOSS_ORDER])
        y = torch.cat([aux[a][2] for a in c150.LOSS_ORDER])
        d = aux["COLOR"][1]
        combined = 3 * F.cross_entropy(h.scores(q, d) * c150.SCALE, y)
        self.assertTrue(torch.allclose(sum(values[2:]), combined, atol=1e-6, rtol=1e-6))

    def test_control_optimizer_matches_explicit_reference_arithmetic(self):
        h, main, scopes = self.make_tensors()
        reference = copy.deepcopy(h)
        aux = scopes["WITHIN_FACTOR"]
        c150._train(h, main, aux, steps=3)
        optimizer = torch.optim.AdamW(reference.parameters(), lr=c150.LR, weight_decay=0.0)
        for _ in range(3):
            optimizer.zero_grad(set_to_none=True)
            def ce(t): return F.cross_entropy(reference.scores(t[0], t[1]) * 12.0, t[2])
            loss = ce(main) + 1.0*ce(aux["COLOR"]) + 1.0*ce(aux["MATERIAL"]) + 1.0*ce(aux["SHAPE"])
            loss.backward(); optimizer.step()
        for k, value in h.state_dict().items():
            self.assertTrue(torch.equal(value, reference.state_dict()[k]))

    def test_paired_weights_equal_before_training_but_not_after(self):
        h, main, scopes = self.make_tensors()
        control, treatment = copy.deepcopy(h), copy.deepcopy(h)
        c150._train(control, main, scopes["WITHIN_FACTOR"], steps=2)
        c150._train(treatment, main, scopes["GLOBAL_CONCEPT"], steps=2)
        self.assertTrue(any(not torch.equal(a, b) for a, b in zip(control.parameters(), treatment.parameters())))
        self.assertEqual(sum(p.numel() for p in control.parameters()), sum(p.numel() for p in treatment.parameters()))

    def test_training_bad_steps_and_nonfinite_objective_rejected(self):
        h, main, scopes = self.make_tensors()
        for step in (0, True, 1.5):
            with self.assertRaises(ValueError):
                c150._train(h, main, scopes["GLOBAL_CONCEPT"], steps=step)
        main[0][0, 0] = float("nan")
        with self.assertRaises(RuntimeError):
            c150._objective(h, main, scopes["GLOBAL_CONCEPT"])

    def test_strict_perfect_gate(self):
        self.assertTrue(c150._perfect([dict(correct=True, expected_margin=0.1)]))
        for correct, margin in ((False, 0.1), (True, 0), (True, -0.1), (True, float("nan")), (True, float("inf"))):
            self.assertFalse(c150._perfect([dict(correct=correct, expected_margin=margin)]))
        self.assertFalse(c150._perfect([]))

    def test_checkpoint_contains_scope_metadata_and_safe_weights(self):
        h, _, _ = self.make_tensors()
        config = dict(feature_dim=h.feature_dim, hidden_dim=5, residual_scale=1.0)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "model.pt"
            record = c150._save_head(path, h, list(map(str, range(h.feature_dim))), "GLOBAL_CONCEPT", config)
            saved = torch.load(path, weights_only=True)
            clone = SharedRetrievalContentHead(**saved["config"])
            clone.load_state_dict(saved["state_dict"])
            self.assertEqual(saved["auxiliary_candidate_scope"], "GLOBAL_CONCEPT")
            self.assertEqual(saved["training_composition"], "POOL_THEN_ENCODE")
            self.assertEqual(saved["inference_composition"], "ENCODE_THEN_POOL")
            self.assertEqual(record["sha256"], c150._sha(path))
            self.assertTrue(all(torch.equal(v, clone.state_dict()[k]) for k, v in h.state_dict().items()))

    def test_fresh_seeds_and_no_validation_interface(self):
        self.assertEqual(c150.SEEDS, tuple(range(20261701, 20261713)))
        self.assertFalse(set(c150.SEEDS) & set(range(20261581, 20261693)))
        self.assertEqual(list(inspect.signature(c150._candidate_specs).parameters), ["specs", "scope"])
        self.assertEqual(c150.STEPS, 600)

    def test_full_synthetic_audit_reaggregation(self):
        data, source, suite = synthetic_prior()
        c150._validate_audit(data, source, suite, summarize)

    def test_audit_rejects_console_only_and_wrong_identity(self):
        with self.assertRaises(ValueError):
            c150._validate_audit(dict(experiment_id="C148"), {}, {}, summarize)
        data, source, suite = synthetic_prior()
        data["records"] = "omitted; see summary.json"
        with self.assertRaisesRegex(ValueError, "Full ordered"):
            c150._validate_audit(data, source, suite, summarize)

    def test_audit_rejects_case_mismatch_and_accounting_drift(self):
        data, source, suite = synthetic_prior()
        case = data["records"][0]["cases"][0]
        for key, bad in (("case_id", "bad"), ("same_factor", 999.0), ("cross_factor", float("nan")), ("reconstruction_error", 1e-3)):
            original = case[key]; case[key] = bad
            with self.assertRaises(ValueError):
                c150._validate_audit(data, source, suite, summarize)
            case[key] = original
        data["summary"]["arms"]["POOLED_TRAIN"]["errors"] = 0
        with self.assertRaises(ValueError):
            c150._validate_audit(data, source, suite, summarize)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
