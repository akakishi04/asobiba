"""Development contract tests, not the artifact-backed C172 deciding batch."""
import hashlib
import inspect
import json
import unittest
from dataclasses import asdict, replace, FrozenInstanceError
from unittest.mock import patch

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_derived_result as proof
from fold_lm.v05 import structured_action_runtime as api
from fold_lm.v05_benchmarks import gate_e_c172_action_runtime as bench


class ActionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.s=bench.fixture()

    def take(self, name, state=None, **kwargs):
        s=self.s if state is None else state
        return api.step(s,api.propose(s,name,**kwargs))

    def test_01_names_are_not_legacy_indices(self):
        self.assertEqual(api.ACTIONS,('ANSWER','COMPUTE','RETRIEVE','OBSERVE','ASK_USER','STOP'))
        self.assertEqual(self.take(2).result.reason,'UNSUPPORTED_ACTION')

    def test_02_stage_is_unverified_without_solver(self):
        c=bench.candidate(self.s,value=0)
        with patch.object(proof,'verify',side_effect=AssertionError('staging must not verify')):
            t=self.take('COMPUTE',candidate=c)
        self.assertEqual(t.state.staged,c);self.assertIsNone(t.result.derived)
        self.assertEqual(t.result.status,'STAGED');self.assertEqual(t.result.internal_charged,1)

    def test_03_answer_accepts_valid_zero_and_one(self):
        for bit in (0,1):
            s=bench.fixture(bit);t=self.take('COMPUTE',s,candidate=bench.candidate(s))
            u=self.take('ANSWER',t.state)
            self.assertEqual(u.result.derived.value,bit);self.assertEqual(u.state.terminal,'ANSWERED')
            self.assertEqual(u.result.internal_charged,3);self.assertIsNone(u.state.staged)

    def test_04_answer_rejects_wrong_conclusion(self):
        t=self.take('COMPUTE',candidate=bench.candidate(self.s,0));u=self.take('ANSWER',t.state)
        self.assertEqual(u.result.reason,'CONCLUSION_MISMATCH');self.assertIsNone(u.result.derived)
        self.assertEqual(u.result.checked_steps,2)

    def test_05_unprepared_answer_is_not_fabricated(self):
        t=self.take('ANSWER');self.assertEqual(t.result.reason,'NO_CANDIDATE')
        self.assertEqual(t.result.internal_charged,1);self.assertIsNone(t.result.derived)

    def test_06_stop_at_zero_internal(self):
        s=bench.fixture(internal=0);t=self.take('STOP',s)
        self.assertEqual(t.state.terminal,'UNRESOLVED');self.assertEqual(t.result.internal_charged,0)

    def test_07_all_external_actions_reserve_not_observe(self):
        for name in task.TOOLS:
            t=self.take(name,fact_index=1)
            self.assertEqual(t.result.status,'PENDING');self.assertEqual(t.result.intent.action,name)
            self.assertEqual(t.state.view.facts,self.s.view.facts);self.assertEqual(t.result.acquisition_reserved,1)

    def test_08_permission_denial_before_availability(self):
        s=bench.fixture(available=False,permitted=False);t=self.take('RETRIEVE',s,fact_index=1)
        self.assertEqual(t.result.reason,'PERMISSION_DENIED');self.assertEqual(t.result.acquisition_reserved,0)

    def test_09_unavailable_provider(self):
        t=self.take('OBSERVE',bench.fixture(available=False),fact_index=1)
        self.assertEqual(t.result.reason,'PROVIDER_UNAVAILABLE')

    def test_10_acquisition_budget_zero(self):
        t=self.take('ASK_USER',bench.fixture(acquisitions=0),fact_index=1)
        self.assertEqual(t.result.reason,'BUDGET_EXHAUSTED');self.assertEqual(t.result.internal_charged,1)

    def test_11_internal_budget_zero(self):
        s=bench.fixture(internal=0);t=self.take('RETRIEVE',s,fact_index=1)
        self.assertIs(t.state,s);self.assertEqual(t.result.reason,'INTERNAL_BUDGET_EXHAUSTED')

    def test_12_known_fact_is_not_reacquired(self):
        t=self.take('RETRIEVE',fact_index=0)
        self.assertEqual(t.result.reason,'ALREADY_OBSERVED');self.assertEqual(t.result.acquisition_reserved,0)

    def test_13_exact_proposal_replay_is_stale(self):
        p=api.propose(self.s,'RETRIEVE',fact_index=1);t=api.step(self.s,p);u=api.step(t.state,p)
        self.assertEqual(u.result.reason,'STALE_STATE');self.assertIs(u.state,t.state)

    def test_14_pending_blocks_fresh_duplicate(self):
        t=self.take('ASK_USER',fact_index=1);u=self.take('ASK_USER',t.state,fact_index=1)
        self.assertEqual(u.result.reason,'PENDING_ACQUISITION');self.assertEqual(u.state.pending,t.state.pending)

    def test_15_pending_blocks_cross_tool(self):
        t=self.take('ASK_USER',fact_index=1);u=self.take('RETRIEVE',t.state,fact_index=1)
        self.assertEqual(u.result.acquisition_reserved,0);self.assertEqual(u.result.reason,'PENDING_ACQUISITION')

    def test_16_pending_blocks_compute(self):
        t=self.take('RETRIEVE',fact_index=1);u=self.take('COMPUTE',t.state,candidate=bench.candidate(t.state))
        self.assertEqual(u.result.reason,'PENDING_ACQUISITION');self.assertIsNone(u.state.staged)

    def test_17_stop_cancels_without_refund(self):
        t=self.take('ASK_USER',fact_index=1);u=self.take('STOP',t.state)
        self.assertIsNone(u.state.pending);self.assertEqual(u.state.view.resources.acquisitions_remaining,0)

    def test_18_closed_cannot_restart(self):
        t=self.take('STOP');u=self.take('RETRIEVE',t.state,fact_index=1)
        self.assertEqual(u.result.reason,'SESSION_CLOSED');self.assertIs(u.state,t.state)

    def test_19_state_binding_covers_resources(self):
        p=api.propose(self.s,'RETRIEVE',fact_index=1)
        s=replace(self.s,view=replace(self.s.view,resources=replace(self.s.view.resources,permitted=(False,)*3)))
        self.assertEqual(api.step(s,p).result.reason,'STALE_STATE')

    def test_20_state_binding_covers_evidence(self):
        p=api.propose(self.s,'STOP');v=replace(self.s.view,revision=2)
        self.assertEqual(api.step(replace(self.s,view=v),p).result.reason,'STALE_STATE')

    def test_21_state_binding_covers_expression(self):
        p=api.propose(self.s,'STOP');v=replace(self.s.view,nodes=(*self.s.view.nodes[:-1],task.Node('AND',left=0,right=1)))
        self.assertEqual(api.step(replace(self.s,view=v),p).result.reason,'STALE_STATE')

    def test_22_scope_binding(self):
        p=replace(api.propose(self.s,'STOP'),scope_id='wrong')
        self.assertEqual(api.step(self.s,p).result.reason,'REQUEST_SCOPE_MISMATCH')

    def test_23_numeric_target_type(self):
        for value in (True,1.0,4,-2):
            p=api.propose(self.s,'RETRIEVE',fact_index=value)
            self.assertEqual(api.step(self.s,p).result.reason,'INVALID_ARGUMENT')

    def test_24_malformed_proposals_no_state_change(self):
        rows=bench.malformed();self.assertEqual(len(rows),24)
        for name,p in rows:
            with self.subTest(name=name):
                t=api.step(self.s,p);self.assertEqual(t.result.status,'REJECTED');self.assertIs(t.state,self.s)

    def test_25_immutable_candidate_container(self):
        c=replace(bench.candidate(self.s),proof=[])
        self.assertFalse(api.candidate_shape(c))
        with self.assertRaises(ValueError):replace(self.s,staged=c)

    def test_26_noncanonical_current_view_is_configuration_error(self):
        with self.assertRaises((TypeError,ValueError)):api.RuntimeState({})
        with self.assertRaises(TypeError):api.step({},None)

    def test_27_verification_capacity_no_hidden_debit(self):
        s=replace(bench.fixture(internal=2),staged=bench.candidate(self.s))
        t=self.take('ANSWER',s)
        self.assertEqual(t.result.reason,'VERIFICATION_BUDGET_EXHAUSTED')
        self.assertEqual(t.result.checked_steps,0);self.assertEqual(t.result.internal_charged,1)

    def test_28_exact_remaining_verification_budget(self):
        s=replace(bench.fixture(internal=3),staged=bench.candidate(self.s));t=self.take('ANSWER',s)
        self.assertEqual(t.result.status,'VERIFIED_DERIVED');self.assertEqual(t.state.view.resources.internal_remaining,0)

    def test_29_explicit_capacity_remains_binding(self):
        s=replace(self.s,staged=bench.candidate(self.s));t=api.step(s,api.propose(s,'ANSWER'),max_proof_steps=0)
        self.assertEqual(t.result.reason,'VERIFICATION_BUDGET_EXHAUSTED');self.assertEqual(t.result.internal_charged,1)

    def test_30_verifier_configuration_types(self):
        for value in (True,-1,8,1.5):
            with self.assertRaises(ValueError):api.step(self.s,api.propose(self.s,'STOP'),max_proof_steps=value)

    def test_31_version_bound(self):
        s=replace(self.s,transition=task.MAX_INTEGER);t=self.take('STOP',s)
        self.assertEqual(t.result.reason,'VERSION_LIMIT');self.assertIs(t.state,s)

    def test_32_internal_step_bound(self):
        s=replace(self.s,view=replace(self.s.view,resources=replace(self.s.view.resources,internal_step=task.MAX_INTEGER)))
        t=self.take('RETRIEVE',s,fact_index=1);self.assertEqual(t.result.reason,'INTERNAL_STEP_LIMIT')
        self.assertEqual(self.take('STOP',s).result.status,'UNRESOLVED')

    def test_33_readonly_inputs_and_bindings(self):
        before=bench.blob(asdict(self.s));p=api.propose(self.s,'RETRIEVE',fact_index=1);pb=bench.blob(asdict(p))
        api.step(self.s,p);self.assertEqual(before,bench.blob(asdict(self.s)));self.assertEqual(pb,bench.blob(asdict(p)))
        with self.assertRaises(FrozenInstanceError):self.s.transition=1

    def test_34_output_json_zero_and_none(self):
        s=bench.fixture(0);t=self.take('COMPUTE',s,candidate=bench.candidate(s));u=self.take('ANSWER',t.state)
        decoded=json.loads(bench.blob(asdict(u)));self.assertEqual(decoded['result']['derived']['value'],0)
        self.assertIsNone(json.loads(bench.blob(asdict(self.take('STOP'))))['result']['derived'])

    def test_35_manifest_counts_and_hash(self):
        self.assertEqual(sum(bench.EXPECTED.values()),197)
        self.assertEqual(hashlib.sha256(bench.blob(bench.manifest())).hexdigest(),bench.MANIFEST_SHA)

    def test_36_gate_rejects_finite_failures(self):
        s=dict(counts=bench.EXPECTED,calls=197,failed_checks=0,acquisition_reserved=27,
               internal_charged=147,verifier_calls=46,checked_steps=28)
        self.assertTrue(bench.gate(s));self.assertFalse(bench.gate(dict(s,failed_checks=1)))

    def test_37_no_oracle_or_provider_parameter(self):
        self.assertEqual(tuple(inspect.signature(api.step).parameters),('state','proposal','max_proof_steps'))
        self.assertNotIn('dependency',api.ActionProposal.__dataclass_fields__)

    def test_38_stale_fixture_coverage(self):
        p=api.propose(self.s,'RETRIEVE',fact_index=1);rows=bench.stale_states(self.s);self.assertEqual(len(rows),12)
        for name,s in rows:
            self.assertIn(api.step(s,p).result.reason,('STALE_STATE','REQUEST_SCOPE_MISMATCH'))

    def test_39_unusable_fact_reservation_is_not_observation(self):
        f=task.Fact('B','CONFLICT',None,('B:0','B:1'));s=replace(self.s,view=replace(self.s.view,facts=(self.s.view.facts[0],f)))
        t=self.take('OBSERVE',s,fact_index=1);self.assertEqual(t.state.view.facts[1],f)
        self.assertEqual(t.result.status,'PENDING')

    def test_40_staged_evidence_is_rechecked_at_answer(self):
        t=self.take('COMPUTE',candidate=bench.candidate(self.s));s=replace(t.state,view=replace(t.state.view,revision=2))
        u=self.take('ANSWER',s);self.assertEqual(u.result.reason,'CLOCK_MISMATCH')
        self.assertIsNone(u.result.derived)


if __name__=='__main__':unittest.main()
