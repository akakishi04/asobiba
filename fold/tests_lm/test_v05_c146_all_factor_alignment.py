from __future__ import annotations

from collections import Counter
import copy
import hashlib
import itertools
import json
import math
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146


def training_rows():
    return [dict(split="TRAIN_COMBINATION", descriptor="red round metal",
                 train=["ruby curved steel","crimson circular alloy"],validation="ruby circular alloy"),
            dict(split="TRAIN_COMBINATION",descriptor="blue hexagonal wood",
                 train=["azure six-sided lumber","navy honeycomb timber"],validation="azure honeycomb timber"),
            dict(split="UNSEEN_COMBINATION",descriptor="red hexagonal wood",train=[],validation="ruby six-sided timber")]


def result(expected, predicted, count):
    rival = ((expected+1)%count) if expected == predicted else predicted
    a,b = (0.75,0.25) if expected == predicted else (0.25,0.75)
    return dict(predicted_address=predicted, best_other_address=rival, correct=expected==predicted,
                expected_score=a,best_other_score=b,expected_margin=a-b)


def tiny_suite():
    return dict(descriptors=["red round metal","blue round metal","red square wood"],
                queries=[dict(expected_address=i,bucket="NEW_COMBINATION",original_validation_query=True) for i in range(3)])


def synthetic_prior():
    """Synthetic records matching the aggregate contract; not actual C145 outcomes."""
    factors = (("blue","green","red","yellow"),("hexagonal","round","square","triangular"),
               ("glass","metal","stone","wood"))
    descriptors = [" ".join(x) for x in itertools.product(*factors)]
    queries = [dict(expected_address=i,bucket="NEW_COMBINATION") for i in range(64) for _ in range(27)]
    suite = dict(descriptors=descriptors,queries=queries)
    def pools(masks):
        material, other = [],[]
        for mask,n in masks.items():
            (material if "MATERIAL" in mask else other).extend([mask]*n)
        return material,other
    cm,co = pools(c146.PRIOR_MASKS["COLOR_AUX"])
    tm,to = pools(c146.PRIOR_MASKS["COLOR_MATERIAL_AUX"])
    rescue_pool = iter(cm[:724]+co[:429])
    both_control_pool = iter(cm[724:]+co[429:])
    new_pool = iter(tm[:4]+to[:31])
    both_treatment_pool = iter(tm[4:]+to[31:])
    c_counts=(106,116,155,115,105,136,54,100,230,108,143,96)
    t_counts=(16,13,16,14,31,46,5,18,107,34,30,16)
    new_counts=(1,0,0,4,0,2,2,4,8,4,6,4)
    def wrong(e,mask):
        parts = descriptors[e].split()
        for j,axis in enumerate(c146.AXES):
            if axis in mask.split("+"):
                parts[j]=factors[j][(factors[j].index(parts[j])+1)%4]
        return descriptors.index(" ".join(parts))
    records=[]
    for seed,nc,nt,nn in zip(range(20261641,20261653),c_counts,t_counts,new_counts,strict=True):
        before=[result(q["expected_address"],q["expected_address"],64) for q in queries]
        after=copy.deepcopy(before)
        nw=nt-nn
        for j in range(nc):
            at=216+j;e=queries[at]["expected_address"]
            cmask=next(both_control_pool if j<nw else rescue_pool)
            before[at]=result(e,wrong(e,cmask),64)
            if j<nw:
                after[at]=result(e,wrong(e,next(both_treatment_pool)),64)
        for j in range(nn):
            at=216+nc+j;e=queries[at]["expected_address"]
            after[at]=result(e,wrong(e,next(new_pool)),64)
        entries={}
        for arm,results in (("COLOR_AUX",before),("COLOR_MATERIAL_AUX",after)):
            entries[arm]=dict(initial_head_sha256="0"*64,training=dict(optimizer_steps=600),results=results,
                              metrics=c146._audit_results(results,suite),
                              original12=[result(i,i,12) for i in range(12)],original12_all_pass=True)
        records.append(dict(seed=seed,arms=entries))
    aggregates={}
    for arm,masks in c146.PRIOR_MASKS.items():
        errors=sum(masks.values())
        aggregates[arm]=dict(cases=20736,errors=errors,correct=20736-errors,mismatch_masks=masks,
                             material_involved_errors=sum(n for mask,n in masks.items() if "MATERIAL" in mask),
                             full_model_pass_count=0,original12_full_pass_count=12)
    summary=dict(fresh_seeds=list(range(20261641,20261653)),unique_fresh_seed_count=12,paired_heads=24,
                 **c146.CONFIG,train_steps=600,learning_rate=c146.LR,logit_scale=c146.SCALE,
                 color_weight=1.0,material_weight=1.0,full_candidate_count=64,queries_per_model=1728,
                 full_ranking_cases_per_arm=20736,additional_runtime_path=False,inference_oracle_used=False,
                 material_alignment_gate_passed=False,paired=c146.PRIOR_PAIRED,arms=aggregates)
    return dict(experiment_id=c146.C145_ID,commit_sha=c146.C145_COMMIT,status="FAIL",diagnostic_execution_valid=True,
                production_runtime_modified=False,gate_e_candidate=False,C144_result_sha256=c146.C144_SHA,
                summary=summary,records=records),suite


