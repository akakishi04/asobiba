"""C174: preregistered offline learned necessity pilot, paired syntax ablation.

Not final Gate E, a production FOLD core, a proof generator or a live agent.
Truth-table calculations below construct split groups/teacher labels ONLY.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import time

import numpy as np
import torch

from fold_lm.v05 import structured_task_input as task
from fold_lm.v05 import structured_necessity_probe as api

EXPERIMENT_ID = 'C174-v5e-learned-necessity-syntax-ablation'
STAGE = 'V5-E-LEARNED-NECESSITY-SYNTAX-ABLATION'
BASE = '2cc2b1f40e9c7638e4bc0f72c07feb85d95a9c26'
PARENT_SHA = '3c4759bbc14b4ab9849d482d2f330cbf1038c1473e2deab2aaf40f9637e635aa'
MANIFEST_SHA = '6b06991409954a6a97340a2fd93dcf22bd4622e9b90e9968a670f337c830f1a4'
DATA_SHA = 'eaae9aef5f64a204fe4d249bccbd437cd42f90172cd6f0eeb91be834b9450c65'
EXPECTED_DATA = {'templates': 640, 'rows': 51840, 'features': 72, 'semantic_groups': 40, 'train_rows': 42444, 'train_groups': 36, 'train_templates': 524, 'train_sufficient': 27816, 'train_needs_observation': 14628, 'eval_rows': 9396, 'eval_groups': 4, 'eval_templates': 116, 'eval_sufficient': 6744, 'eval_needs_observation': 2652}  # Filled from the immutable generator before training/registration.
SHAPES = ((((0, 1), 2), 3), ((0, (1, 2)), 3), ((0, 1), (2, 3)),
          (0, ((1, 2), 3)), (0, (1, (2, 3))))
BITS = tuple(itertools.product((0, 1), repeat=4))
PARTIAL = tuple(itertools.product((None, 0, 1), repeat=4))
PERMUTATIONS = tuple(itertools.permutations(range(4)))
PARENT_OWN = ('fold_lm/v05/structured_acquisition_lifecycle.py',
    'fold_lm/v05_benchmarks/gate_e_c173_acquisition_lifecycle.py',
    'tests_lm/test_v05_c173_acquisition_lifecycle.py', 'tools/run_c173.ps1',
    'docs/structured-acquisition-lifecycle-v0.1.md', 'docs/experiment-ledger-addendum-c173-preregistration.md')
OWN = ('fold_lm/v05/structured_necessity_probe.py',
    'fold_lm/v05_benchmarks/gate_e_c174_learned_necessity.py',
    'tests_lm/test_v05_c174_learned_necessity.py', 'tools/run_c174.ps1',
    'docs/learned-necessity-probe-v0.1.md', 'docs/experiment-ledger-addendum-c174-preregistration.md')


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


def nodes_for(shape, operators, negations):
    """Copy ordered syntax, with each fact occurring once; no simplification."""
    kinds = iter(operators); nodes = []
    def emit(s):
        if type(s) is int:
            nodes.append(task.Node('FACT', s, negate=bool(negations[s])))
        else:
            kind = next(kinds); left = emit(s[0]); right = emit(s[1])
            nodes.append(task.Node(kind, left=left, right=right))
        return len(nodes)-1
    emit(shape)
    return tuple(nodes)


def evaluate(nodes, values):
    stack = []
    for n in nodes:
        stack.append((values[n.fact] ^ int(n.negate)) if n.kind == 'FACT'
            else (stack[n.left] & stack[n.right]) if n.kind == 'AND'
            else (stack[n.left] | stack[n.right]))
    return stack[-1]


@lru_cache(maxsize=640)
def semantic_group(table):
    # Necessity is invariant to whole-output complementation as well as variable
    # permutations. Keep both in one split. Group IDs are never policy features.
    tables = []
    for p in PERMUTATIONS:
        renamed = tuple(table[BITS.index(tuple(b[p[i]] for i in range(4)))] for b in BITS)
        tables.extend((renamed, tuple(1-v for v in renamed)))
    return ''.join(map(str, min(tables)))


def known_development_groups():
    # The two 4-variable C170/C171 templates and all their permutation-equivalent
    # functions are forced into TRAIN, never presented as new pilot holdout.
    specs = ((SHAPES[2], ('OR', 'AND', 'AND')),
             (SHAPES[4], ('OR', 'AND', 'OR')))
    return frozenset(semantic_group(tuple(evaluate(nodes_for(s, ops, (0,)*4), b) for b in BITS))
                     for s, ops in specs)


def partition(group):
    if group in known_development_groups():
        return 'TRAIN'
    key = hashlib.sha256(('C174:function-permutation-split:v1|' + group).encode()).digest()
    return 'PILOT_EVAL' if int.from_bytes(key[:8], 'big') % 5 == 0 else 'TRAIN'


def structures():
    for si, shape in enumerate(SHAPES):
        for ops in itertools.product(('AND', 'OR'), repeat=3):
            for neg in itertools.product((0, 1), repeat=4):
                nodes = nodes_for(shape, ops, neg)
                table = tuple(evaluate(nodes, b) for b in BITS)
                group = semantic_group(table)
                yield dict(template_id=f'{si}-'+''.join(o[0] for o in ops)+'-'+''.join(map(str, neg)),
                    nodes=nodes, truth_table=table, group=group, split=partition(group))


def make_view(nodes, values):
    facts = tuple(task.Fact(chr(65+i)) if v is None else
        task.Fact(chr(65+i), 'OBSERVED', v, ('visible:'+chr(65+i),)) for i, v in enumerate(values))
    return task.TaskView('C174|task', 'C174', nodes, facts,
                         task.Resources(12, 4, (True, False, False), (True, False, False)))


def label_for(table, visible):
    # Additional observation is logically needed iff both conclusions are possible.
    # This is not which fact/tool to request and not a claim of proof availability.
    return int(len({v for b, v in zip(BITS, table, strict=True)
        if all(x is None or x == y for x, y in zip(visible, b, strict=True))}) == 2)


def dataset():
    features = []; labels = []; template_ids = []; metadata = []
    def consumer(p):
        return api.packet_values(p)
    consumer.input_schema = task.SCHEMA
    for ti, spec in enumerate(structures()):
        metadata.append(dict(spec, nodes=[asdict(n) for n in spec['nodes']], truth_table=list(spec['truth_table'])))
        for visible in PARTIAL:
            # Capture the actual canonical input BEFORE computing its teacher label.
            features.append(task.deliver(make_view(spec['nodes'], visible), consumer))
            labels.append(label_for(spec['truth_table'], visible)); template_ids.append(ti)
    x = np.asarray(features, dtype='<i4'); y = np.asarray(labels, dtype='<i8')
    ids = np.asarray(template_ids, dtype='<i4')
    splits = np.asarray([int(metadata[i]['split'] == 'PILOT_EVAL') for i in ids], dtype='u1')
    group_names = sorted({r['group'] for r in metadata})
    groups = np.asarray([group_names.index(metadata[i]['group']) for i in ids], dtype='<i4')
    profile = dict(templates=len(metadata), rows=len(y), features=72, semantic_groups=len(group_names))
    for name, code in (('train', 0), ('eval', 1)):
        mask = splits == code
        profile.update({name+'_rows':int(mask.sum()), name+'_groups':len(set(groups[mask].tolist())),
            name+'_templates':len(set(ids[mask].tolist())), name+'_sufficient':int((y[mask] == 0).sum()),
            name+'_needs_observation':int((y[mask] == 1).sum())})
    require(not set(groups[splits == 0]) & set(groups[splits == 1]), 'Semantic group leakage')
    h = hashlib.sha256(blob(metadata))
    for a in (x, y, ids, splits, groups): h.update(a.tobytes())
    return dict(features=x, labels=y, template_ids=ids, split_codes=splits, groups=groups,
                metadata=metadata, profile=profile, content_sha256=h.hexdigest())


def manifest():
    return dict(experiment_id=EXPERIMENT_ID, input_schema=task.SCHEMA,
        shapes=SHAPES, operator_order='preorder,AND/OR', negation_masks=list(itertools.product((0,1), repeat=4)),
        partial_order=[None, 0, 1], function_group='minimum 16-bit truth table over 24 variable permutations and output complementation',
        split_salt='C174:function-permutation-split:v1|', eval_modulus=5, eval_residue=0,
        forced_train_groups=sorted(known_development_groups()), data_profile=EXPECTED_DATA,
        dataset_content_sha256=DATA_SHA, arms=api.ARMS, seeds=api.SEEDS, scale=api.SCALES,
        model='MLP72-128-ReLU-128-ReLU-2', parameters=26114, optimizer='Adam', lr=0.001,
        betas=[0.9,0.999], eps=1e-8, weight_decay=0, loss='unweighted CrossEntropyLoss',
        steps=api.TRAIN_STEPS, batch_size=api.BATCH_SIZE, sampling='with replacement, paired seed+1000000',
        device='cpu', dtype='float32', threads=2, deterministic_algorithms=True,
        training_resubstitution_predictions=254664, pilot_predictions=56376,
        training_forward_calls=12000, postfit_inference_forward_calls=312,
        evaluation='once after all six final checkpoints saved; raw argmax, no rule/proof/action mask',
        decision='each seed full macro-group BA exceeds matched ablation and missing-rule; both recalls>0.5',
        scientific_scope='development pilot, not final Gate E or a learned FOLD-core/live controller')


def metrics(labels, prediction, groups):
    y, p, g = (np.asarray(x) for x in (labels, prediction, groups))
    require(y.ndim == p.ndim == g.ndim == 1 and len(y) == len(p) == len(g) and len(y) > 0,
            'Bad metric shape')
    require(set(y.tolist()) <= {0,1} and set(p.tolist()) <= {0,1}, 'Bad metric labels')
    def local(a, b):
        counts = [[int(((a == i) & (b == j)).sum()) for j in (0,1)] for i in (0,1)]
        require(all(sum(row) > 0 for row in counts), 'Both label classes required')
        recall = [counts[i][i]/sum(counts[i]) for i in (0,1)]
        return dict(confusion=counts, sufficient_recall=recall[0], needs_recall=recall[1],
                    balanced_accuracy=sum(recall)/2, accuracy=float((a == b).mean()))
    per_group = {str(i):local(y[g == i], p[g == i]) for i in sorted(set(g.tolist()))}
    return dict(local(y,p), macro_group_balanced_accuracy=float(np.mean(
        [v['balanced_accuracy'] for v in per_group.values()])), per_group=per_group)


def gate(pairs, missing):
    if len(pairs) != len(api.SEEDS) or [r.get('seed') for r in pairs] != list(api.SEEDS):
        return False
    return all(r.get('paired_initial_equal') is True and r.get('paired_batches_equal') is True
        and r['full']['macro_group_balanced_accuracy'] > r['ablated']['macro_group_balanced_accuracy']
        and r['full']['macro_group_balanced_accuracy'] > missing['macro_group_balanced_accuracy']
        and r['full']['sufficient_recall'] > 0.5 and r['full']['needs_recall'] > 0.5
        for r in pairs)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def validate_parent(path):
    require(sha(path) == PARENT_SHA, 'C173 parent hash mismatch')
    p = json.loads(Path(path).read_text(encoding='utf-8'))
    require(p.get('experiment_id') == 'C173-v5e-bounded-acquisition-lifecycle' and p.get('commit_sha') == BASE
        and p.get('status') == 'PASS' and p.get('diagnostic_execution_valid') is True
        and p.get('production_runtime_modified') is False and p.get('gate_e_candidate') is False,
        'Expected accepted C173')
    require(p['summary']['scenarios'] == 122 and p['summary']['failed_checks'] == 0
        and p['summary']['fact_publications'] == 24 and len(p['source_blobs']) == 36, 'C173 profile mismatch')
    return p


def protect_sources(root, parent):
    pins = dict(parent['source_blobs']); hashes = {}
    for name in PARENT_OWN: pins[name] = git(root,'rev-parse',BASE+':fold/'+name).decode().strip()
    for name, want in pins.items():
        require(git(root,'rev-parse','HEAD:fold/'+name).decode().strip() == want, 'Historical source changed: '+name)
    for name in (*pins, *OWN):
        canonical = git(root,'show','HEAD:fold/'+name); raw = (root/name).read_bytes()
        require(raw == canonical or raw == canonical.replace(b'\n',b'\r\n'), 'Uncommitted source: '+name)
        hashes[str((root/name).resolve())] = hashlib.sha256(raw).hexdigest()
    return pins, hashes


def regression_modules(root):
    text = (Path(root)/'tools/run_c167.ps1').read_text(encoding='utf-8')
    names = re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$',text,re.M)
    require(len(names) == len(set(names)) == 51, 'Historical module list drift')
    return names + ['tests_lm.'+n for n in ('test_v05_c168_necessity_observability',
        'test_v05_c169_interface_batch','test_v05_c170_structured_task_input','test_v05_c171_derived_result',
        'test_v05_c172_action_runtime','test_v05_c173_acquisition_lifecycle','test_v05_c174_learned_necessity')]


def run(*, c173_summary, output_dir, expected_head):
    root = Path(__file__).resolve().parents[2]
    def guard():
        require(git(root,'rev-parse','HEAD').decode().strip() == expected_head, 'HEAD mismatch')
        require(git(root,'branch','--show-current').decode().strip() == 'feat/sft-target-loss', 'Branch mismatch')
        require(not git(root,'status','--porcelain','--untracked-files=no').strip(), 'Tracked tree dirty')
    guard(); parent = validate_parent(c173_summary); pins, protected = protect_sources(root,parent)
    protected[str(Path(c173_summary).resolve())] = PARENT_SHA
    require(hashlib.sha256(blob(manifest())).hexdigest() == MANIFEST_SHA, 'Preregistered manifest drift')
    out = Path(output_dir); out.mkdir(parents=True,exist_ok=False); started = time.perf_counter()
    artifacts = []; fits = []; pairs = []
    def save(name, raw):
        path = out/name; path.write_bytes(raw)
        artifacts.append(dict(file=name,sha256=sha(path),serialized_bytes=len(raw)))
    save('necessity-plan.json',blob(dict(manifest(),source_blobs=pins)))
    try:
        torch.set_num_threads(2); torch.use_deterministic_algorithms(True)
        print('[C174] plan fixed; three paired seeds; CPU float32; no live actions or proof oracle',flush=True)
        data = dataset()
        require(data['profile'] == EXPECTED_DATA and data['content_sha256'] == DATA_SHA,'Data/split drift')
        save('templates-and-splits.json',blob(data['metadata']))
        data_path = out/'pilot-data.npz'
        np.savez_compressed(data_path, **{k:data[k] for k in ('features','labels','template_ids','split_codes','groups')})
        artifacts.append(dict(file=data_path.name,sha256=sha(data_path),serialized_bytes=data_path.stat().st_size))
        data_before = data['content_sha256']
        train = data['split_codes'] == 0; test = ~train
        xraw = torch.from_numpy(data['features']); ytrain = torch.from_numpy(data['labels'][train].copy())
        models = {}
        # All six fits are completed and saved BEFORE any pilot evaluation.
        for seed in api.SEEDS:
            torch.manual_seed(seed); initial = api.NecessityProbe().cpu()
            initial_hash = api.fingerprint(initial)
            for arm in api.ARMS:
                xtrain = api.prepare(xraw[train],arm)
                def progress(row,seed=seed,arm=arm):
                    print(f"[C174] seed={seed} arm={arm} step={row['step']}/2000 train_loss={row['training_loss']:.6f}",flush=True)
                model, log = api.fit(initial,xtrain,ytrain,seed,progress=progress)
                require(api.fingerprint(initial) == initial_hash,'Initial model changed')
                final_hash = api.fingerprint(model)
                path = out/f'probe-{seed}-{arm}.pt'
                torch.save(dict(schema=task.SCHEMA,seed=seed,arm=arm,steps=api.TRAIN_STEPS,
                    state_dict=model.state_dict()),path)
                restored = api.NecessityProbe().cpu()
                checkpoint = torch.load(path,map_location='cpu',weights_only=True)
                restored.load_state_dict(checkpoint['state_dict'],strict=True)
                require(api.fingerprint(restored) == final_hash,'Checkpoint roundtrip drift')
                artifacts.append(dict(file=path.name,sha256=sha(path),serialized_bytes=path.stat().st_size))
                fits.append(dict(seed=seed,arm=arm,initial_sha256=initial_hash,final_sha256=final_hash,
                    parameters=sum(p.numel() for p in model.parameters()),**log))
                models[(seed,arm)] = restored.eval()
        require(len(fits) == 6 and all(f['steps'] == 2000 and f['examples_drawn'] == 512000
            and f['parameters'] == 26114 for f in fits), 'Incomplete registered training workload')
        for seed in api.SEEDS:
            pair_fits = [f for f in fits if f['seed'] == seed]
            require(len(pair_fits) == 2 and pair_fits[0]['initial_sha256'] == pair_fits[1]['initial_sha256']
                and pair_fits[0]['batch_schedule_sha256'] == pair_fits[1]['batch_schedule_sha256'],
                'Paired initialization/minibatch contract violated')
        yeval = data['labels'][test]; geval = data['groups'][test]
        absent = (data['features'][test,48:62:4] == 0).any(axis=1).astype(np.int64)
        baseline = metrics(yeval,absent,geval)
        baseline_rows = dict(missing_fact_rule=baseline,
            always_sufficient=metrics(yeval,np.zeros_like(yeval),geval),
            always_needs_observation=metrics(yeval,np.ones_like(yeval),geval))
        eval_records = []; train_predictions = []; training_metrics = []
        for seed in api.SEEDS:
            results = {}
            for arm in api.ARMS:
                xeval = api.prepare(xraw[test],arm)
                pred, logits = api.predict(models[(seed,arm)],xeval)
                results[arm] = metrics(yeval,pred.numpy(),geval)
                train_pred, _ = api.predict(models[(seed,arm)],api.prepare(xraw[train],arm))
                tm = metrics(data['labels'][train],train_pred.numpy(),data['groups'][train])
                training_metrics.append(dict(seed=seed,arm=arm,**{k:v for k,v in tm.items() if k != 'per_group'}))
                train_predictions.append(train_pred.numpy().astype('i1'))
                eval_records.append(dict(seed=seed,arm=arm,row_indices=np.flatnonzero(test).tolist(),
                    predictions=pred.tolist(),logits=logits.tolist()))
            same = [f for f in fits if f['seed'] == seed]
            pair = dict(seed=seed,full=results[api.ARMS[0]],ablated=results[api.ARMS[1]],
                paired_initial_equal=same[0]['initial_sha256'] == same[1]['initial_sha256'],
                paired_batches_equal=same[0]['batch_schedule_sha256'] == same[1]['batch_schedule_sha256'])
            pairs.append(pair)
            print(f"[C174] seed={seed} macro_BA full={pair['full']['macro_group_balanced_accuracy']:.6f} "
                f"ablated={pair['ablated']['macro_group_balanced_accuracy']:.6f} missing_rule={baseline['macro_group_balanced_accuracy']:.6f}",flush=True)
        save('pilot-predictions.json',blob(eval_records))
        training_path = out/'training-predictions.npz'
        np.savez_compressed(training_path,row_indices=np.flatnonzero(train).astype('<i4'),
                            predictions=np.stack(train_predictions))
        artifacts.append(dict(file=training_path.name,sha256=sha(training_path),serialized_bytes=training_path.stat().st_size))
        # Recompute the array/metadata fingerprint without repeating data generation.
        h = hashlib.sha256(blob(data['metadata']))
        for k in ('features','labels','template_ids','split_codes','groups'): h.update(data[k].tobytes())
        require(h.hexdigest() == data_before,'Dataset mutated')
        guard(); protect_sources(root,parent)
        for path,wanted in protected.items(): require(sha(path) == wanted,'Protected input changed: '+path)
        for item in artifacts: require(sha(out/item['file']) == item['sha256'],'Output changed: '+item['file'])
        report = dict(experiment_id=EXPERIMENT_ID,stage=STAGE,commit_sha=expected_head,
            status='PASS' if gate(pairs,baseline) else 'FAIL',diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,C173_summary_sha256=PARENT_SHA,
            source_blobs=pins,input_sha256=protected,artifacts=artifacts,data_profile=data['profile'],
            training_metrics=training_metrics,training_resubstitution_predictions=sum(len(r) for r in train_predictions),
            data_content_sha256=DATA_SHA,fit_records=fits,pairs=pairs,baselines=baseline_rows,
            fresh_seed_count=3,trained_models=len(fits),training_steps_total=sum(f['steps'] for f in fits),
            training_examples_drawn=sum(f['examples_drawn'] for f in fits),
            training_forward_calls=sum(f['steps'] for f in fits),
            inference_forward_calls=sum((len(r['predictions'])+1023)//1024 for r in eval_records)
                + sum((len(r)+1023)//1024 for r in train_predictions),
            pilot_predictions=sum(len(r['predictions']) for r in eval_records),
            actual_acquisitions=0,proof_checker_calls=0,evidence_writes=0,network_calls=0,
            environment=dict(torch=torch.__version__,numpy=np.__version__,device='cpu',dtype='float32',threads=2),
            wall_clock_seconds=time.perf_counter()-started,
            limitations=['offline learned diagnostic MLP,not FOLD core or live autonomous policy',
                'read-once four-variable development-pilot domain,not final Gate E holdout',
                'logical need for some observation,not which fact/tool or proof generation',
                'teacher labels/grouping are exhaustive evaluator work,never inference features',
                'paired-seed directional criterion is not a statistical significance or general-intelligence claim'])
        (out/'summary.json').write_bytes(blob(report))
        print('=== C174 RESULT ===',flush=True);print(blob(report).decode(),flush=True)
        return report
    except Exception as exc:
        (out/'invalid.json').write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,status='INVALID',
            diagnostic_execution_valid=False,error=str(exc),completed_fits=fits,completed_pairs=pairs)))
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--c173-summary',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-head',required=True);run(**vars(p.parse_args()));return 0


if __name__ == '__main__':
    raise SystemExit(main())
