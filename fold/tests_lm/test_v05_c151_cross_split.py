from __future__ import annotations
from collections import Counter
import copy
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import torch
from fold_lm.v05_benchmarks import gate_e_c151_cross_split as c151


def rows():
    # Same registered TRAIN fixture; other fields are not read by the planner.
    d=['red round metal','red square wood','blue round stone','blue square glass','green triangular metal','green hexagonal wood','yellow triangular stone','yellow hexagonal glass']
    color={'red':('crimson','ruby','vermillion'),'blue':('azure','navy','cobalt'),'green':('verdant','emerald','jade'),'yellow':('golden','amber','lemon')}
    shape={'round':('circular','curved','ring'),'square':('boxy','angular','four-sided'),'triangular':('three-sided','pointed','triangle'),'hexagonal':('six-sided','honeycomb','hexagon')}
    material={'metal':('metallic','alloy','steel'),'wood':('timber','lumber','wooden'),'stone':('rocky','mineral','stony'),'glass':('crystal','vitreous','transparent')}
    return [dict(key=f'q{i}',descriptor=x,split='TRAIN_COMBINATION',validation='unused',
                 train=[' '.join(m[w][k] for m,w in zip((color,shape,material),x.split(),strict=True)) for k in range(3)]) for i,x in enumerate(d)]