class V05C146AllFactorAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior,cls.full_suite=synthetic_prior()

    def tensors(self):
        torch.manual_seed(24680)  # Only synthetic helper weights; no formal fresh seed.
        head=SharedRetrievalContentHead(feature_dim=4,hidden_dim=3,residual_scale=1.0)
        def data():
            return F.normalize(torch.randn(3,4),dim=-1),F.normalize(torch.randn(2,4),dim=-1),torch.tensor([0,1,0])
        return head,data(),{axis:data() for axis in c146.AXES}

    def test_training_uses_no_validation_or_heldout_fields(self):
        rows=training_rows(); expected=c146._training_specs(rows)
        for r in rows:r["validation"]="poison"
        rows[-1]["descriptor"]="invalid";rows[-1]["train"]=["poison"]
        self.assertEqual(c146._training_specs(rows),expected)

    def test_specs_preserve_hyphenated_shape_expression_and_source(self):
        rows=training_rows();original=copy.deepcopy(rows)
        main,specs=c146._training_specs(rows)
        self.assertEqual(rows,original);self.assertIn("six-sided",specs["SHAPE"][0])
        self.assertEqual(main[1],("red round metal","blue hexagonal wood"))

    def test_conflicting_factor_alias_is_rejected(self):
        rows=training_rows();rows[1]["train"]=["azure curved lumber"]
        with self.assertRaises(ValueError):c146._training_specs(rows)

    def test_malformed_and_empty_training_rejected(self):
        for rows in ([],[training_rows()[-1]],[dict(split="TRAIN_COMBINATION",descriptor="red",train=["ruby"])]):
            with self.assertRaises(ValueError):c146._training_specs(rows)

    def test_control_has_no_shape_loss_graph(self):
        head,main,align=self.tensors()
        values=c146._objective(head,main,align["COLOR"],align["MATERIAL"],None,shape_weight=0.0)
        self.assertEqual(values[-1].item(),0.0);self.assertFalse(values[-1].requires_grad)

    def test_shape_one_objective_is_exact_weighted_sum(self):
        head,main,align=self.tensors()
        total,*losses=c146._objective(head,main,align["COLOR"],align["MATERIAL"],align["SHAPE"],shape_weight=1.0)
        torch.testing.assert_close(total,losses[0]+losses[1]+losses[2]+losses[3],rtol=0,atol=0)

    def test_invalid_weight_and_nonfinite_loss_rejected(self):
        head,main,align=self.tensors()
        for w in (-1,0.5,True,float("nan")):
            with self.assertRaises(ValueError):c146._objective(head,main,align["COLOR"],align["MATERIAL"],None,shape_weight=w)
        main[0][0,0]=float("nan")
        with self.assertRaises(RuntimeError):c146._objective(head,main,align["COLOR"],align["MATERIAL"],None,shape_weight=0.0)

    def test_control_updates_match_explicit_c145_treatment_arithmetic(self):
        head,main,align=self.tensors();reference=copy.deepcopy(head)
        c146._train(head,main,align,shape_weight=0.0,steps=3)
        opt=torch.optim.AdamW(reference.parameters(),lr=0.002,weight_decay=0.0)
        for _ in range(3):
            opt.zero_grad(set_to_none=True)
            def loss(d):return F.cross_entropy(reference.scores(d[0],d[1])*12.0,d[2])
            total=loss(main)+1.0*loss(align["COLOR"])+1.0*loss(align["MATERIAL"])
            total.backward();opt.step()
        self.assertEqual(c146._fingerprint(head),c146._fingerprint(reference))

    def test_paired_models_start_equal_but_auxiliary_changes_updates(self):
        head,main,align=self.tensors();a,b=copy.deepcopy(head),copy.deepcopy(head)
        self.assertEqual(c146._fingerprint(a),c146._fingerprint(b))
        c146._train(a,main,align,shape_weight=0.0,steps=2)
        c146._train(b,main,align,shape_weight=1.0,steps=2)
        self.assertNotEqual(c146._fingerprint(a),c146._fingerprint(b))

    def test_pass_requires_correct_and_strictly_positive_finite_margin(self):
        self.assertTrue(c146._perfect([dict(correct=True,expected_margin=0.01)]))
        for margin in (0,-1,float("nan"),float("inf")):
            self.assertFalse(c146._perfect([dict(correct=True,expected_margin=margin)]))
        self.assertFalse(c146._perfect([]))

    def test_masks_include_overlapping_factor_counts(self):
        suite=tiny_suite();results=[result(0,2,3),result(1,0,3),result(2,2,3)]
        m=c146._audit_results(results,suite)
        self.assertEqual(m["factor_involved_errors"],dict(COLOR=1,SHAPE=1,MATERIAL=1))
        self.assertEqual(m["errors"],2)

    def test_audit_rejects_invalid_index_and_inconsistent_margin(self):
        suite=tiny_suite();results=[result(i,i,3) for i in range(3)]
        for key,value in (("predicted_address",9),("expected_margin",float("nan")),("expected_margin",-0.1),("correct",False)):
            invalid=copy.deepcopy(results);invalid[0][key]=value
            with self.assertRaises(ValueError):c146._audit_results(invalid,suite)

    def test_group_metrics_preserve_overlapping_original_group(self):
        suite=tiny_suite();results=[result(i,i,3) for i in range(3)]
        metrics=c146._audit_results(results,suite)
        self.assertEqual(metrics["cases"],3)
        self.assertEqual(metrics["groups"]["ORIGINAL_VALIDATION_IN_64"]["cases"],3)

    def test_paired_counts_distinguish_rescue_and_new_error(self):
        suite=tiny_suite()
        b=[result(0,2,3),result(1,1,3),result(2,2,3)]
        a=[result(0,0,3),result(1,0,3),result(2,2,3)]
        paired=c146._pair(b,a,suite)
        self.assertEqual(paired["rescued_errors"],1);self.assertEqual(paired["new_errors"],1)
        self.assertEqual(paired["rescued_masks"],{"SHAPE+MATERIAL":1})
        self.assertEqual(paired["regression_masks"],{"COLOR":1})

    def test_full_synthetic_prerequisite_recomputes_accepted_aggregates(self):
        c146._validate_c145(self.prior,self.full_suite)

    def test_prerequisite_rejects_console_only_or_wrong_commit(self):
        for field,value in (("records","omitted"),("commit_sha","wrong"),("status","PASS")):
            data=dict(self.prior);data[field]=value
            with self.assertRaises(ValueError):c146._validate_c145(data,self.full_suite)

    def test_prerequisite_rejects_duplicate_seed_and_false_full_pass_count(self):
        data=copy.deepcopy(self.prior);data["records"][-1]["seed"]=20261641
        with self.assertRaises(ValueError):c146._validate_c145(data,self.full_suite)
        data=copy.deepcopy(self.prior);data["summary"]["arms"]["COLOR_AUX"]["full_model_pass_count"]=12
        with self.assertRaises(ValueError):c146._validate_c145(data,self.full_suite)

    def test_prerequisite_rejects_modified_case(self):
        data=copy.deepcopy(self.prior)
        data["records"][0]["arms"]["COLOR_AUX"]["results"][0]["expected_margin"]=-99
        with self.assertRaises(ValueError):c146._validate_c145(data,self.full_suite)

    def test_manifest_checks_lf_and_crlf_bytes_without_semantic_fallback(self):
        suite=tiny_suite();text=json.dumps(suite,indent=2,allow_nan=False)
        for raw in (text.encode(),text.replace("\n","\r\n").encode()):
            self.assertEqual(c146._manifest_bytes(suite,hashlib.sha256(raw).hexdigest()),raw)
        with self.assertRaises(RuntimeError):c146._manifest_bytes(suite,"0"*64)

    def test_seed_set_is_fresh_and_configuration_fixed(self):
        self.assertEqual(c146.SEEDS,tuple(range(20261661,20261673)))
        self.assertFalse(set(c146.SEEDS)&set(range(20261581,20261653)))
        self.assertEqual((c146.STEPS,c146.LR,c146.SCALE),(600,0.002,12.0))


if __name__ == "__main__":
    unittest.main()
