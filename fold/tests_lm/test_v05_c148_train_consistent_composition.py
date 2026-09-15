from __future__ import annotations

from collections import Counter
import copy
import inspect
from itertools import product
from pathlib import Path
import tempfile
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05_benchmarks import gate_e_c148_train_consistent_composition as c148


def _features(texts, dtype=torch.float64):
    vocabulary = ("a", "b", "c", "three-sided")
    rows = [[t.split().count(v) for v in vocabulary] for t in texts]
    return F.normalize(torch.tensor(rows,dtype=dtype),dim=-1)


def _synthetic_prior():
    """Full-size synthetic records test C148 glue, with an injected toy auditor.

    Not the real C147 report and not a test of C146's existing audit module.
    """
    descriptors = [" ".join(p) for p in product(("red","blue","green","yellow"),
                    ("round","square","triangular","hexagonal"),("metal","wood","glass","stone"))]
    suite = dict(descriptors=descriptors,queries=[dict(expected_address=0) for _ in range(1728)])
    def result(e=0,p=0):
        return dict(predicted_address=p,correct=p==e,expected_margin=0.1 if e==p else -0.1)
    def audit(rows,suite):
        masks=Counter()
        for r,q in zip(rows,suite["queries"],strict=True):
            if not r["correct"]:
                e,p=suite["descriptors"][q["expected_address"]].split(),suite["descriptors"][r["predicted_address"]].split()
                masks["+".join(a for a,x,y in zip(c148.AXES,e,p) if x!=y)] += 1
        return dict(errors=sum(masks.values()),mismatch_masks=dict(sorted(masks.items())))
    def paired(b,a):
        return dict(rescued_errors=sum(not x["correct"] and y["correct"] for x,y in zip(b,a)),
                    new_errors=sum(x["correct"] and not y["correct"] for x,y in zip(b,a)),
                    both_correct=sum(x["correct"] and y["correct"] for x,y in zip(b,a)),
                    both_wrong=sum(not x["correct"] and not y["correct"] for x,y in zip(b,a)))
    records=[]
    for i,seed in enumerate(range(20261661,20261673)):
        b=[result() for _ in range(1728)]; a=copy.deepcopy(b)
        for j,p in ({3:{0:16,1:16},4:{0:4},5:{0:16,1:16,2:1,3:1,4:1,5:1,6:1},10:{0:16}}.get(i,{})).items():
            b[j]=result(p=p)
        if i==5:
            for j in (0,10,11,12):
                a[j]=result(p=16)
        modes={}
        for mode,rows in (("POOL_THEN_ENCODE",b),(c148.EVAL_MODE,a)):
            modes[mode]=dict(results=rows,metrics=audit(rows,suite),original12=[result(e=j,p=j) for j in range(12)])
        records.append(dict(seed=seed,source_training_alignment_accuracy=dict.fromkeys(c148.AXES,1.0),
                            modes=modes,paired=paired(b,a)))
    summary=dict(source_seeds=list(range(20261661,20261673)),source_arm="ALL_FACTOR_AUX",loaded_checkpoints=12,
                 fresh_seed_count=0,additional_training_steps=0,inference_oracle_used=False,runtime_path_exercised=False,
                 baseline_full_replay_cases=20736,treatment_full_ranking_cases=20736,original12_replay_cases=144,
                 original12_treatment_cases=144,full_replay_match_rate=1.0,frozen_weights_preserved_rate=1.0,
                 composition_order_gate_passed=False,modes={})
    flat={}
    for mode in ("POOL_THEN_ENCODE",c148.EVAL_MODE):
        flat[mode]=[r for entry in records for r in entry["modes"][mode]["results"]]
        m=audit(flat[mode],dict(descriptors=descriptors,queries=suite["queries"]*12))
        m.update(full_model_pass_count=sum(c148._perfect(r["modes"][mode]["results"]) for r in records),original12_full_pass_count=12)
        summary["modes"][mode]=m
    summary["paired"]=paired(flat["POOL_THEN_ENCODE"],flat[c148.EVAL_MODE])
    return dict(experiment_id=c148.C147_ID,commit_sha=c148.C147_COMMIT,status="FAIL",diagnostic_execution_valid=True,
                production_runtime_modified=False,gate_e_candidate=False,C146_summary_sha256=c148.C146_SHA,
                evaluation_manifest_sha256=c148.MANIFEST_SHA,summary=summary,records=records),suite,audit,paired


