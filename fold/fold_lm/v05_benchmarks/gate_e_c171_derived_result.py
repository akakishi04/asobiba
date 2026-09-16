"""C171: bounded proof/result contract, with explicit symbolic test fixtures.

This is NOT learned reasoning. The fixture proof builder is benchmark-only;
the production checker receives proposed claims and never returns repaired ones.
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
from fold_lm.v05 import structured_derived_result as api

EXPERIMENT_ID = 'C171-v5e-bounded-derived-result-contract'
STAGE = 'V5-E-BOUNDED-DERIVED-RESULT-CONTRACT'
BASE = 'da09a86e25f12927a9206217b7933609c2fe1b8c'
PARENT_SHA = 'a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e'
# Filled from the label-free manifest before registration, not from deciding results.
MANIFEST_SHA = 'af6df4dff24b42b95bfb081485127604a5ce8c6c15753522838fe3abe6799285'
EXPECTED = dict(reference=504, malformed=48, unusable=14, rebound=16,
                resources=8, capacity=8, rule_scope=2)
PARENT_OWN = ('fold_lm/v05/structured_task_input.py',
    'fold_lm/v05_benchmarks/gate_e_c170_structured_task_input.py',
    'tests_lm/test_v05_c170_structured_task_input.py','tools/run_c170.ps1',
    'docs/experiment-ledger-addendum-c170-preregistration.md','docs/structured-task-interface-v0.1.md')
OWN = ('fold_lm/v05/structured_derived_result.py',
    'fold_lm/v05_benchmarks/gate_e_c171_derived_result.py',
    'tests_lm/test_v05_c171_derived_result.py','tools/run_c171.ps1',
    'docs/structured-derived-result-v0.1.md','docs/experiment-ledger-addendum-c171-preregistration.md')

class InvalidExecution(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise InvalidExecution(message)

def blob(x):
    return (json.dumps(x, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def templates():
    # Same ten development structures as C170, explicitly copied as fixture syntax.
    N = task.Node
    return (
        ('A',1,(N('FACT',0),)),
        ('NOT_A',1,(N('FACT',0,negate=True),)),
        ('A_AND_A',1,(N('FACT',0),N('FACT',0),N('AND',left=0,right=1))),
        ('A_AND_B',2,(N('FACT',0),N('FACT',1),N('AND',left=0,right=1))),
        ('A_OR_B',2,(N('FACT',0),N('FACT',1),N('OR',left=0,right=1))),
        ('NOT_A_OR_B',2,(N('FACT',0,negate=True),N('FACT',1),N('OR',left=0,right=1))),
        ('AB_AND_C_OR',3,(N('FACT',0),N('FACT',1),N('AND',left=0,right=1),N('FACT',2),N('OR',left=2,right=3))),
        ('A_BC_OR_AND',3,(N('FACT',0),N('FACT',1),N('FACT',2),N('OR',left=1,right=2),N('AND',left=0,right=3))),
        ('AB_AND_CD_AND_OR',4,(N('FACT',0),N('FACT',1),N('AND',left=0,right=1),N('FACT',2),N('FACT',3),N('AND',left=3,right=4),N('OR',left=2,right=5))),
        ('A_B_C_D_OR_AND_OR',4,(N('FACT',0),N('FACT',1),N('FACT',2),N('FACT',3),N('OR',left=2,right=3),N('AND',left=1,right=4),N('OR',left=0,right=5))),
    )

def make_view(nodes, values):
    facts = tuple(task.Fact(chr(65+i)) if value is None else
        task.Fact(chr(65+i),'OBSERVED',value,('evidence:'+chr(65+i),))
        for i,value in enumerate(values))
    return task.TaskView('C171|request','C171',nodes,facts)

def reference_views():
    for name,n,nodes in templates():
        for i,values in enumerate(itertools.product((None,0,1), repeat=n)):
            yield name+':'+str(i),make_view(nodes,values)

def proof_fixture(view):
    """Hand-written test proof producer. Never imported by the production checker."""
    def build(index):
        n=view.nodes[index]
        if n.kind=='FACT':
            f=view.facts[n.fact]
            if f.status!='OBSERVED':
                return None
            v=f.value ^ int(n.negate)
            return (api.ProofStep(index,v,'OBSERVED_LEAF'),)
        left,right=build(n.left),build(n.right)
        control=0 if n.kind=='AND' else 1
        for name,premise,child in (('LEFT',left,n.left),('RIGHT',right,n.right)):
            if premise is not None and premise[-1].value==control:
                rule=n.kind+'_'+name+('_ZERO' if control==0 else '_ONE')
                return premise+(api.ProofStep(index,control,rule,(child,)),)
        if left is None or right is None:
            return None
        v=(left[-1].value & right[-1].value) if n.kind=='AND' else (left[-1].value | right[-1].value)
        return left+right+(api.ProofStep(index,v,n.kind+'_BOTH',(n.left,n.right)),)
    proof=build(len(view.nodes)-1)
    if proof is None:
        return (),()
    proof=tuple(sorted(proof,key=lambda s:s.node_index))
    indices=sorted({view.nodes[s.node_index].fact for s in proof if s.rule=='OBSERVED_LEAF'})
    return proof,tuple(api.Support(i,view.facts[i].reference_ids[0]) for i in indices)

def candidate_fixture(view, value):
    proof,support=proof_fixture(view)
    return api.bind_candidate(view,value,proof,support)

def completion_values(view):
    """Independent exhaustive evaluator; never passed into verify or input encoder."""
    unknown=[i for i,f in enumerate(view.facts) if f.status!='OBSERVED']
    outputs=[]
    for bits in itertools.product((0,1), repeat=len(unknown)):
        values={i:f.value for i,f in enumerate(view.facts) if f.status=='OBSERVED'}
        values.update(zip(unknown,bits,strict=True)); stack=[]
        for n in view.nodes:
            stack.append((values[n.fact]^int(n.negate)) if n.kind=='FACT' else
                (stack[n.left]&stack[n.right]) if n.kind=='AND' else
                (stack[n.left]|stack[n.right]))
        outputs.append(stack[-1])
    return tuple(sorted(set(outputs)))

def short_view(bit):
    return make_view((task.Node('FACT',0),task.Node('FACT',1),
        task.Node('OR' if bit else 'AND',left=0,right=1)),(bit,None))

def corruptions(c):
    first,last=c.proof
    return (
        ('schema',replace(c,schema='observed-value')),
        ('request',replace(c,request_id='C171|other')),
        ('scope',replace(c,scope_id='other')),
        ('expression',replace(c,expression_sha256='0'*64)),
        ('evidence',replace(c,evidence_sha256='0'*64)),
        ('time',replace(c,evidence_time=c.evidence_time+1)),
        ('revision',replace(c,revision=c.revision+1)),
        ('conclusion',replace(c,value=1-c.value)),
        ('boolean',replace(c,value=bool(c.value))),
        ('float',replace(c,value=float(c.value))),
        ('empty-proof',replace(c,proof=())),
        ('list-proof',replace(c,proof=list(c.proof))),
        ('oversize-proof',replace(c,proof=c.proof*4)),
        ('reverse-proof',replace(c,proof=c.proof[::-1])),
        ('node',replace(c,proof=(replace(first,node_index=7),last))),
        ('step-bit-type',replace(c,proof=(replace(first,value=True),last))),
        ('rule',replace(c,proof=(replace(first,rule='MAGIC'),last))),
        ('self-premise',replace(c,proof=(first,replace(last,premises=(last.node_index,))))),
        ('other-child',replace(c,proof=(first,replace(last,premises=(1,))))),
        ('leaf-value',replace(c,proof=(replace(first,value=1-first.value),last))),
        ('no-support',replace(c,supporting_references=())),
        ('wrong-support',replace(c,supporting_references=(api.Support(0,'invented'),))),
        ('duplicate-support',replace(c,supporting_references=c.supporting_references*2)),
        ('list-support',replace(c,supporting_references=list(c.supporting_references))),
    )

def rebound_views(view):
    a,b=view.facts
    nodes=(*view.nodes[:-1],replace(view.nodes[-1],kind='AND' if view.nodes[-1].kind=='OR' else 'OR'))
    return (
        ('request',replace(view,request_id='C171|other')),
        ('scope',replace(view,request_id='other|request',scope_id='other')),
        ('time',replace(view,evidence_time=2)),('revision',replace(view,revision=2)),
        ('expression',replace(view,nodes=nodes)),
        ('fact-id',replace(view,facts=(replace(a,fact_id='renamed-A'),b))),
        ('support',replace(view,facts=(replace(a,reference_ids=('new-evidence:A',)),b))),
        ('value',replace(view,facts=(replace(a,value=1-a.value),b))),
    )

def resource_views(view):
    for ir,ar in ((0,0),(0,1),(3,0),(3,1)):
        yield replace(view,resources=task.Resources(ir,ar,(False,False,False),(False,False,False)))

def manifest():
    return dict(experiment_id=EXPERIMENT_ID,schema=api.SCHEMA,input_schema=task.SCHEMA,
        templates=[dict(name=n,facts=k,nodes=[asdict(x) for x in ns]) for n,k,ns in templates()],
        assignments=[None,0,1],proposed_bits=[0,1],rules=list(api.RULES),maximum_proof_steps=7,
        malformed_names=[n for n,_ in corruptions(candidate_fixture(short_view(1),1))],
        unusable_statuses=[s for s in task.STATUSES if s!='OBSERVED'],
        rebound_names=[n for n,_ in rebound_views(short_view(1))],capacities=[0,1,2,7],
        resource_pairs=[[0,0],[0,1],[3,0],[3,1]],rule_scope=['A_OR_NOT_A_unknown','A_AND_NOT_A_unknown'],
        counts=EXPECTED,total_verifier_calls=600,parent_sha256=PARENT_SHA,
        scope='hand-written verifier with symbolic development fixtures,not a learned policy or final Gate E')

def collect():
    rows=[];counts=Counter()
    def probe(group,name,view,candidate,expect,capacity=7,required_reason=None):
        before=blob(asdict(view)); cbefore=blob(asdict(candidate))
        out=api.verify(view,candidate,max_steps=capacity)
        accepted=out.status=='VERIFIED_DERIVED'
        serialized=json.loads(blob(asdict(out)))
        bound=(out.schema==api.SCHEMA and out.derivation_kind=='BOOLEAN_LOCAL_PROOF'
            and out.request_id==view.request_id and out.scope_id==view.scope_id
            and out.expression_sha256==api.expression_digest(view) and out.evidence_sha256==api.evidence_digest(view)
            and out.evidence_time==view.evidence_time and out.revision==view.revision
            and out.status in ('VERIFIED_DERIVED','REJECTED')
            and type(out.reason) is str and bool(out.reason)
            and (not accepted or out.reason=='VALID_LOCAL_PROOF'))
        passed=(bound and accepted is expect and blob(asdict(view))==before and blob(asdict(candidate))==cbefore
            and _canonical_serial(out,serialized) and 0<=out.checked_steps<=capacity
            and (out.value==candidate.value and out.supporting_references==candidate.supporting_references
                 and out.proof==candidate.proof if accepted else
                 out.value is None and out.supporting_references==() and out.proof==())
            and (required_reason is None or out.reason==required_reason))
        rows.append(dict(group=group,case_id=name,current_view=asdict(view),candidate=asdict(candidate),
            result=asdict(out),expected_accept=expect,max_steps=capacity,passed=passed,
            semantic_completions=list(completion_values(view))))
        counts[group]+=1
    for name,view in reference_views():
        for claim in (0,1):
            c=candidate_fixture(view,claim)
            expect=completion_values(view)==(claim,)
            probe('reference',name+':'+str(claim),view,c,expect)
    for bit in (0,1):
        view=short_view(bit); c=candidate_fixture(view,bit)
        for name,bad in corruptions(c):
            probe('malformed',str(bit)+':'+name,view,bad,False)
        for name,new_view in rebound_views(view):
            probe('rebound',str(bit)+':'+name,new_view,c,False)
        for i,v in enumerate(resource_views(view)):
            probe('resources',str(bit)+':'+str(i),v,c,True)
        for cap in (0,1,2,7):
            probe('capacity',str(bit)+':'+str(cap),view,c,cap>=2,cap,
                  'VALID_LOCAL_PROOF' if cap>=2 else 'VERIFICATION_BUDGET_EXHAUSTED')
        for status in task.STATUSES:
            if status=='OBSERVED':
                continue
            refs=() if status=='UNOBSERVED' else ('old:A','other:A') if status=='CONFLICT' else ('old:A',)
            v=make_view((task.Node('FACT',0),),(None,))
            v=replace(v,facts=(task.Fact('A',status,None,refs),))
            bad=api.bind_candidate(v,bit,(api.ProofStep(0,bit,'OBSERVED_LEAF'),),(api.Support(0,'old:A'),))
            probe('unusable',str(bit)+':'+status,v,bad,False,required_reason='SUPPORT_NOT_USABLE')
    for op,claim in (('OR',1),('AND',0)):
        view=make_view((task.Node('FACT',0),task.Node('FACT',0,negate=True),
                       task.Node(op,left=0,right=1)),(None,))
        # No excluded-middle/case-split rule. Rejection is NOT logical impossibility.
        probe('rule_scope',op,view,candidate_fixture(view,claim),False,required_reason='MALFORMED_PROOF')
    summary=dict(counts=dict(counts),verifier_calls=len(rows),failed_checks=sum(not r['passed'] for r in rows),
        verified=sum(r['result']['status']=='VERIFIED_DERIVED' for r in rows),
        rejected=sum(r['result']['status']=='REJECTED' for r in rows),
        checked_steps=sum(r['result']['checked_steps'] for r in rows),
        reference_false_accepts=sum(r['group']=='reference' and not r['expected_accept'] and r['result']['status']=='VERIFIED_DERIVED' for r in rows),
        reference_false_rejects=sum(r['group']=='reference' and r['expected_accept'] and r['result']['status']!='VERIFIED_DERIVED' for r in rows))
    return summary,rows

def _canonical_serial(out,decoded):
    return blob(decoded)==blob(asdict(out)) and (decoded['value'] is None or type(decoded['value']) is int)

def gate(s):
    return (s.get('counts')==EXPECTED and s.get('verifier_calls')==600
        and s.get('failed_checks')==s.get('reference_false_accepts')==s.get('reference_false_rejects')==0
        and s.get('verified',0)+s.get('rejected',0)==600)

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])

def validate_parent(path):
    require(sha(path)==PARENT_SHA,'C170 report hash mismatch')
    p=json.loads(Path(path).read_text(encoding='utf-8'))
    require(p.get('experiment_id')=='C170-v5e-structured-task-input-contract'
        and p.get('stage')=='V5-E-STRUCTURED-TASK-INPUT-CONTRACT' and p.get('commit_sha')==BASE
        and p.get('status')=='PASS' and p.get('diagnostic_execution_valid') is True
        and p.get('production_runtime_modified') is False and p.get('gate_e_candidate') is False,'Wrong accepted parent')
    require(p['summary'].get('capture_attempts')==p['summary'].get('consumer_calls')==532
        and p['summary'].get('failed_roundtrips')==0 and p['summary'].get('malformed_rejected')==40
        and len(p.get('necessity',[]))==8 and len(p.get('malformed',[]))==40,'Full accepted C170 required')
    return p

def protect_sources(root,parent):
    pins=dict(parent['source_blobs']); hashes={}
    for name in PARENT_OWN:
        pins[name]=git(root,'rev-parse',BASE+':fold/'+name).decode().strip()
    for name,wanted in pins.items():
        require(git(root,'rev-parse','HEAD:fold/'+name).decode().strip()==wanted,'Historical source changed: '+name)
    for name in (*pins,*OWN):
        canonical=git(root,'show','HEAD:fold/'+name); raw=(root/name).read_bytes()
        require(raw==canonical or raw==canonical.replace(b'\n',b'\r\n'),'Uncommitted source: '+name)
        hashes[str((root/name).resolve())]=hashlib.sha256(raw).hexdigest()
    return pins,hashes

def regression_modules(root):
    names=re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$',
        (Path(root)/'tools/run_c167.ps1').read_text(encoding='utf-8'),re.M)
    require(len(names)==len(set(names))==51,'Historical module list changed')
    return names+['tests_lm.test_v05_c168_necessity_observability','tests_lm.test_v05_c169_interface_batch',
                  'tests_lm.test_v05_c170_structured_task_input','tests_lm.test_v05_c171_derived_result']

def run(*,c170_summary,output_dir,expected_head):
    root=Path(__file__).resolve().parents[2]
    def guard():
        require(git(root,'rev-parse','HEAD').decode().strip()==expected_head,'HEAD mismatch')
        require(git(root,'branch','--show-current').decode().strip()=='feat/sft-target-loss','Branch mismatch')
        require(not git(root,'status','--porcelain','--untracked-files=no').strip(),'Tracked tree dirty')
    guard();parent=validate_parent(c170_summary);pins,protected=protect_sources(root,parent)
    protected[str(Path(c170_summary).resolve())]=PARENT_SHA
    require(hashlib.sha256(blob(manifest())).hexdigest()==MANIFEST_SHA,'Manifest drift')
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    try:
        plan=out/'derived-result-plan.json';plan.write_bytes(blob(dict(manifest(),source_blobs=pins)))
        protected[str(plan.resolve())]=sha(plan)
        print('[C171] plan fixed; 600 proof checks; hand-written verifier, no learned policy',flush=True)
        summary,rows=collect();require(summary['counts']==EXPECTED,'Incomplete coverage')
        records=out/'proof-results.json';records.write_bytes(blob(rows));rh=sha(records)
        print(f"[C171] checked={len(rows)}/600 failed={summary['failed_checks']} verified={summary['verified']} rejected={summary['rejected']}",flush=True)
        guard();protect_sources(root,parent)
        for path,wanted in protected.items():
            require(sha(path)==wanted,'Protected input changed: '+path)
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,commit_sha=expected_head,
            status='PASS' if gate(summary) else 'FAIL',diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,C170_summary_sha256=PARENT_SHA,
            summary=summary,source_blobs=pins,input_sha256=protected,
            plan=dict(file=plan.name,sha256=sha(plan)),
            records=dict(file=records.name,rows=len(rows),serialized_bytes=records.stat().st_size,sha256=rh),
            training_steps=0,fresh_seed_count=0,learned_forward_calls=0,adapter_calls=0,evidence_writes=0,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=['Hand-written local-rule verifier and benchmark-only symbolic proof producer,not learned reasoning',
                'Trusted TaskView supplies current statuses and support identity;no upstream authentication or concurrent commit',
                'Ten C170 development templates,not heldout task generalization',
                'Local rules intentionally lack excluded middle/case split;two entailed-but-unproved controls stay rejected',
                'Rejection is neither learned abstention nor impossibility;no observed B is invented',
                'Rule evaluation counts are bounded;runtime budget debit/action dispatch/learning remain separate',
                'C159 unchanged;no production rollout or Gate E completion'])
        (out/'summary.json').write_bytes(blob(report))
        print('=== C171 RESULT ===',flush=True);print(blob(report).decode(),flush=True)
        return report
    except Exception as exc:
        (out/'invalid.json').write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status='INVALID',
            diagnostic_execution_valid=False,error=str(exc))))
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--c170-summary',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-head',required=True)
    run(**vars(p.parse_args()));return 0

if __name__=='__main__':
    raise SystemExit(main())
