"""Tests of the actual new input module; no replacement dependency definitions."""
import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from fold_lm.v05 import structured_task_input as a
from fold_lm.v05_benchmarks import gate_e_c170_structured_task_input as b


class StructuredInputTests(unittest.TestCase):
    def simple(self,value=None):
        return b.view((a.Node('FACT',0),),(value,))

    def test_01_roundtrip(self):
        t=b.view(b.templates()[6][2],(0,None,1))
        self.assertEqual(a.decode(a.encode(t)),t)

    def test_02_zero_not_unknown(self):
        self.assertNotEqual(a.encode(self.simple(0)).features,a.encode(self.simple()).features)

    def test_03_tree_roles_are_not_pooled(self):
        left=b.view(b.templates()[6][2],(None,None,None))
        right=b.view(b.templates()[7][2],(None,None,None))
        self.assertNotEqual(a.encode(left).features,a.encode(right).features)

    def test_04_leaf_negation_survives(self):
        t=b.view((a.Node('FACT',0,negate=True),),(0,))
        self.assertEqual(a.decode(a.encode(t)),t)
        self.assertNotEqual(a.encode(t).features,a.encode(self.simple(0)).features)

    def test_05_repeated_fact_occurrences_preserved(self):
        t=b.view(b.templates()[2][2],(1,))
        self.assertEqual(len(a.decode(a.encode(t)).nodes),3)
        self.assertEqual(a.decode(a.encode(t)).nodes[0].fact,a.decode(a.encode(t)).nodes[1].fact)

    def test_06_disconnected_nodes_rejected(self):
        with self.assertRaises(ValueError):
            b.view((a.Node('FACT',0),a.Node('FACT',0)),(None,))

    def test_07_unknown_fact_and_forward_children_rejected(self):
        with self.assertRaises(ValueError): b.view((a.Node('FACT',1),),(None,))
        with self.assertRaises(ValueError): b.view((a.Node('AND',left=0,right=0),),(None,))

    def test_08_observed_bit_is_not_boolean_or_float(self):
        for value in (True,0.,2,None):
            with self.subTest(value=value),self.assertRaises(ValueError): a.Fact('A','OBSERVED',value,('r',))

    def test_09_unusable_payloads_rejected(self):
        for status in a.STATUSES:
            if status!='OBSERVED':
                with self.subTest(status=status),self.assertRaises(ValueError): replace(b.fact_status(0,status),value=0)

    def test_10_unobserved_support_rejected(self):
        with self.assertRaises(ValueError): a.Fact('A',reference_ids=('r',))

    def test_11_conflict_retains_two_distinct_identities(self):
        for refs in ((),('r',),('r','r')):
            with self.subTest(refs=refs),self.assertRaises(ValueError): a.Fact('A','CONFLICT',None,refs)
        self.assertEqual(a.Fact('A','CONFLICT',None,('r','s')).value,None)

    def test_12_duplicate_fact_ids_rejected(self):
        with self.assertRaises(ValueError): replace(self.simple(),facts=(a.Fact('A'),a.Fact('A')))

    def test_13_mutable_containers_rejected(self):
        with self.assertRaises(TypeError): replace(self.simple(),facts=[a.Fact('A')])
        with self.assertRaises(TypeError): a.Fact('A',reference_ids=[])

    def test_14_bounds_fail_closed(self):
        with self.assertRaises(ValueError): replace(self.simple(),facts=tuple(a.Fact(str(i)) for i in range(5)))
        with self.assertRaises(ValueError): replace(self.simple(),nodes=())

    def test_15_resource_flags_are_explicit_booleans(self):
        with self.assertRaises(ValueError): a.Resources(available=(1,False,False))
        with self.assertRaises(ValueError): a.Resources(permitted=(False,))

    def test_16_no_oracle_arguments(self):
        names=set(inspect.signature(a.TaskView).parameters)|set(inspect.signature(a.encode).parameters)
        self.assertFalse(names & {'dependency','expected_value','requires_acquisition','hidden_value','label'})

    def test_17_unknown_payload_placeholder_rejected(self):
        p=a.encode(self.simple());x=list(p.features);x[49]=1
        with self.assertRaises(ValueError): a.decode(replace(p,features=tuple(x)))

    def test_18_nonzero_padding_rejected(self):
        p=a.encode(self.simple());x=list(p.features);x[10]=1
        with self.assertRaises(ValueError): a.decode(replace(p,features=tuple(x)))

    def test_19_boolean_feature_rejected(self):
        p=a.encode(self.simple());x=list(p.features);x[0]=True
        with self.assertRaises(ValueError): a.decode(replace(p,features=tuple(x)))

    def test_20_status_codes_checked(self):
        p=a.encode(self.simple());x=list(p.features);x[47]=99
        with self.assertRaises(ValueError): a.decode(replace(p,features=tuple(x)))

    def test_21_schema_mismatch_rejected(self):
        with self.assertRaises(ValueError): a.decode(replace(a.encode(self.simple()),schema='old'))

    def test_22_binding_count_checked(self):
        p=a.encode(self.simple())
        with self.assertRaises(ValueError): a.decode(replace(p,binding=replace(p.binding,fact_ids=())))

    def test_23_integer_range_exact_for_float32(self):
        with self.assertRaises(ValueError): a.Resources(internal_remaining=a.MAX_INTEGER+1)
        t=replace(self.simple(),resources=a.Resources(internal_remaining=a.MAX_INTEGER))
        self.assertEqual(a.decode(a.encode(t)),t)

    def test_24_actual_consumer_receives_complete_vector(self):
        got=[]
        def reader(x): got.append(x);return a.decode(x)
        reader.input_schema=a.SCHEMA
        t=b.view(b.templates()[8][2],(None,0,1,None))
        self.assertEqual(a.deliver(t,reader),t);self.assertEqual(len(got[0].features),72)

    def test_25_legacy_consumer_not_silently_adapted(self):
        with self.assertRaises(TypeError): a.deliver(self.simple(),lambda *args:None)

    def test_26_packet_and_view_immutable(self):
        p=a.encode(self.simple())
        with self.assertRaises(FrozenInstanceError): p.schema='changed'
        with self.assertRaises(TypeError): p.features[0]=99

    def test_27_bindings_are_separate_from_numeric_task(self):
        t=self.simple(1);renamed=replace(t,facts=(replace(t.facts[0],fact_id='RENAMED',reference_ids=('other-ref',)),))
        self.assertEqual(a.encode(t).features,a.encode(renamed).features)
        self.assertNotEqual(a.encode(t).binding,a.encode(renamed).binding)
        self.assertEqual(a.decode(a.encode(renamed)),renamed)

    def test_28_all_runtime_outcomes_roundtrip(self):
        for outcome in a.OUTCOMES:
            t=replace(self.simple(),resources=a.Resources(last_outcome=outcome))
            self.assertEqual(a.decode(a.encode(t)),t)

    def test_29_scope_binding_rejected(self):
        with self.assertRaises(ValueError): replace(self.simple(),request_id='elsewhere|q')

    def test_30_plan_is_deterministic_and_label_free(self):
        self.assertEqual(b.blob(b.manifest()),b.blob(b.manifest()))
        self.assertEqual(len(b.manifest()['templates']),10)
        self.assertFalse(b.manifest()['hidden_values_in_input'])

    def test_31_template_assignment_counts(self):
        rows=list(b.template_views());self.assertEqual(len(rows),252)
        self.assertEqual(len({name for name,_ in rows}),252)

    def test_32_operator_and_known_fact_reach_numeric_input(self):
        values=[]
        for op in ('AND','OR'):
            for bit in (0,1):
                t=b.view((a.Node('FACT',0),a.Node('FACT',1),a.Node(op,left=0,right=1)),(bit,None))
                values.append(a.encode(t).features)
        self.assertEqual(len(set(values)),4)

    def test_33_resource_grid_complete(self):
        rows=list(b.resource_views());self.assertEqual(len(rows),256)
        self.assertEqual(len({a.encode(t).features for _,t in rows}),256)

    def test_34_status_grid_complete_and_safe(self):
        rows=list(b.status_views());self.assertEqual(len(rows),16)
        self.assertTrue(all(f.value is None for _,t in rows for f in t.facts if f.status!='OBSERVED'))

    def test_35_all_registered_malformed_controls(self):
        rows=b.check_malformed();self.assertEqual(len(rows),40)
        self.assertTrue(all(x['rejected'] for x in rows))

    def test_36_gate_rejects_collisions_coverage_and_missing_guards(self):
        s=dict(b.EXPECTED,failed_roundtrips=0,malformed_rejected=40,necessity_classes=4,
            necessity_conflicting_classes=0,necessity_error_lower_bound=0,resource_classes=256,feature_width=72)
        self.assertTrue(b.gate(s))
        for key,value in (('necessity_conflicting_classes',1),('malformed_rejected',39),('consumer_calls',531),('failed_roundtrips',1)):
            self.assertFalse(b.gate(dict(s,**{key:value})))


if __name__=='__main__': unittest.main()
