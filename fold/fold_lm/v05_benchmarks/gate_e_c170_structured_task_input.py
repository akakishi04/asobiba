"""C170: implement and verify a bounded, explicit task-to-policy input contract.

No old-model retuning, answer solver, action execution or observed-state commit.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import time

from fold_lm.v05 import structured_task_input as api

EXPERIMENT_ID = "C170-v5e-structured-task-input-contract"
STAGE = "V5-E-STRUCTURED-TASK-INPUT-CONTRACT"
BASE = "c227e93c3c6f73dbf30fcfd457da88d3f01c1355"
MANIFEST_SHA = "012efdd6e6ad2656929d034a95c93fdfda256b39df1c6788e0a5ecceb9ec5450"
PARENT_SHA = "1a509646a01c26306f6a41b0dfaca968be39500d12e21bef7d04b98b82fd2ae6"
EXPECTED = dict(necessity_cases=8, template_roundtrips=252, status_roundtrips=16,
    resource_roundtrips=256, consumer_calls=532, capture_attempts=532, malformed_cases=40)
OWN = ("fold_lm/v05/structured_task_input.py",
       "fold_lm/v05_benchmarks/gate_e_c170_structured_task_input.py",
       "tests_lm/test_v05_c170_structured_task_input.py", "tools/run_c170.ps1",
       "docs/experiment-ledger-addendum-c170-preregistration.md",
       "docs/structured-task-interface-v0.1.md")
EXTRA = ("fold_lm/v05_benchmarks/gate_e_c169_interface_batch.py",
         "tests_lm/test_v05_c169_interface_batch.py", "tools/run_c169.ps1",
         "docs/experiment-ledger-addendum-c169-preregistration.md")


class InvalidExecution(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InvalidExecution(message)


def blob(x):
    return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def templates():
    N=api.Node
    return (
        ("A",1,(N("FACT",0),)),
        ("NOT_A",1,(N("FACT",0,negate=True),)),
        ("A_AND_A",1,(N("FACT",0),N("FACT",0),N("AND",left=0,right=1))),
        ("A_AND_B",2,(N("FACT",0),N("FACT",1),N("AND",left=0,right=1))),
        ("A_OR_B",2,(N("FACT",0),N("FACT",1),N("OR",left=0,right=1))),
        ("NOT_A_OR_B",2,(N("FACT",0,negate=True),N("FACT",1),N("OR",left=0,right=1))),
        ("AB_AND_C_OR",3,(N("FACT",0),N("FACT",1),N("AND",left=0,right=1),N("FACT",2),N("OR",left=2,right=3))),
        ("A_BC_OR_AND",3,(N("FACT",0),N("FACT",1),N("FACT",2),N("OR",left=1,right=2),N("AND",left=0,right=3))),
        ("AB_AND_CD_AND_OR",4,(N("FACT",0),N("FACT",1),N("AND",left=0,right=1),N("FACT",2),N("FACT",3),N("AND",left=3,right=4),N("OR",left=2,right=5))),
        ("A_B_C_D_OR_AND_OR",4,(N("FACT",0),N("FACT",1),N("FACT",2),N("FACT",3),N("OR",left=2,right=3),N("AND",left=1,right=4),N("OR",left=0,right=5))),
    )


def fact(i, value):
    name=chr(65+i)
    return api.Fact(name) if value is None else api.Fact(name,"OBSERVED",value,("observed:"+name,))


def view(nodes, values, resources=api.Resources()):
    return api.TaskView("C170|request","C170",nodes,tuple(fact(i,v) for i,v in enumerate(values)),resources)


def template_views():
    for name,n,nodes in templates():
        for i,values in enumerate(itertools.product((None,0,1),repeat=n)):
            yield name+":"+str(i),view(nodes,values)


def fact_status(i,status):
    name=chr(65+i)
    refs=() if status=="UNOBSERVED" else ("ref:"+name,"other:"+name) if status=="CONFLICT" else ("ref:"+name,)
    return api.Fact(name,status,0 if status=="OBSERVED" else None,refs)


def status_views():
    base=view(templates()[3][2],(1,1))
    for i,status in itertools.product(range(2),api.STATUSES):
        fs=list(base.facts);fs[i]=fact_status(i,status)
        yield f"slot{i}:{status}",replace(base,facts=tuple(fs))


def resource_views():
    base=view(templates()[3][2],(0,None))
    masks=tuple(itertools.product((False,True),repeat=3))
    for i,(av,pe,bud) in enumerate(itertools.product(masks,masks,((0,0),(0,1),(3,0),(3,1)))):
        yield str(i),replace(base,resources=api.Resources(*bud,av,pe))


def manifest():
    return dict(experiment_id=EXPERIMENT_ID,input_schema=api.SCHEMA,feature_width=api.FEATURE_WIDTH,
        templates=[dict(name=n,facts=k,nodes=[asdict(x) for x in ns]) for n,k,ns in templates()],
        value_states=[None,0,1],statuses=list(api.STATUSES),tools=list(api.TOOLS),
        resource_masks="all 8 availability masks x all 8 permission masks x 4 budget pairs",
        budget_pairs=[[0,0],[0,1],[3,0],[3,1]],
        necessity="AND/OR x known A0/1 x audit-only stale0/1; no hidden B; evaluator after capture",
        malformed="28 non-observed payload injections +12 malformed policy packets",
        counts=dict(EXPECTED),hidden_values_in_input=False,training_steps=0,fresh_seed_count=0,
        learned_forward_calls=0,legacy_controller_adaptation=False,
        scope="development contract verification, not learned necessity or full Gate E")


def malformed_probes():
    rows=[]
    for i,status,value in itertools.product(range(2),[s for s in api.STATUSES if s!="OBSERVED"],(0,1)):
        f=fact_status(i,status)
        rows.append((f"unusable:{i}:{status}:{value}",lambda f=f,v=value:replace(f,value=v)))
    p=api.encode(view((api.Node("FACT",0),),(None,)))
    def changed(index,value):
        x=list(p.features);x[index]=value
        return replace(p,features=tuple(x))
    invalid=(('schema',replace(p,schema='legacy')),('short',replace(p,features=p.features[:-1])),
        ('node-padding',changed(10,1)),('fact-padding',changed(50,1)),
        ('node-mask',changed(4,0)),('fact-mask',changed(46,0)),
        ('hidden-placeholder',changed(49,1)),('kind',changed(5,9)),
        ('boolean-number',changed(0,True)),('tool-flag',changed(64,2)),
        ('budget-range',changed(62,api.MAX_INTEGER+1)),
        ('binding-count',replace(p,binding=replace(p.binding,fact_ids=()))))
    rows.extend((name,lambda packet=packet:api.decode(packet)) for name,packet in invalid)
    return rows


def check_malformed():
    records=[]
    for name,fn in malformed_probes():
        try:
            fn()
        except (ValueError,TypeError) as error:
            records.append(dict(case_id=name,rejected=True,error_type=type(error).__name__))
        else:
            records.append(dict(case_id=name,rejected=False,error_type=None))
    return records


def collect_contract():
    rows=[];counts=Counter();necessity_rows=[]
    def consumer(packet):
        counts['consumer_calls']+=1
        return packet
    consumer.input_schema=api.SCHEMA
    def capture(group,name,t):
        counts['capture_attempts']+=1
        before=blob(asdict(t));packet=None;error=None
        try:
            packet=api.deliver(t,consumer)
            recovered=api.decode(packet)
            passed=(recovered==t and blob(asdict(t))==before)
        except (ValueError,TypeError) as exc:
            # Rejection of a well-formed registered input is a finite contract failure.
            passed=False;error=type(exc).__name__+': '+str(exc)
        row=dict(group=group,case_id=name,passed=passed,error=error,
                 packet=asdict(packet) if type(packet) is api.PolicyInput else None)
        rows.append(row);return packet
    # All relevant distinctions come from visible syntax/facts, not necessity labels.
    pending=[]
    for op,a,stale in itertools.product(('AND','OR'),(0,1),(0,1)):
        ns=(api.Node('FACT',0),api.Node('FACT',1),api.Node(op,left=0,right=1))
        packet=capture('necessity',f'{op}-{a}-stale{stale}',view(ns,(a,None)))
        pending.append((op,a,stale,packet));counts['necessity_cases']+=1
    groups=defaultdict(list)
    for op,a,stale,packet in pending:
        outputs=[(a & b) if op=='AND' else (a | b) for b in (0,1)]
        need=outputs[0]!=outputs[1]
        if type(packet) is api.PolicyInput:
            groups[packet.features].append(need)
        necessity_rows.append(dict(operator=op,known_a=a,audit_stale=stale,
            requires_acquisition=need,possible_outputs=sorted(set(outputs)),
            feature_sha256=hashlib.sha256(blob(packet.features)).hexdigest() if type(packet) is api.PolicyInput else None))
    for group,gen,count_name in (('templates',template_views(),'template_roundtrips'),
                                ('statuses',status_views(),'status_roundtrips'),
                                ('resources',resource_views(),'resource_roundtrips')):
        for name,t in gen:
            capture(group,name,t);counts[count_name]+=1
    malformed=check_malformed();counts['malformed_cases']=len(malformed)
    summary=dict(counts,failed_roundtrips=sum(not x['passed'] for x in rows),
        malformed_rejected=sum(x['rejected'] for x in malformed),
        necessity_classes=len(groups),necessity_conflicting_classes=sum(len(set(g))>1 for g in groups.values()),
        necessity_error_lower_bound=sum(len(g)-max(Counter(g).values()) for g in groups.values()),
        resource_classes=len({tuple(x['packet']['features']) for x in rows if x['group']=='resources' and x['packet'] is not None}),
        feature_width=api.FEATURE_WIDTH)
    return summary,rows,necessity_rows,malformed


def gate(s):
    return all(s.get(k)==v for k,v in EXPECTED.items()) and all(s.get(k)==v for k,v in dict(
        failed_roundtrips=0,malformed_rejected=40,necessity_classes=4,necessity_conflicting_classes=0,
        necessity_error_lower_bound=0,resource_classes=256,feature_width=72).items())


def validate_parent(path):
    require(sha(path)==PARENT_SHA,'C169 report hash mismatch')
    p=json.loads(Path(path).read_text(encoding='utf-8'))
    require(p.get('experiment_id')=='C169-v5e-frozen-interface-readiness-batch' and p.get('commit_sha')==BASE
        and p.get('status')=='FAIL' and p.get('diagnostic_execution_valid') is True
        and p.get('production_runtime_modified') is False and p.get('gate_e_candidate') is False,'Wrong accepted C169 identity')
    require(p.get('summary')==dict(finite_violation_sections=0,gap_sections=3,interface_ready=False,sections_completed=6)
        and len(p.get('sections',[]))==6,'Full accepted C169 profile required')
    return p


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])


def protect_sources(root,parent):
    pins=dict(parent['source_blobs']); hashes={}
    for name in EXTRA:
        pins[name]=git(root,'rev-parse',BASE+':fold/'+name).decode().strip()
    for name,wanted in pins.items():
        require(git(root,'rev-parse','HEAD:fold/'+name).decode().strip()==wanted,'Historical source drift: '+name)
    for name in tuple(pins)+OWN:
        canonical=git(root,'show','HEAD:fold/'+name); raw=(root/name).read_bytes()
        require(raw==canonical or raw==canonical.replace(b'\n',b'\r\n'),'Uncommitted source: '+name)
        hashes[str((root/name).resolve())]=hashlib.sha256(raw).hexdigest()
    return pins,hashes


def regression_modules(root):
    text=(Path(root)/'tools/run_c167.ps1').read_text(encoding='utf-8')
    names=re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$',text,re.M)
    require(len(names)==len(set(names))==51,'Historical module list changed')
    return names+['tests_lm.test_v05_c168_necessity_observability',
                  'tests_lm.test_v05_c169_interface_batch','tests_lm.test_v05_c170_structured_task_input']


def run(*,c169_summary,output_dir,expected_head):
    root=Path(__file__).resolve().parents[2]
    def guard():
        require(git(root,'rev-parse','HEAD').decode().strip()==expected_head,'HEAD mismatch')
        require(git(root,'branch','--show-current').decode().strip()=='feat/sft-target-loss','Branch mismatch')
        require(not git(root,'status','--porcelain','--untracked-files=no').strip(),'Tracked tree dirty')
    guard();p=validate_parent(c169_summary);pins,protected=protect_sources(root,p)
    protected[str(Path(c169_summary).resolve())]=PARENT_SHA
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    require(hashlib.sha256(blob(manifest())).hexdigest()==MANIFEST_SHA,'Registered manifest drift')
    plan_file=out/'input-contract-plan.json';plan_file.write_bytes(blob(dict(manifest(),source_blobs=pins)))
    protected[str(plan_file.resolve())]=sha(plan_file)
    try:
        print('[C170] plan fixed; new structured input; 532 captures +40 malformed controls; training=0',flush=True)
        summary,rows,necessity,malformed=collect_contract()
        require(all(summary.get(k)==v for k,v in EXPECTED.items() if k!='consumer_calls'),'Incomplete registered coverage')
        captures=out/'policy-inputs.json';captures.write_bytes(blob(rows))
        print(f"[C170] captures={summary['consumer_calls']}/532 conflicts={summary['necessity_conflicting_classes']} guards={summary['malformed_rejected']}/40",flush=True)
        guard();protect_sources(root,p)
        for path,wanted in protected.items():
            require(sha(path)==wanted,'Protected bytes changed: '+path)
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,commit_sha=expected_head,
            status='PASS' if gate(summary) else 'FAIL',diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,C169_summary_sha256=PARENT_SHA,
            source_blobs=pins,input_sha256=protected,summary=summary,necessity=necessity,malformed=malformed,
            plan=dict(file=plan_file.name,sha256=sha(plan_file)),
            captures=dict(file=captures.name,rows=len(rows),sha256=sha(captures),serialized_bytes=captures.stat().st_size),
            training_steps=0,fresh_seed_count=0,learned_forward_calls=0,adapter_calls=0,
            wall_clock_seconds=time.perf_counter()-start,
            limitations=['New explicit policy schema; no legacy Controller/checkpoint adaptation',
                'Consumer is a capture callback, not a trained policy or necessity predictor',
                'No expression evaluation in encoder; truth table is post-capture scoring only',
                'Fact status/support metadata are supplied by fixtures, not authenticated by this adapter',
                'Opaque IDs are binding sidecars; policy numeric input preserves indexed syntax and visible state',
                'Finite development contract, not heldout generalization, action execution, derived-answer verification or Gate E'])
        (out/'summary.json').write_bytes(blob(report));print('=== C170 RESULT ===',flush=True);print(blob(report).decode(),flush=True)
        return report
    except Exception as e:
        (out/'invalid.json').write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status='INVALID',error=str(e))))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--c169-summary',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-head',required=True)
    run(**vars(p.parse_args()));return 0


if __name__=='__main__':
    raise SystemExit(main())
