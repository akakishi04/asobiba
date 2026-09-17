"""C172: typed action, resource debit and acquisition-intent boundary.

Scripted proposals and trusted in-memory views, not a trained policy or transport.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import time

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_derived_result as proof
from fold_lm.v05 import structured_action_runtime as api

EXPERIMENT_ID = 'C172-v5e-typed-action-runtime-boundary'
STAGE = 'V5-E-TYPED-ACTION-RUNTIME-BOUNDARY'
BASE = '42bc2b83269a1279e50d51156de11b9d720b17c0'
PARENT_SHA = '4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c'
MANIFEST_SHA = 'c706b3dd02677b7c6e1ad00a813fa99cb6f2a318f5850c9b35271b0bb1e64c76'
EXPECTED = dict(external_grid=48, local=10, malformed=24, stale=12,
                pending=15, proof_rejection=24, proof_budget=40, fact_status=24)
PARENT_OWN = ('fold_lm/v05/structured_derived_result.py',
    'fold_lm/v05_benchmarks/gate_e_c171_derived_result.py',
    'tests_lm/test_v05_c171_derived_result.py', 'tools/run_c171.ps1',
    'docs/structured-derived-result-v0.1.md', 'docs/experiment-ledger-addendum-c171-preregistration.md')
OWN = ('fold_lm/v05/structured_action_runtime.py',
    'fold_lm/v05_benchmarks/gate_e_c172_action_runtime.py',
    'tests_lm/test_v05_c172_action_runtime.py', 'tools/run_c172.ps1',
    'docs/structured-action-runtime-v0.1.md', 'docs/experiment-ledger-addendum-c172-preregistration.md')


class InvalidExecution(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InvalidExecution(message)


def blob(x):
    return (json.dumps(x, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fixture(value=1, internal=8, acquisitions=1, available=True, permitted=True):
    nodes = (task.Node('FACT', 0), task.Node('FACT', 1),
             task.Node('OR' if value else 'AND', left=0, right=1))
    facts = (task.Fact('A', 'OBSERVED', value, ('evidence:A',)), task.Fact('B'))
    view = task.TaskView('C172|request', 'C172', nodes, facts,
                        task.Resources(internal, acquisitions, (available,)*3, (permitted,)*3))
    return api.RuntimeState(view)


def candidate(state, value=None):
    v = state.view.facts[0].value
    rule = 'OR_LEFT_ONE' if state.view.nodes[-1].kind == 'OR' else 'AND_LEFT_ZERO'
    return proof.bind_candidate(state.view, v if value is None else value,
        (proof.ProofStep(0, v, 'OBSERVED_LEAF'), proof.ProofStep(2, v, rule, (0,))),
        (proof.Support(0, 'evidence:A'),))


def malformed():
    s = fixture(); p = api.propose(s, 'RETRIEVE', fact_index=1)
    c = candidate(s); compute = api.propose(s, 'COMPUTE', candidate=c)
    return (
        ('mapping', asdict(p)), ('schema', replace(p, schema='legacy')),
        ('empty-request', replace(p, request_id='')), ('empty-scope', replace(p, scope_id='')),
        ('empty-token', replace(p, expected_state_sha256='')),
        ('numeric-action', replace(p, action=2)), ('unknown-action', replace(p, action='MAGIC')),
        ('missing-target', replace(p, fact_index=-1)), ('boolean-target', replace(p, fact_index=True)),
        ('float-target', replace(p, fact_index=1.0)), ('large-target', replace(p, fact_index=4)),
        ('external-payload', replace(p, candidate=c)),
        ('compute-no-candidate', replace(compute, candidate=None)),
        ('compute-target', replace(compute, fact_index=1)),
        ('candidate-mapping', replace(compute, candidate=asdict(c))),
        ('candidate-list-proof', replace(compute, candidate=replace(c, proof=list(c.proof)))),
        ('candidate-list-support', replace(compute, candidate=replace(c, supporting_references=list(c.supporting_references)))),
        ('candidate-long-proof', replace(compute, candidate=replace(c, proof=c.proof*4))),
        ('candidate-boolean-bit', replace(compute, candidate=replace(c, value=True))),
        ('candidate-float-bit', replace(compute, candidate=replace(c, value=1.0))),
        ('answer-injected-proof', api.propose(s, 'ANSWER', candidate=c)),
        ('answer-target', api.propose(s, 'ANSWER', fact_index=1)),
        ('stop-payload', api.propose(s, 'STOP', candidate=c)),
        ('stop-target', api.propose(s, 'STOP', fact_index=1)))


def stale_states(s):
    v = s.view; a, b = v.facts; r = v.resources
    return (
        ('request', replace(s, view=replace(v, request_id='C172|other'))),
        ('scope', replace(s, view=replace(v, request_id='other|request', scope_id='other'))),
        ('time', replace(s, view=replace(v, evidence_time=2))),
        ('revision', replace(s, view=replace(v, revision=2))),
        ('expression', replace(s, view=replace(v, nodes=(*v.nodes[:-1], replace(v.nodes[-1], kind='AND'))))),
        ('fact-id', replace(s, view=replace(v, facts=(replace(a, fact_id='other-A'), b)))),
        ('support-id', replace(s, view=replace(v, facts=(replace(a, reference_ids=('other-evidence:A',)), b)))),
        ('value', replace(s, view=replace(v, facts=(replace(a, value=0), b)))),
        ('availability', replace(s, view=replace(v, resources=replace(r, available=(False,)*3)))),
        ('permission', replace(s, view=replace(v, resources=replace(r, permitted=(False,)*3)))),
        ('allowance', replace(s, view=replace(v, resources=replace(r, acquisitions_remaining=0)))),
        ('transition', replace(s, transition=1)))


def corruptions(c):
    return (
        ('conclusion', replace(c, value=1-c.value)),
        ('support', replace(c, supporting_references=(proof.Support(0, 'invented'),))),
        ('expression', replace(c, expression_sha256='0'*64)),
        ('unobserved', replace(c, supporting_references=(proof.Support(1, 'invented-B'),))),
        ('rule', replace(c, proof=(replace(c.proof[0], rule='MAGIC'), c.proof[1]))),
        ('order', replace(c, proof=c.proof[::-1])))


def manifest():
    return dict(experiment_id=EXPERIMENT_ID, schema=api.SCHEMA, actions=list(api.ACTIONS),
        tools=list(task.TOOLS), external_grid='3 tools x available x permitted x acquisition0/1 x internal0/1',
        local='each bit: COMPUTE, ANSWER, closed ANSWER; unprepared ANSWER; zero-budget STOP',
        malformed_names=[n for n, _ in malformed()], stale_names=[n for n, _ in stale_states(fixture())],
        pending='each tool: reserve, exact replay, fresh duplicate, cross-tool request, STOP',
        corruption_names=[n for n, _ in corruptions(candidate(fixture()))],
        proof_budget_internal=[0,1,2,3,4], proof_capacities=[0,1,2,7], statuses=list(task.STATUSES),
        counts=EXPECTED, calls=197, maximum_proof_steps=7, parent_sha256=PARENT_SHA,
        authority_order=['pending','permission','availability','already-observed','acquisition-budget'],
        cost='non-STOP bound valid attempt=1 internal; ANSWER adds actual rule evaluations; intent reserves1 acquisition',
        external_completion=False, policy='scripted typed proposals', learned_forward_calls=0,
        real_provider_calls=0, evidence_writes=0, training_steps=0, fresh_seed_count=0)


def collect():
    rows = []; counts = Counter()
    def probe(group, name, s, p, status, reason=None, charged=0, reserved=0, value=None, capacity=7):
        before = blob(asdict(s)); pbefore = blob(asdict(p) if type(p) is api.ActionProposal else p)
        t = api.step(s, p, max_proof_steps=capacity); out = t.result; ns = t.state
        immut = blob(asdict(s)) == before and blob(asdict(p) if type(p) is api.ActionProposal else p) == pbefore
        binding = (out.schema == api.SCHEMA and out.request_id == s.view.request_id and out.scope_id == s.view.scope_id
            and out.action == (p.action if type(p) is api.ActionProposal and type(p.action) is str else None))
        facts_same = (ns.view.facts == s.view.facts and ns.view.nodes == s.view.nodes
            and (ns.view.evidence_time, ns.view.revision) == (s.view.evidence_time, s.view.revision))
        accounting = (out.internal_charged == charged and out.acquisition_reserved == reserved
            and ns.view.resources.internal_remaining == s.view.resources.internal_remaining-charged
            and ns.view.resources.acquisitions_remaining == s.view.resources.acquisitions_remaining-reserved
            and ns.view.resources.internal_step == s.view.resources.internal_step+charged
            and ns.transition == s.transition + int(charged > 0 or status == 'UNRESOLVED'))
        answer_ok = (out.derived is None if value is None else out.derived is not None
            and type(out.derived.value) is int and out.derived.value == value
            and out.derived.status == 'VERIFIED_DERIVED' and ns.terminal == 'ANSWERED')
        pending_ok = (out.intent is None if not reserved else out.intent is not None
            and out.intent == ns.pending and out.intent.fact_id == s.view.facts[p.fact_index].fact_id
            and out.intent.action == p.action and out.intent.origin_state_sha256 == api.state_digest(s))
        passed = (immut and binding and facts_same and accounting and answer_ok and pending_ok
            and out.status == status and (reason is None or out.reason == reason)
            and out.checked_steps <= capacity and out.verifier_calls in (0,1)
            and out.checked_steps <= max(0, out.internal_charged-1)
            and (out.derived is None or (s.staged is not None
                and out.derived.proof == s.staged.proof
                and out.derived.supporting_references == s.staged.supporting_references
                and out.derived.request_id == s.view.request_id
                and out.derived.scope_id == s.view.scope_id
                and out.derived.expression_sha256 == proof.expression_digest(s.view)
                and out.derived.evidence_sha256 == proof.evidence_digest(s.view)))
            and (charged > 0 or status == 'UNRESOLVED' or ns == s)
            and (status != 'STAGED' or ns.staged == p.candidate)
            and (status != 'UNRESOLVED' or ns.pending is None and ns.staged is None))
        rows.append(dict(group=group, case_id=name, before=asdict(s), proposal=asdict(p) if type(p) is api.ActionProposal else p,
            transition=asdict(t), expected=dict(status=status,reason=reason,charged=charged,reserved=reserved,value=value),
            checks=dict(immutable=immut,binding=binding,facts_same=facts_same,accounting=accounting,
                        answer=answer_ok,pending=pending_ok), passed=passed))
        counts[group] += 1
        return ns
    for name, av, pe, ar, ir in itertools.product(task.TOOLS, (False,True), (False,True), (0,1), (0,1)):
        s=fixture(internal=ir,acquisitions=ar,available=av,permitted=pe)
        reason = ('INTERNAL_BUDGET_EXHAUSTED' if not ir else 'PERMISSION_DENIED' if not pe
                  else 'PROVIDER_UNAVAILABLE' if not av else 'BUDGET_EXHAUSTED' if not ar else 'ACQUISITION_RESERVED')
        ok = reason == 'ACQUISITION_RESERVED'
        probe('external_grid',f'{name}:{av}:{pe}:{ar}:{ir}',s,api.propose(s,name,fact_index=1),
              'PENDING' if ok else 'DENIED',reason,int(bool(ir)),int(ok))
    for bit in (0,1):
        s=fixture(bit); c=candidate(s)
        t=probe('local',f'{bit}:stage',s,api.propose(s,'COMPUTE',candidate=c),'STAGED','UNVERIFIED_CANDIDATE',1)
        u=probe('local',f'{bit}:answer',t,api.propose(t,'ANSWER'),'VERIFIED_DERIVED','VALID_LOCAL_PROOF',3,value=bit)
        probe('local',f'{bit}:closed',u,api.propose(u,'ANSWER'),'REJECTED','SESSION_CLOSED')
        probe('local',f'{bit}:unprepared',s,api.propose(s,'ANSWER'),'REJECTED','NO_CANDIDATE',1)
        z=fixture(bit,internal=0)
        probe('local',f'{bit}:stop',z,api.propose(z,'STOP'),'UNRESOLVED','STOP_REQUESTED')
    for name,p in malformed():
        probe('malformed',name,fixture(),p,'REJECTED')
    s=fixture(); p=api.propose(s,'RETRIEVE',fact_index=1)
    for name,current in stale_states(s):
        reason='REQUEST_SCOPE_MISMATCH' if name in ('request','scope') else 'STALE_STATE'
        probe('stale',name,current,p,'REJECTED',reason)
    for index,name in enumerate(task.TOOLS):
        s=fixture(); p=api.propose(s,name,fact_index=1)
        t=probe('pending',name+':reserve',s,p,'PENDING','ACQUISITION_RESERVED',1,1)
        u=probe('pending',name+':replay',t,p,'REJECTED','STALE_STATE')
        w=probe('pending',name+':repeat',u,api.propose(u,name,fact_index=1),'DENIED','PENDING_ACQUISITION',1)
        v=probe('pending',name+':cross',w,api.propose(w,task.TOOLS[(index+1)%3],fact_index=1),'DENIED','PENDING_ACQUISITION',1)
        probe('pending',name+':stop',v,api.propose(v,'STOP'),'UNRESOLVED','STOP_REQUESTED')
    for bit in (0,1):
        s=fixture(bit)
        for name,bad in corruptions(candidate(s)):
            t=probe('proof_rejection',f'{bit}:{name}:stage',s,api.propose(s,'COMPUTE',candidate=bad),'STAGED','UNVERIFIED_CANDIDATE',1)
            # Expected verifier rule work fixed by where each declared corruption is checked.
            steps={'conclusion':2,'support':0,'expression':0,'unobserved':0,'rule':1,'order':1}[name]
            probe('proof_rejection',f'{bit}:{name}:answer',t,api.propose(t,'ANSWER'),'REJECTED',charged=1+steps)
    for bit,ir,cap in itertools.product((0,1),(0,1,2,3,4),(0,1,2,7)):
        s=fixture(bit,internal=ir); s=replace(s,staged=candidate(s)); ok=ir>=3 and cap>=2
        status='VERIFIED_DERIVED' if ok else 'DENIED' if ir==0 else 'REJECTED'
        reason='VALID_LOCAL_PROOF' if ok else 'INTERNAL_BUDGET_EXHAUSTED' if ir==0 else 'VERIFICATION_BUDGET_EXHAUSTED'
        probe('proof_budget',f'{bit}:{ir}:{cap}',s,api.propose(s,'ANSWER'),status,reason,
              3 if ok else int(ir>0),value=bit if ok else None,capacity=cap)
    for name,status in itertools.product(task.TOOLS,task.STATUSES):
        s=fixture(); refs=() if status=='UNOBSERVED' else ('B:first','B:second') if status=='CONFLICT' else ('B:first',)
        f=task.Fact('B',status,0 if status=='OBSERVED' else None,refs)
        s=replace(s,view=replace(s.view,facts=(s.view.facts[0],f)))
        ok=status!='OBSERVED'
        probe('fact_status',name+':'+status,s,api.propose(s,name,fact_index=1),
              'PENDING' if ok else 'DENIED','ACQUISITION_RESERVED' if ok else 'ALREADY_OBSERVED',1,int(ok))
    summary=dict(counts=dict(counts),calls=len(rows),failed_checks=sum(not r['passed'] for r in rows),
        status_counts=dict(Counter(r['transition']['result']['status'] for r in rows)),
        internal_charged=sum(r['transition']['result']['internal_charged'] for r in rows),
        acquisition_reserved=sum(r['transition']['result']['acquisition_reserved'] for r in rows),
        verifier_calls=sum(r['transition']['result']['verifier_calls'] for r in rows),
        checked_steps=sum(r['transition']['result']['checked_steps'] for r in rows))
    return summary, rows


def gate(s):
    return (s.get('counts')==EXPECTED and s.get('calls')==197 and s.get('failed_checks')==0
        and s.get('acquisition_reserved')==27 and s.get('internal_charged')==147
        and s.get('verifier_calls')==46 and s.get('checked_steps')==28)


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])


def validate_parent(path):
    require(sha(path)==PARENT_SHA,'C171 summary hash mismatch')
    p=json.loads(Path(path).read_text(encoding='utf-8'))
    require(p.get('experiment_id')=='C171-v5e-bounded-derived-result-contract' and p.get('commit_sha')==BASE
        and p.get('status')=='PASS' and p.get('diagnostic_execution_valid') is True
        and p.get('production_runtime_modified') is False and p.get('gate_e_candidate') is False,'Expected accepted C171')
    require(p.get('summary')==dict(checked_steps=1022,counts=dict(reference=504,malformed=48,unusable=14,
        rebound=16,resources=8,capacity=8,rule_scope=2),failed_checks=0,reference_false_accepts=0,
        reference_false_rejects=0,rejected=442,verified=158,verifier_calls=600),'C171 profile mismatch')
    return p


def protect(root,parent):
    pins=dict(parent['source_blobs']); hashes={}
    for name in PARENT_OWN:
        pins[name]=git(root,'rev-parse',BASE+':fold/'+name).decode().strip()
    for name,wanted in pins.items():
        require(git(root,'rev-parse','HEAD:fold/'+name).decode().strip()==wanted,'Historical source drift: '+name)
    for name in tuple(pins)+OWN:
        canonical=git(root,'show','HEAD:fold/'+name);raw=(root/name).read_bytes()
        require(raw==canonical or raw==canonical.replace(b'\n',b'\r\n'),'Uncommitted source: '+name)
        hashes[str((root/name).resolve())]=hashlib.sha256(raw).hexdigest()
    return pins,hashes


def preflight(root,parent_path,expected_head):
    require(git(root,'rev-parse','HEAD').decode().strip()==expected_head,'HEAD mismatch')
    require(git(root,'branch','--show-current').decode().strip()=='feat/sft-target-loss','Branch mismatch')
    require(not git(root,'status','--porcelain','--untracked-files=no').strip(),'Tracked tree dirty')
    p=validate_parent(parent_path); pins,protected=protect(root,p)
    protected[str(Path(parent_path).resolve())]=PARENT_SHA
    return p,pins,protected


def regression_modules(root):
    text=(Path(root)/'tools/run_c167.ps1').read_text(encoding='utf-8')
    names=re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$',text,re.M)
    require(len(names)==len(set(names))==51,'Historical regression module list changed')
    return names+['tests_lm.test_v05_c168_necessity_observability','tests_lm.test_v05_c169_interface_batch',
        'tests_lm.test_v05_c170_structured_task_input','tests_lm.test_v05_c171_derived_result',
        'tests_lm.test_v05_c172_action_runtime']


def run(*,c171_summary,output_dir,expected_head):
    root=Path(__file__).resolve().parents[2]; p,pins,protected=preflight(root,c171_summary,expected_head)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    try:
        require(hashlib.sha256(blob(manifest())).hexdigest()==MANIFEST_SHA,'Registered manifest drift')
        plan=out/'action-runtime-plan.json';plan.write_bytes(blob(dict(manifest(),source_blobs=pins)))
        protected[str(plan.resolve())]=sha(plan)
        print('[C172] plan fixed; 197 action attempts in 8 groups; no learned policy or provider IO',flush=True)
        summary,rows=collect()
        require(summary['counts']==EXPECTED and len(rows)==197,'Incomplete attempted coverage')
        records=out/'action-results.json';records.write_bytes(blob(rows))
        print(f"[C172] checked=197/197 failed={summary['failed_checks']} reserved={summary['acquisition_reserved']}",flush=True)
        preflight(root,c171_summary,expected_head)
        for path,wanted in protected.items():
            require(sha(path)==wanted,'Protected input changed: '+path)
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,commit_sha=expected_head,
            status='PASS' if gate(summary) else 'FAIL',diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,C171_summary_sha256=PARENT_SHA,
            source_blobs=pins,input_sha256=protected,summary=summary,
            records=dict(file=records.name,sha256=sha(records),rows=len(rows),serialized_bytes=records.stat().st_size),
            plan=dict(file=plan.name,sha256=sha(plan)),learned_forward_calls=0,real_provider_calls=0,
            actual_acquisitions=0,evidence_writes=0,training_steps=0,fresh_seed_count=0,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=['scripted typed proposals,not learned task control',
                'COMPUTE stages a supplied candidate,not a solver or neural computation',
                'PENDING is a reservation only,no transport/reply/admission/completion',
                'trusted single-owner immutable state;digest is not cryptographic authorization or CAS',
                'C171 local proof rules unchanged;guard correctness is not candidate accuracy',
                'model compute/source IO/authentication/concurrency/final Gate E are not measured'])
        (out/'summary.json').write_bytes(blob(report));print('=== C172 RESULT ===',flush=True)
        print(blob(report).decode(),flush=True);return report
    except Exception as exc:
        (out/'invalid.json').write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status='INVALID',
            diagnostic_execution_valid=False,error=str(exc))))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--c171-summary',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--expected-head',required=True)
    run(**vars(parser.parse_args()));return 0


if __name__=='__main__':
    raise SystemExit(main())