class V05C148TrainConsistentCompositionTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(8675309)  # Toy seed, not registered experiment evidence.
        self.head=SharedRetrievalContentHead(feature_dim=4,hidden_dim=3,residual_scale=1.0).double()

    def training(self):
        main=(c148._prepare(["a b","a c","b c"],_features),c148._prepare(["a c","b a"],_features),torch.tensor([0,1,0]))
        aux={axis:(_features(["a","b"]),_features(["c","three-sided"]),torch.tensor([0,1])) for axis in c148.AXES}
        return main,aux

    def test_units_sort_without_dropping_hyphens_or_repetitions(self):
        self.assertEqual(c148._units("b a a three-sided"),("a","a","b","three-sided"))

    def test_empty_or_invalid_text_is_rejected(self):
        for text in ("","  ",None,17):
            with self.assertRaises(ValueError): c148._units(text)
        with self.assertRaises(ValueError): c148._prepare([],_features)

    def test_preparation_keeps_input_and_only_caches_features(self):
        texts=["a b","b c"];saved=list(texts)
        batch=c148._prepare(texts,_features)
        self.assertEqual(texts,saved)
        self.assertFalse(batch.unit_features.requires_grad)
        self.assertFalse(hasattr(batch,"unit_vectors"))
        self.assertEqual(batch.unit_features.shape[0],3)

    def test_preparation_rejects_nonfinite_features(self):
        with self.assertRaises(ValueError): c148._prepare(["a"],lambda ts: torch.full((len(ts),4),float("nan")))

    def test_composition_matches_c147_normalized_sum_formula(self):
        texts=["a b c","three-sided a","b b c"]
        actual=c148._encode(self.head,c148._prepare(texts,_features),c148.EVAL_MODE)
        vectors=[F.normalize(self.head.encode(_features(sorted(t.split()))).sum(0),dim=0) for t in texts]
        torch.testing.assert_close(actual,torch.stack(vectors),rtol=0,atol=1e-14)

    def test_single_unit_matches_shared_encoder(self):
        actual=c148._encode(self.head,c148._prepare(["a","three-sided"],_features),c148.EVAL_MODE)
        torch.testing.assert_close(actual,self.head.encode(_features(["a","three-sided"])),rtol=0,atol=1e-14)

    def test_permutation_invariance_and_repetition_weight(self):
        batch=c148._prepare(["a b c","c a b","a a b"],_features)
        v=c148._encode(self.head,batch,c148.EVAL_MODE)
        self.assertTrue(torch.equal(v[0],v[1]))
        self.assertFalse(torch.equal(v[0],v[2]))

    def test_padding_does_not_contribute_vectors(self):
        batch=c148._prepare(["a","a b c"],_features)
        actual=c148._encode(self.head,batch,c148.EVAL_MODE)[0]
        expected=self.head.encode(_features(["a"]))[0]
        torch.testing.assert_close(actual,expected)

    def test_unregistered_mode_and_zero_sum_are_rejected(self):
        batch=c148._prepare(["a"],_features)
        with self.assertRaises(ValueError): c148._encode(self.head,batch,"UNREGISTERED")
        class Zero:
            def encode(self,f): return torch.zeros_like(f)
        with self.assertRaises(ValueError): c148._encode(Zero(),batch,c148.EVAL_MODE)

    def test_gradient_matches_double_precision_finite_difference(self):
        batch=c148._prepare(["a b c"],_features)
        weight=self.head.network[0].weight
        value=c148._encode(self.head,batch,c148.EVAL_MODE)[0,0]
        value.backward(); analytic=weight.grad[0,0].item();eps=1e-6
        with torch.no_grad():
            old=weight[0,0].item();weight[0,0]=old+eps
            hi=c148._encode(self.head,batch,c148.EVAL_MODE)[0,0].item();weight[0,0]=old-eps
            lo=c148._encode(self.head,batch,c148.EVAL_MODE)[0,0].item();weight[0,0]=old
        self.assertNotEqual(analytic,0.0)
        self.assertAlmostEqual(analytic,(hi-lo)/(2*eps),places=7)

    def test_multiple_steps_recompute_learned_vectors(self):
        main,aux=self.training();before=c148._fingerprint(self.head)
        r=c148._train(self.head,main,aux,mode=c148.EVAL_MODE,steps=3)
        self.assertNotEqual(before,c148._fingerprint(self.head));self.assertEqual(r["optimizer_steps"],3)

    def test_pooled_control_objective_is_c146_arithmetic(self):
        main,aux=self.training();v=c148._objective(self.head,main,aux,train_mode="POOL_THEN_ENCODE")
        ml=F.cross_entropy(self.head.scores(main[0].whole_features,main[1].whole_features)*12,main[2])
        def ce(axis):
            a,d,y=aux[axis];return F.cross_entropy(self.head.scores(a,d)*12,y)
        expected=ml+1.0*ce("COLOR")+1.0*ce("MATERIAL")+1.0*ce("SHAPE")
        self.assertTrue(torch.equal(v[0],expected))

    def test_pooled_control_updates_equal_reference(self):
        main,aux=self.training();reference=copy.deepcopy(self.head)
        c148._train(self.head,main,aux,mode="POOL_THEN_ENCODE",steps=2)
        opt=torch.optim.AdamW(reference.parameters(),lr=.002,weight_decay=0)
        for _ in range(2):
            opt.zero_grad(set_to_none=True)
            loss=F.cross_entropy(reference.scores(main[0].whole_features,main[1].whole_features)*12,main[2])
            for axis in ("COLOR","MATERIAL","SHAPE"):
                a,d,y=aux[axis];loss=loss+1.0*F.cross_entropy(reference.scores(a,d)*12,y)
            loss.backward();opt.step()
        self.assertEqual(c148._fingerprint(self.head),c148._fingerprint(reference))

    def test_only_main_term_changes_between_objectives(self):
        main,aux=self.training()
        b=c148._objective(self.head,main,aux,train_mode="POOL_THEN_ENCODE")
        a=c148._objective(self.head,main,aux,train_mode=c148.EVAL_MODE)
        self.assertTrue(all(torch.equal(x,y) for x,y in zip(b[2:],a[2:])))
        self.assertFalse(torch.equal(b[1],a[1]))

    def test_paired_initial_state_same_updates_differ(self):
        main,aux=self.training();control=copy.deepcopy(self.head);treatment=copy.deepcopy(self.head)
        self.assertEqual(c148._fingerprint(control),c148._fingerprint(treatment))
        for head,mode in ((control,"POOL_THEN_ENCODE"),(treatment,c148.EVAL_MODE)):
            c148._train(head,main,aux,mode=mode,steps=2)
        self.assertNotEqual(c148._fingerprint(control),c148._fingerprint(treatment))

    def test_bad_steps_and_nonfinite_losses_rejected(self):
        main,aux=self.training()
        for steps in (0,-1,True,1.5):
            with self.assertRaises(ValueError): c148._train(self.head,main,aux,mode=c148.EVAL_MODE,steps=steps)
        with torch.no_grad(): self.head.network[0].weight[0,0]=float("nan")
        with self.assertRaises((ValueError,RuntimeError)): c148._objective(self.head,main,aux,train_mode=c148.EVAL_MODE)

    def test_encoder_has_no_labels_or_factor_slot_interface(self):
        self.assertEqual(list(inspect.signature(c148._encode).parameters),(list(("head","batch","mode"))))
        main,_=self.training();scores=c148._scores(self.head,main[0],main[1],c148.EVAL_MODE)
        main[2].fill_(1)
        self.assertTrue(torch.equal(scores,c148._scores(self.head,main[0],main[1],c148.EVAL_MODE)))

    def test_strict_gate_rejects_ties_errors_and_nonfinite_margin(self):
        self.assertTrue(c148._perfect([dict(correct=True,expected_margin=.1)]))
        for margin in (0,-.1,float("nan"),float("inf")):
            self.assertFalse(c148._perfect([dict(correct=True,expected_margin=margin)]))
        self.assertFalse(c148._perfect([]));self.assertFalse(c148._perfect([dict(correct=False,expected_margin=.1)]))

    def test_evaluation_does_not_mutate_head(self):
        before=c148._fingerprint(self.head);batch=c148._prepare(["a b"],_features)
        with torch.inference_mode(): c148._encode(self.head,batch,c148.EVAL_MODE)
        self.assertEqual(before,c148._fingerprint(self.head))

    def test_checkpoint_contains_composition_metadata_and_loads_safely(self):
        head=SharedRetrievalContentHead(**c148.CONFIG)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.pt";meta=c148._save_head(path,head,tuple(map(str,range(49))),c148.EVAL_MODE)
            saved=torch.load(path,weights_only=True);clone=SharedRetrievalContentHead(**saved["config"])
            clone.load_state_dict(saved["state_dict"])
            self.assertEqual(c148._fingerprint(head),c148._fingerprint(clone))
            self.assertEqual(saved["inference_composition"],c148.EVAL_MODE)
            self.assertEqual(meta["sha256"],c148._sha(path))

    def test_fresh_seed_set_does_not_reuse_recent_experiments(self):
        self.assertEqual(c148.SEEDS,tuple(range(20261681,20261693)))
        self.assertFalse(set(c148.SEEDS)&set(range(20261581,20261673)))
        self.assertEqual((c148.STEPS,c148.LR,c148.SCALE),(600,.002,12))

    def test_synthetic_full_prior_reaggregation(self):
        data,suite,audit,paired=_synthetic_prior()
        c148._validate_prior(data,suite,audit,paired)

    def test_prior_rejects_wrong_identity_summary_only_and_seed_duplicates(self):
        data,suite,audit,paired=_synthetic_prior()
        for field,value in (("experiment_id","wrong"),("records","omitted"),("commit_sha","wrong")):
            modified=dict(data);modified[field]=value
            with self.assertRaises(ValueError): c148._validate_prior(modified,suite,audit,paired)
        data["records"][0]["seed"]=data["records"][1]["seed"]
        with self.assertRaises(ValueError): c148._validate_prior(data,suite,audit,paired)

    def test_prior_rejects_changed_predictions_pair_or_fit(self):
        for mutation in ("case","pair","fit"):
            data,suite,audit,paired=_synthetic_prior()
            r=data["records"][0]
            if mutation=="case": r["modes"][c148.EVAL_MODE]["results"][0].update(correct=False,predicted_address=16,expected_margin=-.1)
            elif mutation=="pair": r["paired"]["new_errors"]=1
            else: r["source_training_alignment_accuracy"]["COLOR"]=.5
            with self.assertRaises(ValueError): c148._validate_prior(data,suite,audit,paired)


if __name__ == "__main__":
    unittest.main()
