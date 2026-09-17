"""Development tests for C173; real dependencies, no model or source substitutes."""
from dataclasses import asdict, fields, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_derived_result as proof
from fold_lm.v05 import structured_action_runtime as action
from fold_lm.v05 import structured_acquisition_lifecycle as api
from fold_lm.v05_benchmarks import gate_e_c173_acquisition_lifecycle as bench

class C173Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.sources=bench.write_sources(Path(self.temp.name)/'sources')
    def scenario(self,tool='RETRIEVE',bit=0,view=None,fault=None):
        return bench.Scenario(self.sources['bit'+str(bit)],tool,view,fault)
    def run_dispatch(self,**kwargs):
        s=self.scenario(**kwargs);r=s.dispatch(s.reserve());return s,r
    def test_01_zero_is_published(self):
        s,r=self.run_dispatch();self.assertEqual((r.status,r.evidence.value),('PUBLISHED',0))
        self.assertEqual(s.owner.state.view.facts[1].status,'OBSERVED')
    def test_02_one_is_published(self):
        s,r=self.run_dispatch(bit=1);self.assertEqual(r.evidence.value,1)
    def test_03_all_named_tools_use_only_registered_callback(self):
        for tool in task.TOOLS:
            with self.subTest(tool=tool):
                s,r=self.run_dispatch(tool=tool);self.assertEqual(s.calls,1);self.assertEqual(r.evidence.action,tool)
    def test_04_epoch_and_other_facts_preserved(self):
        s=self.scenario();before=s.owner.state.view;s.dispatch(s.reserve());after=s.owner.state.view
        self.assertEqual((before.evidence_time,before.revision,before.facts[0]),(after.evidence_time,after.revision,after.facts[0]))
    def test_05_reservation_not_charged_twice(self):
        s,r=self.run_dispatch();self.assertEqual(s.owner.state.view.resources.acquisitions_remaining,0)
        self.assertEqual((r.internal_charged,r.provider_calls), (2,1))
    def test_06_duplicate_dispatch_does_not_read_again(self):
        s=self.scenario();i=s.reserve();s.dispatch(i);state=s.owner.state
        self.assertEqual(s.dispatch(i).reason,'NO_PENDING_INTENT');self.assertIs(s.owner.state,state);self.assertEqual(s.calls,1)
    def test_07_permission_revocation_prevents_read(self):
        s=self.scenario();i=s.reserve();v=s.owner.state.view;s.owner.refresh(replace(v,resources=replace(v.resources,permitted=(False,True,True))))
        r=s.dispatch(i);self.assertEqual((r.reason,r.provider_calls),('PERMISSION_DENIED',0));self.assertEqual(s.calls,0)
    def test_08_availability_revocation_prevents_read(self):
        s=self.scenario();i=s.reserve();v=s.owner.state.view;s.owner.refresh(replace(v,resources=replace(v.resources,available=(False,True,True))))
        self.assertEqual(s.dispatch(i).reason,'PROVIDER_UNAVAILABLE');self.assertEqual(s.provider.reads,0)
    def test_09_zero_and_one_internal_budget_prevent_side_effect(self):
        for budget in (0,1):
            s=self.scenario();i=s.reserve();v=s.owner.state.view;s.owner.refresh(replace(v,resources=replace(v.resources,internal_remaining=budget)))
            before=s.owner.state;r=s.dispatch(i);self.assertEqual(r.reason,'INTERNAL_BUDGET_EXHAUSTED');self.assertIs(s.owner.state,before)
    def test_10_stale_expression_clears_intent_without_io(self):
        s=self.scenario();i=s.reserve();v=s.owner.state.view;s.owner.refresh(replace(v,nodes=(*v.nodes[:-1],replace(v.nodes[-1],kind='OR'))))
        self.assertEqual(s.dispatch(i).reason,'STALE_RESERVATION');self.assertIsNone(s.owner.state.pending);self.assertEqual(s.calls,0)
    def test_11_stale_fact_is_detected(self):
        s=self.scenario();i=s.reserve();v=s.owner.state.view;s.owner.refresh(replace(v,facts=(replace(v.facts[0],value=0),v.facts[1])))
        self.assertEqual(s.dispatch(i).reason,'STALE_RESERVATION')
    def test_12_wrong_intent_does_not_cancel_real_one(self):
        s=self.scenario();i=s.reserve();before=s.owner.state
        self.assertEqual(s.dispatch('wrong').reason,'INTENT_MISMATCH');self.assertIs(s.owner.state,before)
        self.assertEqual(s.dispatch(i).status,'PUBLISHED')
    def test_13_stop_blocks_dispatch_without_refund(self):
        s=self.scenario();i=s.reserve();s.apply('STOP');self.assertEqual(s.dispatch(i).reason,'NO_PENDING_INTENT')
        self.assertEqual(s.owner.state.view.resources.acquisitions_remaining,0);self.assertEqual(s.calls,0)
    def test_14_missing_delivery_has_no_payload(self):
        s,r=self.run_dispatch(fault='missing');self.assertEqual(r.reason,'MISSING_DELIVERY');self.assertIsNone(r.evidence)
        self.assertIsNone(s.owner.state.view.facts[1].value)
    def test_15_delivery_bindings_reject_changed_fields(self):
        for fault in bench.FAULTS[1:11]:
            with self.subTest(fault=fault):
                s,r=self.run_dispatch(fault=fault);self.assertEqual(r.reason,'DELIVERY_BINDING_MISMATCH');self.assertIsNone(r.evidence)
    def test_16_payload_types_and_reference_reject(self):
        for fault in ('reference','boolean','float','range','payload_none','status'):
            with self.subTest(fault=fault):
                s,r=self.run_dispatch(fault=fault);self.assertEqual(r.reason,'INVALID_EVIDENCE')
    def test_17_valid_bit_flip_is_checked_against_source_witness(self):
        s,r=self.run_dispatch(fault='value_flip');self.assertEqual(r.reason,'INVALID_EVIDENCE')
        self.assertIsNone(s.owner.state.view.facts[1].value)
    def test_18_false_missing_cannot_override_real_record(self):
        s,r=self.run_dispatch(fault='false_missing');self.assertEqual(r.status,'REJECTED')
    def test_19_provider_failure_closes_attempt_without_refund(self):
        s,r=self.run_dispatch(fault='exception');self.assertEqual(r.reason,'PROVIDER_FAILURE')
        self.assertEqual(s.calls,1);self.assertIsNone(s.owner.state.pending);self.assertEqual(s.apply('RETRIEVE',fact_index=1).reason,'BUDGET_EXHAUSTED')
    def test_20_unexpected_exception_consumes_attempt_then_propagates(self):
        s=self.scenario();i=s.reserve()
        def bad(request): raise RuntimeError('test unexpected')
        s.extra=bad
        with self.assertRaises(RuntimeError): s.owner.dispatch(i)
        self.assertIsNone(s.owner.state.pending);self.assertEqual(len(s.owner.dispatched_intents),1)
        self.assertEqual(s.owner.dispatch(i).provider_calls,0)
    def test_21_source_hash_mismatch_rejected(self):
        s=bench.Scenario(self.sources['hash_mismatch'],'RETRIEVE');r=s.dispatch(s.reserve())
        self.assertEqual((r.reason,s.provider.reads),('PROVIDER_FAILURE',1))
    def test_22_malformed_sources_rejected(self):
        for name in ('duplicate_fact','boolean_bit','float_bit','wrong_epoch','malformed_json'):
            with self.subTest(name=name):
                s=bench.Scenario(self.sources[name],'RETRIEVE');r=s.dispatch(s.reserve());self.assertEqual(r.reason,'PROVIDER_FAILURE')
    def test_23_oversized_read_is_bounded(self):
        s=bench.Scenario(self.sources['oversize'],'RETRIEVE');s.dispatch(s.reserve())
        self.assertEqual(s.provider.bytes_read,api.MAX_SOURCE_BYTES+1);self.assertIsNone(s.owner.state.view.facts[1].value)
    def test_24_missing_record_is_not_zero_or_nonexistence(self):
        s=bench.Scenario(self.sources['missing_record'],'RETRIEVE');r=s.dispatch(s.reserve())
        self.assertEqual(r.reason,'RECORD_UNBOUND');self.assertEqual(s.owner.state.view.facts[1].status,'UNOBSERVED')
    def test_25_source_witness_not_exposed_in_receipts_or_policy(self):
        s,r=self.run_dispatch();self.assertNotIn('source_document',asdict(r.evidence))
        packet=task.encode(s.owner.state.view);self.assertNotIn('source_document',asdict(packet));self.assertEqual(len(packet.features),72)
    def test_26_admission_invalidates_staged_candidate(self):
        v=bench.initial_view('OR',controlling=True,bit=1);s=self.scenario(view=v);old=bench.short_candidate(v)
        s.apply('COMPUTE',candidate=old);s.dispatch(s.reserve());self.assertIsNone(s.owner.state.staged)
        self.assertEqual(s.apply('ANSWER').reason,'NO_CANDIDATE')
    def test_27_old_proof_rejects_after_fact_update(self):
        v=bench.initial_view('OR',controlling=True,bit=1);s=self.scenario(view=v);old=bench.short_candidate(v)
        s.dispatch(s.reserve());s.apply('COMPUTE',candidate=old);self.assertEqual(s.apply('ANSWER').reason,'EVIDENCE_MISMATCH')
    def test_28_new_proof_uses_actual_admitted_fact(self):
        for op in ('AND','OR'):
            for bit in (0,1):
                s=self.scenario(bit=bit,view=bench.initial_view(op));s.dispatch(s.reserve())
                s.apply('COMPUTE',candidate=bench.both_candidate(s.owner.state.view));r=s.apply('ANSWER')
                self.assertEqual((r.status,r.derived.value,r.checked_steps),('VERIFIED_DERIVED',bit,3))
    def test_29_reentrant_dispatch_and_action_cannot_execute(self):
        s=self.scenario();i=s.reserve()
        def callback(request):
            self.assertEqual(s.owner.dispatch(i).reason,'TRANSPORT_BUSY')
            self.assertEqual(s.owner.apply(action.propose(s.owner.state,'STOP')).result.reason,'TRANSPORT_BUSY')
            return s.provider(request)
        s.extra=callback;s.dispatch(i);self.assertEqual(s.calls,1);self.assertEqual(s.provider.reads,1)
    def test_30_replayed_delivery_cannot_populate_other_target(self):
        s=self.scenario(view=bench.initial_view(acquisitions=2,third=True));s.dispatch(s.reserve())
        old=s.last_delivery;s.extra=lambda request:old;r=s.dispatch(s.reserve(2))
        self.assertEqual(r.reason,'DELIVERY_BINDING_MISMATCH');self.assertIsNone(s.owner.state.view.facts[2].value)
        self.assertEqual((s.calls,s.provider.reads,len(s.owner.receipts)),(2,1,1))
    def test_31_dispatch_limit_is_hard(self):
        path,binding=self.sources['bit0'];p=api.FileSnapshotProvider(path,binding)
        o=api.AcquisitionOwner(action.RuntimeState(bench.initial_view(acquisitions=2,third=True)),{'RETRIEVE':api.Endpoint(binding,p)},max_dispatches=1)
        i=o.apply(action.propose(o.state,'RETRIEVE',fact_index=1)).result.intent.intent_id;o.dispatch(i)
        i=o.apply(action.propose(o.state,'RETRIEVE',fact_index=2)).result.intent.intent_id
        self.assertEqual(o.dispatch(i).reason,'ATTEMPT_LIMIT');self.assertEqual(p.reads,1)
    def test_32_refresh_cannot_refill_or_run_during_dispatch(self):
        s=self.scenario();i=s.reserve();v=s.owner.state.view
        with self.assertRaises(ValueError): s.owner.refresh(replace(v,resources=replace(v.resources,acquisitions_remaining=2)))
        def callback(request):
            with self.assertRaises(ValueError): s.owner.refresh(s.owner.state.view)
            return s.provider(request)
        s.extra=callback;s.dispatch(i)
    def test_33_missing_endpoint_and_epoch_fail_before_io(self):
        o=api.AcquisitionOwner(action.RuntimeState(bench.initial_view()),{})
        i=o.apply(action.propose(o.state,'RETRIEVE',fact_index=1)).result.intent.intent_id
        self.assertEqual(o.dispatch(i).reason,'PROVIDER_UNAVAILABLE')
        path,binding=self.sources['bit0'];p=api.FileSnapshotProvider(path,replace(binding,evidence_time=2))
        o=api.AcquisitionOwner(action.RuntimeState(bench.initial_view()),{'RETRIEVE':api.Endpoint(p.source,p)})
        i=o.apply(action.propose(o.state,'RETRIEVE',fact_index=1)).result.intent.intent_id
        self.assertEqual(o.dispatch(i).reason,'SOURCE_EPOCH_MISMATCH');self.assertEqual(p.reads,0)
    def test_34_strict_bindings_and_witness_shape(self):
        for kwargs in (dict(provider_id=''),dict(source_sha256='bad'),dict(evidence_time=True)):
            with self.assertRaises(ValueError): replace(self.sources['bit0'][1],**kwargs)
        s=self.scenario();i=s.reserve()
        s.extra=lambda request:replace(s.provider(request),source_document='not the source')
        self.assertEqual(s.dispatch(i).reason,'INVALID_EVIDENCE')
    def test_35_manifest_and_group_totals_are_fixed(self):
        self.assertEqual(sum(bench.GROUPS.values()),122);self.assertEqual(len(bench.FAULTS),20)
        self.assertEqual(hashlib.sha256(bench.blob(bench.manifest())).hexdigest(),bench.MANIFEST_SHA)
    def test_36_gate_checks_every_deciding_count(self):
        s=dict(scenarios=122,counts=bench.GROUPS,failed_checks=0,provider_calls=98,file_read_attempts=95,
            fact_publications=24,acquisition_reserved=122,verified_derived=12,verifier_calls=18,checked_steps=36,
            internal_charged=417,action_calls=236,dispatch_calls=143)
        self.assertTrue(bench.gate(s))
        for k in s:
            bad=dict(s);bad[k]={} if k=='counts' else s[k]+1
            self.assertFalse(bench.gate(bad),k)

if __name__=='__main__': unittest.main()
