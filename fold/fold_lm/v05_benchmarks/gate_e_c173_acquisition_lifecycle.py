"""C173: reservation -> bounded file response -> admitted view -> supplied proof.

A scripted, single-owner integration/reference test; no learned model or external
account messaging. OBSERVE/ASK_USER endpoints are explicitly local-file simulations.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict, replace
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import time

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_derived_result as proof
from fold_lm.v05 import structured_action_runtime as action
from fold_lm.v05 import structured_acquisition_lifecycle as api

EXPERIMENT_ID = 'C173-v5e-bounded-acquisition-lifecycle'
STAGE = 'V5-E-BOUNDED-ACQUISITION-LIFECYCLE'
BASE = 'e38ca796acd51dc54d6041ae69988f57592573e4'
PARENT_SHA = 'b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943'
MANIFEST_SHA = '4d80ee765b8c277228b1fd73e187a086d2922e3a4d3d3900863691a53bac862f'
GROUPS = dict(success=12, delivery_faults=60, pre_dispatch=27, source_guards=8,
              staged=6, reentrant=3, retry_budget=3, replay_delivery=3)
TOTAL_CASES = 122
EXPECTED_PROVIDER_CALLS, EXPECTED_FILE_READS = 98, 95
EXPECTED_PUBLICATIONS, EXPECTED_RESERVATIONS = 24, 122
FAULTS = ('missing', 'schema', 'intent', 'request', 'scope', 'action', 'fact',
          'provider', 'source', 'time', 'revision', 'reference', 'boolean', 'float',
          'range', 'payload_none', 'status', 'exception', 'value_flip', 'false_missing')
PRE = ('permission', 'availability', 'stale_expression', 'stale_fact', 'budget0',
       'budget1', 'wrong_intent', 'no_pending', 'stopped')
SOURCE_GUARDS = ('hash_mismatch', 'duplicate_fact', 'boolean_bit', 'float_bit',
                 'wrong_epoch', 'malformed_json', 'oversize', 'missing_record')
PARENT_OWN = ('fold_lm/v05/structured_action_runtime.py',
    'fold_lm/v05_benchmarks/gate_e_c172_action_runtime.py',
    'tests_lm/test_v05_c172_action_runtime.py', 'tools/run_c172.ps1',
    'docs/structured-action-runtime-v0.1.md', 'docs/experiment-ledger-addendum-c172-preregistration.md')
OWN = ('fold_lm/v05/structured_acquisition_lifecycle.py',
    'fold_lm/v05_benchmarks/gate_e_c173_acquisition_lifecycle.py',
    'tests_lm/test_v05_c173_acquisition_lifecycle.py', 'tools/run_c173.ps1',
    'docs/structured-acquisition-lifecycle-v0.1.md', 'docs/experiment-ledger-addendum-c173-preregistration.md')

class InvalidExecution(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise InvalidExecution(reason)

def blob(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def source_bytes(bit=0, variant=None):
    doc=dict(schema=api.SOURCE_SCHEMA,provider_id='C173:snapshot',evidence_time=1,revision=1,
             records=[dict(fact_id='B',value=bit),dict(fact_id='C',value=1-bit)])
    if variant=='duplicate_fact': doc['records'][1]['fact_id']='B'
    if variant=='boolean_bit': doc['records'][0]['value']=False
    if variant=='float_bit': doc['records'][0]['value']=0.0
    if variant=='wrong_epoch': doc['evidence_time']=2
    if variant=='missing_record': doc['records'][0]['fact_id']='D'
    if variant=='malformed_json': return b'{malformed\n'
    if variant=='oversize': return b' '*4097
    return blob(doc)

def source_specs():
    rows=[]
    for name,bit,variant in [('bit0',0,None),('bit1',1,None)]+[(s,0,s) for s in SOURCE_GUARDS]:
        raw=source_bytes(bit,variant)
        actual=hashlib.sha256(raw).hexdigest()
        expected=hashlib.sha256(raw+b'not-the-file').hexdigest() if variant=='hash_mismatch' else actual
        rows.append(dict(name=name,bytes=len(raw),file_sha256=actual,binding_sha256=expected))
    return rows

def manifest():
    return dict(experiment_id=EXPERIMENT_ID,schema=api.SCHEMA,source_schema=api.SOURCE_SCHEMA,
        groups=GROUPS,scenarios=TOTAL_CASES,tools=list(task.TOOLS),operators=['AND','OR'],bits=[0,1],
        delivery_faults=list(FAULTS),pre_dispatch=list(PRE),source_guards=list(SOURCE_GUARDS),
        sources=source_specs(),max_source_bytes=4096,max_source_records=4,owner_max_dispatches=4,
        initial_internal=12,initial_acquisitions=1,replay_acquisitions=2,
        provider_calls=EXPECTED_PROVIDER_CALLS,file_read_attempts=EXPECTED_FILE_READS,
        fact_publications=EXPECTED_PUBLICATIONS,acquisition_reservations=EXPECTED_RESERVATIONS,
        supplied_proof_answers=12,c171_verifier_calls=18,c171_checked_steps=36,
        internal_charged=417,action_calls=236,dispatch_calls=143,
        learned_forwards=0,training_steps=0,fresh_seeds=0,network_calls=0,
        scope='fixed-epoch local file lifecycle; OBSERVE/ASK_USER are simulations; no learned policy')

def write_sources(directory):
    directory.mkdir(parents=True,exist_ok=False); out={}
    for spec in source_specs():
        name=spec['name']; bit=1 if name=='bit1' else 0
        raw=source_bytes(bit,name if name in SOURCE_GUARDS else None)
        path=directory/(name+'.json');path.write_bytes(raw)
        require(sha(path)==spec['file_sha256'],'Fixture construction drift')
        out[name]=(path,api.SourceBinding('C173:snapshot',spec['binding_sha256']))
    return out

def initial_view(operator='AND', *, controlling=False, bit=0, acquisitions=1, third=False):
    a=bit if controlling else int(operator=='AND')
    facts=(task.Fact('A','OBSERVED',a,('fixture:A',)),task.Fact('B'))
    if third: facts += (task.Fact('C'),)
    nodes=(task.Node('FACT',0),task.Node('FACT',1),task.Node(operator,left=0,right=1))
    return task.TaskView('C173|request','C173',nodes,facts,
                        task.Resources(12,acquisitions,(True,True,True),(True,True,True)))

def both_candidate(view):
    """Explicit symbolic fixture, constructed ONLY from currently visible facts."""
    if any(f.status!='OBSERVED' for f in view.facts[:2]):
        return proof.bind_candidate(view,0,(),())
    a,b=(f.value for f in view.facts[:2]); op=view.nodes[-1].kind
    value=(a & b) if op=='AND' else (a | b)
    steps=(proof.ProofStep(0,a,'OBSERVED_LEAF'),proof.ProofStep(1,b,'OBSERVED_LEAF'),
           proof.ProofStep(2,value,op+'_BOTH',(0,1)))
    return proof.bind_candidate(view,value,steps,tuple(proof.Support(i,view.facts[i].reference_ids[0]) for i in (0,1)))

def short_candidate(view):
    a=view.facts[0].value; rule='AND_LEFT_ZERO' if a==0 else 'OR_LEFT_ONE'
    return proof.bind_candidate(view,a,(proof.ProofStep(0,a,'OBSERVED_LEAF'),
        proof.ProofStep(2,a,rule,(0,))),(proof.Support(0,view.facts[0].reference_ids[0]),))

def corrupt(name, delivery):
    if name=='missing': return None
    if name=='exception': raise api.ProviderFailure('DECLARED_AFTER_READ_FAILURE')
    values={'schema':dict(schema='other'),'intent':dict(intent_id='old-intent'),
        'request':dict(request_id='C173|other'),'scope':dict(scope_id='other'),
        'action':dict(action='ASK_USER' if delivery.action!='ASK_USER' else 'RETRIEVE'),
        'fact':dict(fact_id='C'),'provider':dict(source=replace(delivery.source,provider_id='other')),
        'source':dict(source=replace(delivery.source,source_sha256='0'*64)),
        'time':dict(source=replace(delivery.source,evidence_time=2)),
        'revision':dict(source=replace(delivery.source,revision=2)),
        'reference':dict(reference_id='invented'),'boolean':dict(value=False),
        'float':dict(value=0.0),'range':dict(value=2),'payload_none':dict(value=None),
        'status':dict(status='OTHER'),'value_flip':dict(value=1-delivery.value),
        'false_missing':dict(status='MISSING',value=None,reference_id=None)}
    return replace(delivery,**values[name])

class Scenario:
    def __init__(self, source, tool, view=None, fault=None):
        self.provider=api.FileSnapshotProvider(*source);self.calls=0;self.events=[];self.checks=[]
        self.last_delivery=None;self.extra=None
        def fetch(request):
            self.calls+=1
            if self.extra: return self.extra(request)
            d=self.provider(request);self.last_delivery=d
            return corrupt(fault,d) if fault else d
        self.owner=api.AcquisitionOwner(action.RuntimeState(view or initial_view()),
                                        {tool:api.Endpoint(source[1],fetch)})
        self.tool=tool
    def check(self,name,condition):
        self.checks.append(dict(name=name,passed=bool(condition)))
    def apply(self,name,**kwargs):
        before=self.owner.state; p=action.propose(before,name,**kwargs)
        transition=self.owner.apply(p)
        self.events.append(dict(kind='action',before=asdict(before),proposal=asdict(p),
                               after=asdict(transition.state),result=asdict(transition.result)))
        return transition.result
    def reserve(self,index=1):
        result=self.apply(self.tool,fact_index=index)
        self.check('reserved',result.status=='PENDING' and result.acquisition_reserved==1)
        return result.intent.intent_id if result.intent else 'absent-intent'
    def dispatch(self,identity):
        before=self.owner.state; r=self.owner.dispatch(identity);after=self.owner.state
        self.events.append(dict(kind='dispatch',before=asdict(before),after=asdict(after),result=asdict(r)))
        self.check('dispatch_budget',before.view.resources.internal_remaining-after.view.resources.internal_remaining==r.internal_charged
            and before.view.resources.acquisitions_remaining==after.view.resources.acquisitions_remaining)
        self.check('no_failed_payload',r.evidence is None if not r.fact_publications else r.evidence is not None)
        if not r.fact_publications: self.check('no_failed_fact_change',before.view.facts==after.view.facts)
        self.check('no_witness_in_receipt',r.evidence is None or 'source_document' not in asdict(r.evidence))
        return r
    def result(self,group,name,expected_calls,expected_reads,expected_publications):
        publications=sum(e['result'].get('fact_publications',0) for e in self.events)
        self.check('provider_calls',self.calls==expected_calls)
        self.check('file_reads',self.provider.reads==expected_reads)
        self.check('publications',publications==expected_publications==len(self.owner.receipts))
        self.check('bounded_reads',self.provider.bytes_read<=self.provider.reads*(api.MAX_SOURCE_BYTES+1))
        self.check('unchanged_epoch',self.owner.state.view.evidence_time==1 and self.owner.state.view.revision==1)
        self.check('canonical_view',task.decode(task.encode(self.owner.state.view))==self.owner.state.view)
        return dict(group=group,case_id=name,passed=all(x['passed'] for x in self.checks),checks=self.checks,
            provider_calls=self.calls,file_read_attempts=self.provider.reads,file_bytes_read=self.provider.bytes_read,
            validated_source_records=self.provider.validated_records,fact_publications=publications,
            receipts=[asdict(x) for x in self.owner.receipts],events=self.events)

def collect(sources, rows=None):
    rows=[] if rows is None else rows
    for tool,op,bit in itertools.product(task.TOOLS,('AND','OR'),(0,1)):
        s=Scenario(sources['bit'+str(bit)],tool,initial_view(op));identity=s.reserve()
        r=s.dispatch(identity);s.check('admitted',r.status=='PUBLISHED')
        s.check('policy_view',s.owner.state.view.facts[1].value==bit)
        s.check('replay_no_io',s.dispatch(identity).reason=='NO_PENDING_INTENT')
        s.apply('COMPUTE',candidate=both_candidate(s.owner.state.view));answer=s.apply('ANSWER')
        s.check('derived',answer.status=='VERIFIED_DERIVED' and answer.derived.value==bit)
        s.check('only_target',s.owner.state.view.facts[0]==initial_view(op).facts[0])
        rows.append(s.result('success',f'{tool}:{op}:{bit}',1,1,1))
    print('[C173] 1/8 success collected',flush=True)
    for tool,name in itertools.product(task.TOOLS,FAULTS):
        s=Scenario(sources['bit0'],tool,fault=name);identity=s.reserve();r=s.dispatch(identity)
        expected=('UNRESOLVED','MISSING_DELIVERY') if name=='missing' else ('UNRESOLVED','PROVIDER_FAILURE') if name=='exception' else ('REJECTED','DELIVERY_BINDING_MISMATCH') if name in FAULTS[1:11] else ('REJECTED','INVALID_EVIDENCE')
        s.check('fault_rejected',(r.status,r.reason)==expected and s.owner.state.pending is None)
        s.apply('STOP');s.check('stop_no_value',s.owner.state.terminal=='UNRESOLVED')
        rows.append(s.result('delivery_faults',f'{tool}:{name}',1,1,0))
    print('[C173] 2/8 delivery_faults collected',flush=True)
    for tool,name in itertools.product(task.TOOLS,PRE):
        s=Scenario(sources['bit0'],tool);identity=s.reserve() if name!='no_pending' else 'absent-intent'
        view=s.owner.state.view;r=view.resources;i=task.TOOLS.index(tool)
        if name in ('permission','availability'):
            field='permitted' if name=='permission' else 'available';mask=list(getattr(r,field));mask[i]=False
            s.owner.refresh(replace(view,resources=replace(r,**{field:tuple(mask)})))
        if name=='stale_expression': s.owner.refresh(replace(view,nodes=(*view.nodes[:-1],replace(view.nodes[-1],kind='OR'))))
        if name=='stale_fact': s.owner.refresh(replace(view,facts=(replace(view.facts[0],value=0),view.facts[1])))
        if name in ('budget0','budget1'): s.owner.refresh(replace(view,resources=replace(r,internal_remaining=int(name[-1]))))
        if name=='stopped': s.apply('STOP')
        r=s.dispatch('wrong' if name=='wrong_intent' else identity)
        reasons=dict(permission='PERMISSION_DENIED',availability='PROVIDER_UNAVAILABLE',stale_expression='STALE_RESERVATION',
            stale_fact='STALE_RESERVATION',budget0='INTERNAL_BUDGET_EXHAUSTED',budget1='INTERNAL_BUDGET_EXHAUSTED',
            wrong_intent='INTENT_MISMATCH',no_pending='NO_PENDING_INTENT',stopped='NO_PENDING_INTENT')
        s.check('blocked_before_io',r.reason==reasons[name] and r.provider_calls==0)
        rows.append(s.result('pre_dispatch',f'{tool}:{name}',0,0,0))
    print('[C173] 3/8 pre_dispatch collected',flush=True)
    for name in SOURCE_GUARDS:
        s=Scenario(sources[name],'RETRIEVE');r=s.dispatch(s.reserve())
        s.check('source_rejected',r.status=='UNRESOLVED' and r.reason==('RECORD_UNBOUND' if name=='missing_record' else 'PROVIDER_FAILURE'))
        rows.append(s.result('source_guards',name,1,1,0))
    print('[C173] 4/8 source_guards collected',flush=True)
    for tool,bit in itertools.product(task.TOOLS,(0,1)):
        s=Scenario(sources['bit'+str(bit)],tool,initial_view('AND' if bit==0 else 'OR',controlling=True,bit=bit))
        old=short_candidate(s.owner.state.view);s.apply('COMPUTE',candidate=old)
        s.dispatch(s.reserve());s.check('staged_invalidated',s.owner.state.staged is None)
        s.check('no_automatic_answer',s.apply('ANSWER').reason=='NO_CANDIDATE')
        s.apply('COMPUTE',candidate=old);s.check('old_proof_rejected',s.apply('ANSWER').reason=='EVIDENCE_MISMATCH')
        rows.append(s.result('staged',f'{tool}:{bit}',1,1,1))
    print('[C173] 5/8 staged collected',flush=True)
    for tool in task.TOOLS:
        s=Scenario(sources['bit0'],tool);identity=s.reserve()
        def reentrant(request,s=s,identity=identity):
            nested=s.dispatch(identity);s.check('reentrant_denied',nested.reason=='TRANSPORT_BUSY' and nested.provider_calls==0)
            return s.provider(request)
        s.extra=reentrant;s.dispatch(identity);rows.append(s.result('reentrant',tool,1,1,1))
    print('[C173] 6/8 reentrant collected',flush=True)
    for tool in task.TOOLS:
        s=Scenario(sources['bit0'],tool,fault='missing');identity=s.reserve();s.dispatch(identity)
        s.check('no_budget_refund',s.apply(tool,fact_index=1).reason=='BUDGET_EXHAUSTED')
        s.check('no_replay',s.dispatch(identity).reason=='NO_PENDING_INTENT')
        rows.append(s.result('retry_budget',tool,1,1,0))
    print('[C173] 7/8 retry_budget collected',flush=True)
    for tool in task.TOOLS:
        s=Scenario(sources['bit0'],tool,initial_view(acquisitions=2,third=True));s.dispatch(s.reserve())
        old=s.last_delivery;s.extra=lambda request,old=old:old
        r=s.dispatch(s.reserve(2));s.check('replayed_delivery_rejected',r.reason=='DELIVERY_BINDING_MISMATCH')
        s.check('wrong_target_stays_unknown',s.owner.state.view.facts[2].value is None)
        rows.append(s.result('replay_delivery',tool,2,1,1))
    print('[C173] 8/8 replay_delivery collected',flush=True)
    return rows

def summarize(rows):
    events=[e for row in rows for e in row['events']]
    return dict(scenarios=len(rows),counts=dict(Counter(r['group'] for r in rows)),
        failed_checks=sum(not r['passed'] for r in rows),
        provider_calls=sum(r['provider_calls'] for r in rows),
        file_read_attempts=sum(r['file_read_attempts'] for r in rows),
        file_bytes_read=sum(r['file_bytes_read'] for r in rows),
        validated_source_records=sum(r['validated_source_records'] for r in rows),
        fact_publications=sum(r['fact_publications'] for r in rows),
        acquisition_reserved=sum(e['result'].get('acquisition_reserved',0) for e in events),
        internal_charged=sum(e['result']['internal_charged'] for e in events),
        action_calls=sum(e['kind']=='action' for e in events),dispatch_calls=sum(e['kind']=='dispatch' for e in events),
        verified_derived=sum(e['result']['status']=='VERIFIED_DERIVED' for e in events),
        verifier_calls=sum(e['result'].get('verifier_calls',0) for e in events),
        checked_steps=sum(e['result'].get('checked_steps',0) for e in events))

def gate(s):
    expected=dict(scenarios=122,counts=GROUPS,failed_checks=0,provider_calls=98,file_read_attempts=95,
        fact_publications=24,acquisition_reserved=122,verified_derived=12,verifier_calls=18,checked_steps=36,
        internal_charged=417,action_calls=236,dispatch_calls=143)
    return all(s.get(k)==v for k,v in expected.items())

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])

def validate_parent(path):
    require(sha(path)==PARENT_SHA,'C172 hash mismatch')
    p=json.loads(Path(path).read_text(encoding='utf-8'))
    require(p.get('experiment_id')=='C172-v5e-typed-action-runtime-boundary' and p.get('commit_sha')==BASE
        and p.get('status')=='PASS' and p.get('diagnostic_execution_valid') is True
        and p.get('production_runtime_modified') is False and p.get('gate_e_candidate') is False,'Wrong C172 identity')
    require(p['summary']['calls']==197 and p['summary']['failed_checks']==0
        and p['summary']['acquisition_reserved']==27 and len(p['source_blobs'])==30,'C172 profile mismatch')
    return p

def protect_sources(root,parent):
    pins=dict(parent['source_blobs']); hashes={}
    for name in PARENT_OWN: pins[name]=git(root,'rev-parse',BASE+':fold/'+name).decode().strip()
    for name,wanted in pins.items():
        require(git(root,'rev-parse','HEAD:fold/'+name).decode().strip()==wanted,'Historical drift: '+name)
    for name in tuple(pins)+OWN:
        canonical=git(root,'show','HEAD:fold/'+name);raw=(root/name).read_bytes()
        require(raw==canonical or raw==canonical.replace(b'\n',b'\r\n'),'Local source drift: '+name)
        hashes[str((root/name).resolve())]=hashlib.sha256(raw).hexdigest()
    return pins,hashes

def regression_modules(root):
    text=(Path(root)/'tools/run_c167.ps1').read_text(encoding='utf-8')
    names=re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$',text,re.M)
    require(len(names)==len(set(names))==51,'Historical regression list drift')
    return names+['tests_lm.test_v05_c168_necessity_observability','tests_lm.test_v05_c169_interface_batch',
        'tests_lm.test_v05_c170_structured_task_input','tests_lm.test_v05_c171_derived_result',
        'tests_lm.test_v05_c172_action_runtime','tests_lm.test_v05_c173_acquisition_lifecycle']

def run(*,c172_summary,output_dir,expected_head):
    root=Path(__file__).resolve().parents[2]
    def guard():
        require(git(root,'rev-parse','HEAD').decode().strip()==expected_head,'HEAD mismatch')
        require(git(root,'branch','--show-current').decode().strip()=='feat/sft-target-loss','Branch mismatch')
        require(not git(root,'status','--porcelain','--untracked-files=no').strip(),'Tracked tree changed')
    guard();parent=validate_parent(c172_summary);pins,protected=protect_sources(root,parent)
    protected[str(Path(c172_summary).resolve())]=PARENT_SHA
    require(hashlib.sha256(blob(manifest())).hexdigest()==MANIFEST_SHA,'Manifest drift')
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    plan=out/'acquisition-plan.json';plan.write_bytes(blob(dict(manifest(),source_blobs=pins)))
    protected[str(plan.resolve())]=sha(plan);rows=[]
    try:
        sources=write_sources(out/'sources')
        for path,_ in sources.values(): protected[str(path.resolve())]=sha(path)
        print('[C173] plan fixed; 122 lifecycle scenarios; actual bounded file reads; no learned policy',flush=True)
        collect(sources,rows);s=summarize(rows)
        require(s['scenarios']==TOTAL_CASES and s['counts']==GROUPS,'Incomplete scenario coverage')
        details=out/'acquisition-results.json';details.write_bytes(blob(rows))
        guard();protect_sources(root,parent)
        for path,wanted in protected.items(): require(sha(path)==wanted,'Protected input changed: '+path)
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,commit_sha=expected_head,
            status='PASS' if gate(s) else 'FAIL',diagnostic_execution_valid=True,production_runtime_modified=False,
            gate_e_candidate=False,C172_summary_sha256=PARENT_SHA,source_blobs=pins,input_sha256=protected,
            summary=s,plan=dict(file=plan.name,sha256=sha(plan)),
            records=dict(file=details.name,rows=len(rows),sha256=sha(details),serialized_bytes=details.stat().st_size),
            learned_forward_calls=0,training_steps=0,fresh_seed_count=0,network_calls=0,core_evidence_writes=0,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=['scripted actions and supplied proofs,not learned necessity or answer generation',
                'OBSERVE/ASK_USER are registered local-file simulations,not Vision or user messages',
                'fixed snapshot epoch,private runtime witnesses;only admitted target reaches the C170 policy view',
                'single-owner synchronous object,not durable/concurrent receipts or asynchronous cancellation',
                'TaskView publication only,not production EvidenceState/durable memory integration',
                'source trust configuration is caller-owned;hash matching does not prove real-world truth'])
        (out/'summary.json').write_bytes(blob(report))
        print(f"[C173] checked={len(rows)}/122 failed={s['failed_checks']} provider_calls={s['provider_calls']} published={s['fact_publications']}",flush=True)
        print('=== C173 RESULT ===',flush=True);print(blob(report).decode(),flush=True)
        return report
    except Exception as exc:
        (out/'invalid.json').write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status='INVALID',
            diagnostic_execution_valid=False,error=str(exc),completed_scenarios=rows)))
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--c172-summary',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-head',required=True);run(**vars(p.parse_args()));return 0

if __name__=='__main__':
    raise SystemExit(main())
