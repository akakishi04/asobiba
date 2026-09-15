from __future__ import annotations

import copy
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
from fold_lm.v05_benchmarks import gate_e_c145_material_alignment_intervention as c145


def full_rows():
    return copy.deepcopy(c138._load_fixture())


class V05C145MaterialAlignmentTests(unittest.TestCase):
    def test_seed_set_is_fresh(self):
        self.assertEqual(c145.SEEDS, tuple(range(20261641, 20261653)))
        old = set(range(20261581,20261584)) | set(range(20261591,20261594)) | set(range(20261601,20261613)) | set(range(20261621,20261633))
        self.assertFalse(set(c145.SEEDS) & old)

    def test_alignment_spec_uses_training_rows_only(self):
        rows = full_rows()
        expected = c145._alignment_spec(rows, 2)
        for row in rows:
            if row["split"] != "TRAIN_COMBINATION":
                row["descriptor"] = "green triangular glass"
                row["train"] = ["emerald pointed crystal"]
        self.assertEqual(c145._alignment_spec(rows, 2), expected)
        self.assertEqual(len(expected.aliases), 12)
        self.assertEqual(len(expected.canonicals), 4)

    def test_alignment_spec_rejects_bad_axis(self):
        with self.assertRaises(ValueError):
            c145._alignment_spec(full_rows(), 3)

    def test_main_spec_is_not_mutating(self):
        rows = full_rows()
        saved = copy.deepcopy(rows)
        q,d,t = c145._main_spec(rows)
        self.assertEqual(rows, saved)
        self.assertEqual(len(q), 24)
        self.assertEqual(len(d), 8)
        self.assertEqual(len(t), 24)

    def test_mask_axis_order(self):
        self.assertEqual(c145._mask("red round metal", "blue round metal"), "COLOR")
        self.assertEqual(c145._mask("red round metal", "red square wood"), "SHAPE+MATERIAL")

    def test_identical_mask_rejected(self):
        with self.assertRaises(ValueError):
            c145._mask("red round metal", "red round metal")

    def test_pair_counts_rescue_and_regression(self):
        suite = dict(descriptors=["red round metal","blue round metal"],
                     queries=[dict(expected_address=0),dict(expected_address=1)])
        control = [dict(correct=False,predicted_address=1),dict(correct=True,predicted_address=1)]
        treatment = [dict(correct=True,predicted_address=0),dict(correct=False,predicted_address=0)]
        p = c145._pair(control,treatment,suite)
        self.assertEqual(p["rescued_errors"],1)
        self.assertEqual(p["new_errors"],1)
        self.assertEqual(p["material_related_rescues"],0)

    def test_objective_material_zero_vs_one_differs(self):
        torch.manual_seed(123)
        head = SharedRetrievalContentHead(feature_dim=4, hidden_dim=3, residual_scale=1.0)
        main=(F.normalize(torch.randn(3,4),dim=-1),F.normalize(torch.randn(2,4),dim=-1),torch.tensor([0,1,0]))
        color=(torch.eye(4)[:2],torch.eye(4)[2:],torch.tensor([0,1]))
        material=(torch.eye(4)[2:],torch.eye(4)[:2],torch.tensor([0,1]))
        a = c145._objective(head,main,color,material,material_weight=0.0)[0]
        b = c145._objective(head,main,color,material,material_weight=1.0)[0]
        self.assertNotEqual(float(a),float(b))

    def test_head_fingerprint_detects_update(self):
        head = torch.nn.Linear(2,2)
        before = c145._head_sha(head)
        with torch.no_grad():
            head.weight[0,0] += 1
        self.assertNotEqual(before,c145._head_sha(head))

    def test_metrics_counts_material_involvement(self):
        suite = dict(descriptors=["red round metal","blue round metal","red square wood"],
                     queries=[dict(expected_address=0,bucket="NEW_COMBINATION"),
                              dict(expected_address=1,bucket="NEW_COMBINATION"),
                              dict(expected_address=2,bucket="NEW_COMBINATION")])
        results=[dict(correct=False,predicted_address=2,expected_margin=-.1),
                 dict(correct=True,predicted_address=1,expected_margin=.2),
                 dict(correct=False,predicted_address=0,expected_margin=-.3)]
        m=c145._metrics(suite,results)
        self.assertEqual(m["errors"],2)
        self.assertEqual(m["material_involved_errors"],2)

    def test_c144_validator_accepts_registered_profile(self):
        data=dict(experiment_id=c145.C144_ID,status="PASS",diagnostic_execution_valid=True,
                  C143_summary_sha256=c145.C143_SHA,evaluation_manifest_sha256=c145.MANIFEST_SHA,
                  production_runtime_modified=False,gate_e_candidate=False,
                  summary=dict(attribution_complete=True,
                    color_aux=dict(cases=20736,errors=1525,mismatch_masks={
                        "COLOR":152,"COLOR+MATERIAL":147,"COLOR+SHAPE":36,"COLOR+SHAPE+MATERIAL":38,
                        "MATERIAL":679,"SHAPE":305,"SHAPE+MATERIAL":168}),
                    paired_transitions={"BOTH_CORRECT":17070,"RESCUED":2141,"BOTH_WRONG":1417,"REGRESSION":108}))
        c145._validate_c144(data)

    def test_c144_validator_rejects_wrong_material_count(self):
        data=dict(experiment_id=c145.C144_ID,status="PASS",diagnostic_execution_valid=True,
                  C143_summary_sha256=c145.C143_SHA,evaluation_manifest_sha256=c145.MANIFEST_SHA,
                  production_runtime_modified=False,gate_e_candidate=False,
                  summary=dict(attribution_complete=True,color_aux=dict(cases=20736,errors=1525,mismatch_masks={}),
                               paired_transitions={"BOTH_CORRECT":17070,"RESCUED":2141,"BOTH_WRONG":1417,"REGRESSION":108}))
        with self.assertRaises(ValueError):
            c145._validate_c144(data)


if __name__ == "__main__":
    unittest.main()
