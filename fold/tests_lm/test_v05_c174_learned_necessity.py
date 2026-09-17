"""C174 development tests. No deciding pilot training/evaluation is invoked."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import inspect
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_necessity_probe as api
from fold_lm.v05_benchmarks import gate_e_c174_learned_necessity as b


class C174Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads(); torch.set_num_threads(2)
        cls.data = b.dataset()

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    def packet(self, op='AND', known=0):
        ns=(task.Node('FACT',0),task.Node('FACT',1),task.Node(op,left=0,right=1))
        return task.encode(b.make_view(ns,(known,None)))

    def toy(self):
        x=torch.arange(8*72,dtype=torch.float32).reshape(8,72)/1000
        return x,torch.tensor([0,1]*4,dtype=torch.int64)

    def pairs(self):
        def score(value):
            return dict(macro_group_balanced_accuracy=value,sufficient_recall=.8,needs_recall=.8)
        return [dict(seed=s,full=score(.8),ablated=score(.6),paired_initial_equal=True,
                     paired_batches_equal=True) for s in api.SEEDS], score(.7)

    def test_01_exact_dependency_copy(self):
        raw=Path(task.__file__).read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                         'b874b6abf17fb938a5cc873ff2090c6493f00010')

    def test_02_registered_profile_and_data_hash(self):
        self.assertEqual(self.data['profile'],b.EXPECTED_DATA)
        self.assertEqual(self.data['content_sha256'],b.DATA_SHA)

    def test_03_structure_count_and_unique_syntax(self):
        rows=list(b.structures())
        self.assertEqual(len(rows),640)
        self.assertEqual(len({r['nodes'] for r in rows}),640)
        self.assertTrue(all(len(r['nodes'])==7 for r in rows))

    def test_04_all_shapes_are_valid_read_once(self):
        for r in b.structures():
            view=b.make_view(r['nodes'],(None,)*4)
            self.assertEqual(sorted(n.fact for n in view.nodes if n.kind=='FACT'),[0,1,2,3])
            self.assertEqual(task.decode(task.encode(view)),view)

    def test_05_hand_checked_necessity_cases(self):
        for op,a,wanted in [('AND',0,0),('AND',1,1),('OR',0,1),('OR',1,0)]:
            ns=(task.Node('FACT',0),task.Node('FACT',1),task.Node(op,left=0,right=1))
            table=tuple(b.evaluate(ns,v) for v in b.BITS)
            self.assertEqual(b.label_for(table,(a,None,None,None)),wanted)

    def test_06_all_observed_always_sufficient(self):
        for row in b.structures():
            self.assertTrue(all(b.label_for(row['truth_table'],bits)==0 for bits in b.BITS))

    def test_07_all_unknown_read_once_needs_observation(self):
        self.assertTrue(all(b.label_for(r['truth_table'],(None,)*4)==1 for r in b.structures()))

    def test_08_variable_permutations_share_semantic_group(self):
        row=next(b.structures());table=row['truth_table'];wanted=b.semantic_group(table)
        for p in b.PERMUTATIONS:
            changed=tuple(table[b.BITS.index(tuple(v[p[i]] for i in range(4)))] for v in b.BITS)
            self.assertEqual(b.semantic_group(changed),wanted)
            self.assertEqual(b.semantic_group(tuple(1-v for v in changed)),wanted)

    def test_09_train_eval_have_no_semantic_group_overlap(self):
        d=self.data;train=d['split_codes']==0
        self.assertFalse(set(d['groups'][train]) & set(d['groups'][~train]))
        self.assertEqual(len(set(d['groups'][~train])),4)

    def test_10_known_development_groups_never_eval(self):
        for g in b.known_development_groups(): self.assertEqual(b.partition(g),'TRAIN')

    def test_11_every_template_assignment_stays_in_one_split(self):
        d=self.data
        for ti in range(640):
            mask=d['template_ids']==ti
            self.assertEqual(int(mask.sum()),81)
            self.assertEqual(len(set(d['split_codes'][mask])),1)

    def test_12_no_unknown_value_in_features(self):
        x=self.data['features']
        for i in range(4):
            start=46+4*i;missing=x[:,start+2]==0
            self.assertTrue(np.all(x[missing,start+3]==0))

    def test_13_model_parameter_count_and_raw_shape(self):
        m=api.NecessityProbe()
        self.assertEqual(sum(p.numel() for p in m.parameters()),26114)
        self.assertEqual(tuple(m(torch.zeros((3,72),dtype=torch.float32)).shape),(3,2))

    def test_14_bad_model_shape_or_dtype_is_rejected(self):
        m=api.NecessityProbe()
        for x in (torch.zeros(72),torch.zeros(2,71),torch.zeros(2,72,dtype=torch.float64)):
            with self.assertRaises(ValueError): m(x)

    def test_15_packet_schema_is_checked(self):
        p=self.packet()
        self.assertEqual(api.packet_values(p),p.features)
        with self.assertRaises(ValueError): api.packet_values(replace(p,schema='legacy'))

    def test_16_numeric_input_excludes_opaque_binding_names(self):
        p=self.packet();v=task.decode(p)
        other=replace(v,request_id='other|renamed',scope_id='other',facts=tuple(
            replace(f,fact_id='id'+str(i),reference_ids=() if f.value is None else ('new:'+str(i),))
            for i,f in enumerate(v.facts)))
        self.assertEqual(api.packet_values(p),api.packet_values(task.encode(other)))

    def test_17_ablation_changes_only_node_fields_and_preserves_input(self):
        raw=torch.tensor([self.packet().features],dtype=torch.int32);copy=raw.clone()
        full=api.prepare(raw,api.ARMS[0]);blind=api.prepare(raw,api.ARMS[1])
        self.assertTrue(torch.equal(raw,copy))
        self.assertTrue(torch.equal(full[:,:4],blind[:,:4]))
        self.assertTrue(torch.equal(full[:,46:],blind[:,46:]))
        self.assertTrue(torch.equal(blind[:,4:46],torch.zeros_like(blind[:,4:46])))

    def test_18_operator_changes_reach_full_but_not_ablated_input(self):
        raw=torch.tensor([self.packet('AND').features,self.packet('OR').features],dtype=torch.int32)
        full=api.prepare(raw,api.ARMS[0]);blind=api.prepare(raw,api.ARMS[1])
        self.assertFalse(torch.equal(full[0],full[1]));self.assertTrue(torch.equal(blind[0],blind[1]))

    def test_19_fixed_scales_and_modes(self):
        self.assertEqual(len(api.SCALES),72)
        self.assertTrue(all(x>0 for x in api.SCALES))
        with self.assertRaises(ValueError): api.prepare(torch.zeros(1,72,dtype=torch.int32),'unknown')
        with self.assertRaises(ValueError): api.prepare(torch.zeros(1,72),'TASK_VISIBLE')

    def test_20_fit_signature_has_train_inputs_only(self):
        names=set(inspect.signature(api.fit).parameters)
        self.assertEqual(names,{'initial','x_train','y_train','seed','steps','batch_size','progress'})
        self.assertFalse({'labels','expected','groups','oracle'} & set(inspect.signature(api.predict).parameters))

    def test_21_tiny_train_is_deterministic_and_initial_preserved(self):
        torch.manual_seed(5);initial=api.NecessityProbe();before=api.fingerprint(initial);x,y=self.toy()
        a,la=api.fit(initial,x,y,123,steps=2,batch_size=4)
        c,lc=api.fit(initial,x,y,123,steps=2,batch_size=4)
        self.assertEqual(api.fingerprint(a),api.fingerprint(c));self.assertEqual(la,lc)
        self.assertEqual(api.fingerprint(initial),before);self.assertNotEqual(api.fingerprint(a),before)

    def test_22_paired_sampling_ignores_input_values(self):
        x,y=self.toy();initial=api.NecessityProbe()
        _,a=api.fit(initial,x,y,24,steps=2,batch_size=4)
        _,c=api.fit(initial,x+1,y,24,steps=2,batch_size=4)
        self.assertEqual(a['batch_schedule_sha256'],c['batch_schedule_sha256'])

    def test_23_invalid_training_input_rejected(self):
        x,y=self.toy();m=api.NecessityProbe()
        with self.assertRaises(ValueError): api.fit(m,x,y,0,steps=0)
        with self.assertRaises(ValueError): api.fit(m,x,torch.zeros_like(y),0,steps=1)
        x[0,0]=float('nan')
        with self.assertRaises(ValueError): api.fit(m,x,y,0,steps=1)

    def test_24_checkpoint_roundtrip_weights_only(self):
        m=api.NecessityProbe()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'weights.pt';torch.save({'state_dict':m.state_dict()},p)
            n=api.NecessityProbe();n.load_state_dict(torch.load(p,weights_only=True)['state_dict'])
            self.assertEqual(api.fingerprint(m),api.fingerprint(n))

    def test_25_prediction_has_no_state_or_label_mutation(self):
        m=api.NecessityProbe();x,_=self.toy();copy=x.clone();before=api.fingerprint(m)
        pred,logits=api.predict(m,x,batch_size=3)
        self.assertTrue(torch.equal(pred,logits.argmax(1)))
        self.assertEqual(api.fingerprint(m),before);self.assertTrue(torch.equal(x,copy))

    def test_26_macro_metric_keeps_function_groups_separate(self):
        m=b.metrics([0,1,0,1],[0,1,1,0],[1,1,2,2])
        self.assertEqual(m['macro_group_balanced_accuracy'],.5)
        self.assertEqual(m['per_group']['1']['balanced_accuracy'],1)
        self.assertEqual(m['per_group']['2']['balanced_accuracy'],0)

    def test_27_class_collapse_has_chance_balanced_accuracy(self):
        for bit in (0,1):
            m=b.metrics([0,0,1],[bit]*3,[0]*3)
            self.assertEqual(m['balanced_accuracy'],.5)

    def test_28_gate_requires_each_seed_and_paired_controls(self):
        pairs,base=self.pairs();self.assertTrue(b.gate(pairs,base))
        self.assertFalse(b.gate(pairs[:-1],base))
        pairs[1]['paired_batches_equal']=False;self.assertFalse(b.gate(pairs,base))

    def test_29_gate_rejects_ties_or_one_class_collapse(self):
        pairs,base=self.pairs();pairs[0]['full']['macro_group_balanced_accuracy']=.7
        self.assertFalse(b.gate(pairs,base))
        pairs,base=self.pairs();pairs[0]['full']['needs_recall']=.5
        self.assertFalse(b.gate(pairs,base))

    def test_30_manifest_is_frozen(self):
        self.assertEqual(hashlib.sha256(b.blob(b.manifest())).hexdigest(),b.MANIFEST_SHA)
        self.assertEqual(api.TRAIN_STEPS,2000);self.assertEqual(api.BATCH_SIZE,256)
        self.assertEqual(api.SEEDS,(174001,174002,174003))

    def test_31_npz_is_non_pickle_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.npz';x=self.data['features'][:4];np.savez_compressed(p,features=x)
            with np.load(p,allow_pickle=False) as restored: self.assertTrue(np.array_equal(restored['features'],x))

    def test_32_confusion_denominators_and_wrong_shapes(self):
        m=b.metrics([0,0,1,1],[0,1,1,1],[0]*4)
        self.assertEqual(m['confusion'],[[1,1],[0,2]])
        self.assertEqual(m['balanced_accuracy'],.75)
        with self.assertRaises(b.InvalidExecution): b.metrics([0,1],[0],[0,0])


if __name__ == '__main__':
    unittest.main()
