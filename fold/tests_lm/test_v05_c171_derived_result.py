"""Development unit fixtures, not the hash-pinned C171 formal execution."""
from dataclasses import asdict, replace, FrozenInstanceError
import hashlib
import inspect
import json
import unittest

from fold_lm.v05 import structured_task_input as t
from fold_lm.v05 import structured_derived_result as a
from fold_lm.v05_benchmarks import gate_e_c171_derived_result as b

class DerivedResultTests(unittest.TestCase):
    def base(self,bit=1):
        v=b.short_view(bit)
        return v,b.candidate_fixture(v,bit)
    def accept(self,v,c):
        r=a.verify(v,c);self.assertEqual(r.status,'VERIFIED_DERIVED');return r
    def reject(self,v,c,reason=None):
        r=a.verify(v,c);self.assertEqual(r.status,'REJECTED');self.assertIsNone(r.value)
        self.assertEqual((r.proof,r.supporting_references),((),()))
        if reason:self.assertEqual(r.reason,reason)
        return r
    def test_01_observed_zero_leaf(self):
        v=b.make_view((t.Node('FACT',0),),(0,));self.assertEqual(self.accept(v,b.candidate_fixture(v,0)).value,0)
    def test_02_observed_one_leaf(self):
        v=b.make_view((t.Node('FACT',0),),(1,));self.assertEqual(self.accept(v,b.candidate_fixture(v,1)).value,1)
    def test_03_leaf_negation(self):
        v=b.make_view((t.Node('FACT',0,negate=True),),(0,));self.accept(v,b.candidate_fixture(v,1))
    def test_04_and_both(self):
        v=b.make_view(b.templates()[3][2],(1,1));c=b.candidate_fixture(v,1)
        self.assertEqual(c.proof[-1].rule,'AND_BOTH');self.accept(v,c)
    def test_05_or_both(self):
        v=b.make_view(b.templates()[4][2],(0,0));c=b.candidate_fixture(v,0)
        self.assertEqual(c.proof[-1].rule,'OR_BOTH');self.accept(v,c)
    def test_06_and_left_short(self):
        v,c=self.base(0);self.assertEqual(c.proof[-1].rule,'AND_LEFT_ZERO');self.accept(v,c)
    def test_07_and_right_short(self):
        v=b.make_view(b.templates()[3][2],(None,0));c=b.candidate_fixture(v,0)
        self.assertEqual(c.proof[-1].rule,'AND_RIGHT_ZERO');self.accept(v,c)
    def test_08_or_left_short(self):
        v,c=self.base(1);self.assertEqual(c.proof[-1].rule,'OR_LEFT_ONE');self.accept(v,c)
    def test_09_or_right_short(self):
        v=b.make_view(b.templates()[4][2],(None,1));c=b.candidate_fixture(v,1)
        self.assertEqual(c.proof[-1].rule,'OR_RIGHT_ONE');self.accept(v,c)
    def test_10_unknown_is_not_observation(self):
        v,c=self.base();before=asdict(v);r=self.accept(v,c)
        self.assertEqual(asdict(v),before);self.assertIsNone(v.facts[1].value)
        self.assertEqual(v.facts[1].status,'UNOBSERVED');self.assertEqual(len(r.supporting_references),1)
    def test_11_nested_proof(self):
        v=b.make_view(b.templates()[8][2],(1,1,None,None));self.accept(v,b.candidate_fixture(v,1))
    def test_12_repeated_fact_uses_one_support(self):
        v=b.make_view(b.templates()[2][2],(1,));c=b.candidate_fixture(v,1)
        self.assertEqual(len(c.proof),3);self.assertEqual(len(c.supporting_references),1);self.accept(v,c)
    def test_13_malformed_grid(self):
        for bit in (0,1):
            v,c=self.base(bit)
            self.assertEqual(len(b.corruptions(c)),24)
            for name,bad in b.corruptions(c):
                with self.subTest(bit=bit,case=name):self.reject(v,bad)
    def test_14_unusable_support_statuses(self):
        for status in t.STATUSES:
            if status=='OBSERVED':continue
            refs=() if status=='UNOBSERVED' else ('old','other') if status=='CONFLICT' else ('old',)
            v=t.TaskView('s|q','s',(t.Node('FACT',0),),(t.Fact('A',status,None,refs),))
            c=a.bind_candidate(v,0,(a.ProofStep(0,0,'OBSERVED_LEAF'),),(a.Support(0,'old'),))
            self.reject(v,c,'SUPPORT_NOT_USABLE')
    def test_15_changed_current_views_reject(self):
        v,c=self.base()
        for name,new in b.rebound_views(v):
            with self.subTest(name=name):self.reject(new,c)
    def test_16_resources_are_not_evidence(self):
        v,c=self.base()
        for new in b.resource_views(v):self.accept(new,c)
    def test_17_verification_capacity(self):
        v,c=self.base()
        for cap in (0,1,2,7):
            r=a.verify(v,c,max_steps=cap)
            self.assertLessEqual(r.checked_steps,cap)
            self.assertEqual(r.status,'VERIFIED_DERIVED' if cap>=2 else 'REJECTED')
    def test_18_noncanonical_node_order(self):
        v,c=self.base();self.reject(v,replace(c,proof=c.proof[::-1]))
    def test_19_wrong_branch_premise(self):
        v,c=self.base();self.reject(v,replace(c,proof=(c.proof[0],replace(c.proof[-1],premises=(1,)))))
    def test_20_leaf_value_disagreement(self):
        v,c=self.base();self.reject(v,replace(c,proof=(replace(c.proof[0],value=0),c.proof[-1])),'LEAF_VALUE_MISMATCH')
    def test_21_unused_proof_step(self):
        v=b.make_view(b.templates()[3][2],(0,1));c=b.candidate_fixture(v,0)
        steps=(c.proof[0],a.ProofStep(1,1,'OBSERVED_LEAF'),c.proof[-1])
        c=replace(c,proof=steps,supporting_references=(a.Support(0,'evidence:A'),a.Support(1,'evidence:B')))
        self.reject(v,c,'UNUSED_PROOF_STEP')
    def test_22_unused_support(self):
        v=b.make_view(b.templates()[3][2],(0,1));c=b.candidate_fixture(v,0)
        self.reject(v,replace(c,supporting_references=c.supporting_references+(a.Support(1,'evidence:B'),)),'UNUSED_SUPPORT')
    def test_23_noncanonical_support_order(self):
        v=b.make_view(b.templates()[3][2],(1,1));c=b.candidate_fixture(v,1)
        self.reject(v,replace(c,supporting_references=c.supporting_references[::-1]),'NONCANONICAL_SUPPORT')
    def test_24_invalid_capacity_is_configuration_error(self):
        v,c=self.base()
        for cap in (True,1.0,-1,8):
            with self.assertRaises(ValueError):a.verify(v,c,max_steps=cap)
    def test_25_invalid_current_view_is_not_a_candidate_error(self):
        _,c=self.base()
        with self.assertRaises(TypeError):a.verify({},c)
    def test_26_unobserved_leaf_no_proof(self):
        v=b.make_view((t.Node('FACT',0),),(None,))
        for bit in (0,1):self.reject(v,b.candidate_fixture(v,bit))
    def test_27_local_proofs_are_not_complete_boolean_solver(self):
        v=b.make_view((t.Node('FACT',0),t.Node('FACT',0,negate=True),t.Node('OR',left=0,right=1)),(None,))
        self.assertEqual(b.completion_values(v),(1,));self.reject(v,b.candidate_fixture(v,1),'MALFORMED_PROOF')
    def test_28_arbitrary_candidate_mapping_rejected(self):
        v,c=self.base();self.reject(v,asdict(c),'MALFORMED_CANDIDATE')
    def test_29_immutable_objects(self):
        v,c=self.base();r=self.accept(v,c)
        with self.assertRaises(FrozenInstanceError):r.value=0
        with self.assertRaises(FrozenInstanceError):c.proof=()
    def test_30_serialization_preserves_zero_none(self):
        v,c=self.base(0);yes=self.accept(v,c);no=self.reject(v,replace(c,value=True))
        self.assertIs(type(json.loads(b.blob(asdict(yes)))['value']),int)
        self.assertIsNone(json.loads(b.blob(asdict(no)))['value'])
    def test_31_template_assignment_scope(self):
        vs=list(b.reference_views());self.assertEqual(len(vs),252)
        self.assertEqual(len({name for name,_ in vs}),252)
    def test_32_manifest_hash_and_count(self):
        self.assertEqual(hashlib.sha256(b.blob(b.manifest())).hexdigest(),b.MANIFEST_SHA)
        self.assertEqual(sum(b.EXPECTED.values()),600)
    def test_33_gate_does_not_mask_failures(self):
        s=dict(counts=b.EXPECTED,verifier_calls=600,failed_checks=0,reference_false_accepts=0,reference_false_rejects=0,verified=1,rejected=599)
        self.assertTrue(b.gate(s))
        for key in ('failed_checks','reference_false_accepts','reference_false_rejects'):
            self.assertFalse(b.gate(dict(s,**{key:1})))
        self.assertFalse(b.gate(dict(s,verifier_calls=599)))
    def test_34_no_oracle_argument(self):
        self.assertEqual(tuple(inspect.signature(a.verify).parameters),('view','candidate','max_steps'))
        self.assertNotIn('proof_fixture',inspect.getsource(a))
        self.assertNotIn('completion_values',inspect.getsource(a))
    def test_35_reversed_ast_child_order_supported(self):
        v=b.make_view((t.Node('FACT',0),t.Node('FACT',1),t.Node('AND',left=1,right=0)),(1,1))
        self.accept(v,b.candidate_fixture(v,1))
    def test_36_root_rule_cannot_prove_from_noncontrolling_value(self):
        v=b.make_view(b.templates()[4][2],(0,None))
        steps=(a.ProofStep(0,0,'OBSERVED_LEAF'),a.ProofStep(2,1,'OR_LEFT_ONE',(0,)))
        self.reject(v,a.bind_candidate(v,1,steps,(a.Support(0,'evidence:A'),)),'NONCONTROLLING_PREMISE')

if __name__=='__main__':unittest.main()