class V05C151CrossSplitTests(unittest.TestCase):
    def test_plan_is_deterministic(self):
        self.assertEqual(c151._build_plan(rows()),c151._build_plan(rows()))

    def test_plan_matches_preregistered_sha(self):
        self.assertEqual(hashlib.sha256(c151._bytes(c151._build_plan(rows()))).hexdigest(),c151.PLAN_SHA)

    def test_source_is_not_mutated(self):
        data=rows(); before=copy.deepcopy(data); c151._build_plan(data); self.assertEqual(data,before)

    def test_validation_and_heldout_fields_do_not_change_plan(self):
        data=rows(); original=c151._build_plan(data)
        for r in data: r['validation']='poisoned'
        data.append(dict(split='UNSEEN_COMBINATION',descriptor='invalid',train=['invalid']))
        self.assertEqual(c151._build_plan(data),original)

    def test_four_splits_have_balanced_marginals(self):
        for split in c151._build_plan(rows())['splits']:
            for a in range(3):
                self.assertEqual(sorted(Counter(d.split()[a] for d in split['descriptors']).values()),[2]*4)

    def test_splits_are_mutually_disjoint_and_exclude_original_training(self):
        plan=c151._build_plan(rows()); used=set(plan['source_training_descriptors'])
        for split in plan['splits']:
            self.assertEqual(len(set(split['descriptors'])),8)
            self.assertFalse(used.intersection(split['descriptors'])); used.update(split['descriptors'])
        self.assertEqual(len(used),40)

    def test_all_training_queries_decode_to_their_declared_descriptor(self):
        maps,_=c151._vocabulary_schedule(rows())
        reverse=[{a:v for v,aliases in m.items() for a in aliases} for m in maps]
        for split in c151._build_plan(rows())['splits']:
            for q,y in zip(split['queries'],split['targets'],strict=True):
                self.assertEqual(' '.join(m[a] for m,a in zip(reverse,q.split(),strict=True)),split['descriptors'][y])

    def test_alias_slot_order_is_preserved_not_sorted(self):
        maps,_=c151._vocabulary_schedule(rows())
        self.assertEqual(maps[0]['red'],('crimson','ruby','vermillion'))
        self.assertEqual(maps[1]['hexagonal'],('six-sided','honeycomb','hexagon'))

    def test_every_split_contains_all_36_aliases(self):
        maps,_=c151._vocabulary_schedule(rows()); expected={a for m in maps for s in m.values() for a in s}
        for split in c151._build_plan(rows())['splits']:
            self.assertEqual({a for q in split['queries'] for a in q.split()},expected)

    def test_training_rows_contain_no_evaluation_fields(self):
        split=c151._build_plan(rows())['splits'][0]; r=c151._training_rows(split)
        self.assertEqual(len(r),8)
        self.assertTrue(all(set(x)=={'key','descriptor','split','train'} for x in r))
        self.assertEqual([q for x in r for q in x['train']],split['queries'])

    def test_seeds_are_partitioned_once_and_fresh(self):
        plan=c151._build_plan(rows())
        self.assertEqual([s for p in plan['splits'] for s in p['fresh_seeds']],list(c151.SEEDS))
        self.assertTrue(all(len(p['fresh_seeds'])==3 for p in plan['splits']))
        self.assertFalse(set(c151.SEEDS)&set(range(20261701,20261713)))

    def test_empty_and_malformed_source_rejected(self):
        bad=rows(); bad[0]['train']=['one']
        for data in ([],rows()[:-1],bad):
            with self.assertRaises(ValueError): c151._build_plan(data)

    def test_conflicting_alias_schedule_rejected(self):
        bad=rows(); bad[1]['train'][0]='different boxy timber'
        with self.assertRaises(ValueError): c151._build_plan(bad)

    def test_duplicate_source_record_rejected(self):
        bad=rows(); bad[-1]=copy.deepcopy(bad[0])
        with self.assertRaises(ValueError): c151._build_plan(bad)

    def test_cross_axis_alias_overlap_rejected(self):
        bad=rows()
        for r in bad: r['train']=[q.replace('circular','crimson') for q in r['train']]
        with self.assertRaises(ValueError): c151._build_plan(bad)

    def test_partition_uses_current_split_not_legacy_bucket(self):
        suite=dict(descriptors=['a','b'],queries=[dict(expected_address=0,bucket='TRAIN_COMBINATION'),dict(expected_address=1,bucket='NEW_COMBINATION')])
        result=[dict(correct=True,expected_margin=.2),dict(correct=False,expected_margin=-.1)]
        audit=lambda *args:dict(groups={'OLD':'remove'},errors=1)
        metrics=c151._partition_metrics(result,suite,['b'],audit)
        self.assertEqual(metrics['groups']['CURRENT_TRAIN_COMBINATION']['correct'],0)
        self.assertEqual(metrics['groups']['HELDOUT_COMBINATION']['correct'],1)
        self.assertNotIn('OLD',metrics['groups'])

    def test_empty_partition_rejected(self):
        with self.assertRaises(ValueError):
            c151._partition_metrics([dict(correct=True,expected_margin=.2)],dict(descriptors=['a'],queries=[dict(expected_address=0)]),['a'],lambda *args:dict(groups={}))

    def test_strict_gate_rejects_errors_ties_and_nonfinite(self):
        self.assertTrue(c151._perfect([dict(correct=True,expected_margin=.1)]))
        for m in (0.,-.1,float('nan'),float('inf')):
            self.assertFalse(c151._perfect([dict(correct=True,expected_margin=m)]))
        self.assertFalse(c151._perfect([dict(correct=False,expected_margin=.1)])); self.assertFalse(c151._perfect([]))

    def test_wrong_prior_rejected_before_auditor(self):
        auditor=Mock()
        with self.assertRaises(ValueError): c151._validate_prior(dict(experiment_id='C149'),{},auditor,auditor)
        auditor.assert_not_called()

    def test_valid_identity_with_missing_config_rejected(self):
        prior=dict(experiment_id=c151.PRIOR_ID,commit_sha=c151.PRIOR_COMMIT,status='PASS',diagnostic_execution_valid=True,
                   production_runtime_modified=False,gate_e_candidate=False,evaluation_manifest_sha256=c151.MANIFEST_SHA,summary={})
        with self.assertRaisesRegex(ValueError,'configuration'): c151._validate_prior(prior,{},Mock(),Mock())

    def test_checkpoint_metadata_and_safe_reconstruction(self):
        head=torch.nn.Linear(3,3)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'head.pt'
            out=c151._save_head(p,head,('x','y','z'),'S1','GLOBAL_CONCEPT',lambda h:'toy-fingerprint')
            data=torch.load(p,weights_only=True)
            self.assertEqual(data['experiment_id'],c151.EXPERIMENT_ID)
            self.assertEqual(data['split_plan_sha256'],c151.PLAN_SHA)
            self.assertEqual(data['auxiliary_candidate_scope'],'GLOBAL_CONCEPT')
            clone=torch.nn.Linear(3,3); clone.load_state_dict(data['state_dict'])
            self.assertTrue(torch.equal(head.weight,clone.weight)); self.assertEqual(out['sha256'],c151._sha(p))

    def test_serialization_canonical_and_nan_rejected(self):
        self.assertEqual(c151._bytes({'b':1,'a':2}),c151._bytes({'a':2,'b':1}))
        with self.assertRaises(ValueError): c151._bytes({'bad':float('nan')})

    def test_new_training_strings_do_not_overlap_old_training_strings(self):
        old={q for r in rows() for q in r['train']}
        for split in c151._build_plan(rows())['splits']:
            self.assertEqual(len(set(split['queries'])),24)
            self.assertFalse(old.intersection(split['queries']))

if __name__=='__main__': unittest.main()
