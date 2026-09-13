"""V5-C / C38: isolated model/allocator accounting for the C35 boundary models.

Four fresh sequential worker processes prevent one variant's live graphs and CUDA
allocator cache from being attributed to another. Only the selected model moves
to CUDA. CPU references are used solely for parity, never as model inputs.
No new kernels, validation policy, training, or graph-pool sharing are introduced.

Report tensor payload/storage, a diagnostic torch.save state_dict archive size,
and separately CUDA allocated/reserved and setup/steady peaks. Allocator counters
are NOT whole-device/process VRAM: driver/context/non-PyTorch allocations and CPU
RSS are outside scope. C38 does not time requests or declare a Gate C pass.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import torch

VARIANTS = ('dense_eager', 'triton_eager', 'dense_graph', 'triton_graph')
FIXTURE_SHA = 'a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e'
C35_HASHES = {
    '6c31c2aab5fbcf5dd6c04c2d929acce0ae5d04004bd0cb28610e3628b0d89573',
    '3edb16114882962b9e378c38a7dd6e84341c546b0d5aed1779e1a8c407c3caef',
}
PREFIX = 'C38_RESULT='
FIELDS = (
    'model_unique_storage_bytes', 'state_dict_archive_bytes',
    'idle_allocated_bytes', 'idle_reserved_bytes',
    'steady_peak_allocated_bytes', 'steady_peak_reserved_bytes',
    'setup_peak_allocated_bytes', 'setup_peak_reserved_bytes',
    'retained_after_trim_allocated_bytes', 'retained_after_trim_reserved_bytes',
)


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def tensor_accounting(tensors):
    """Count aliased storage only once; logical bytes are deliberately separate."""
    storage, logical, count = {}, 0, 0
    for tensor in tensors:
        if not isinstance(tensor, torch.Tensor) or tensor.layout != torch.strided:
            raise TypeError('Only strided tensors are supported')
        if tensor.device.type == 'meta':
            raise ValueError('Meta tensors have no resident storage')
        count += 1
        logical += tensor.numel() * tensor.element_size()
        raw = tensor.untyped_storage()
        if raw.nbytes():
            storage[str(tensor.device), raw.data_ptr()] = raw.nbytes()
    return dict(tensor_count=count, logical_tensor_bytes=logical,
                unique_storage_bytes=sum(storage.values()))


def summarize(workers):
    table = {}
    for worker in workers:
        name = worker['variant']
        if name not in VARIANTS or name in table:
            raise ValueError('Unknown or duplicate variant')
        if worker.get('fixture_sha256') != FIXTURE_SHA:
            raise ValueError('Fixture mismatch')
        if worker.get('parity_passed') is not True or worker.get('model_state_unchanged') is not True:
            raise ValueError('Validation failed')
        row = worker['accounting']
        for field in FIELDS:
            if type(row[field]) is not int or row[field] < 0:
                raise ValueError('Byte counts must be nonnegative integers')
        for allocated, reserved in (
            ('idle_allocated_bytes', 'idle_reserved_bytes'),
            ('steady_peak_allocated_bytes', 'steady_peak_reserved_bytes'),
            ('setup_peak_allocated_bytes', 'setup_peak_reserved_bytes'),
            ('retained_after_trim_allocated_bytes', 'retained_after_trim_reserved_bytes'),
        ):
            if row[reserved] < row[allocated]:
                raise ValueError('Reserved cannot be below allocated')
        if row['steady_peak_allocated_bytes'] < row['idle_allocated_bytes']:
            raise ValueError('Steady peak cannot be below end-of-window allocation')
        if type(worker['score_A']) not in (int, float) or not math.isfinite(worker['score_A']) or not 0 <= worker['score_A'] <= 1:
            raise ValueError('Invalid task score')
        table[name] = dict(row, score_A=worker['score_A'])
    if set(table) != set(VARIANTS):
        raise ValueError('Missing variant')
    comparisons = {}
    for mode in ('eager', 'graph'):
        dense, triton = table['dense_' + mode], table['triton_' + mode]
        comparisons['triton_vs_dense_' + mode] = {
            field: {
                'triton_minus_dense_bytes': triton[field] - dense[field],
                'ratio': triton[field] / dense[field] if dense[field] else None,
            } for field in FIELDS
        }
    return dict(variants=table, comparisons=comparisons)


def snapshot():
    torch.cuda.synchronize()
    return {
        'allocated_bytes': torch.cuda.memory_allocated(),
        'reserved_bytes': torch.cuda.memory_reserved(),
        'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
        'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
    }


def prepare_cpu(fixture_path, kind):
    from fold_lm.v05_benchmarks import gate_c_full_model_validation_boundary as c35
    from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture
    from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import _load_initializations
    if file_hash(c35.__file__) not in C35_HASHES:
        raise RuntimeError('C35 source differs from the tested boundary contract')
    if file_hash(fixture_path) != FIXTURE_SHA:
        raise ValueError('Use the unchanged C35/C37 composition fixture')
    fixture = load_runtime_fixture(fixture_path, device='cpu')
    if fixture['task'] != 'composition':
        raise ValueError('Only composition is supported')
    init = _load_initializations(str(fixture_path))
    counts = {role: [int(w.correction_nnz) for w in getattr(init, role).encoded_weights]
              for role in ('up', 'down')}
    if not all(n > 0 for group in counts.values() for n in group):
        raise ValueError('E must be present in every module')
    models = c35.make_models(fixture['models']['dense'], init)  # All still on CPU.
    model = models[kind + '_boundary']
    examples, cfg = fixture['validation'], model.config
    a = tuple(t.cpu().clone() for t in (examples.initial_values, examples.operations, examples.operands))
    b = ((a[0] + 1) % (cfg.max_initial + 1), 1 - a[1],
         (a[2] + 1) % (cfg.max_operand + 1))
    for data in (a, b):
        models['dense_checked']._validate(*data)
    oracle = fixture['models']['dense' if kind == 'dense' else 'compact'].eval()
    references = [oracle(*data).detach().clone() for data in (a, b)]
    if torch.allclose(references[0], references[1], rtol=1e-4, atol=1e-5):
        raise RuntimeError('Reference must change for input B')
    before = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}
    if any(t.is_floating_point() and not bool(torch.isfinite(t).all()) for t in before.values()):
        raise ValueError('Non-finite model state')
    archive = io.BytesIO()
    torch.save(model.state_dict(), archive)
    details = {
        'state_dict_archive_bytes': len(archive.getbuffer()),
        'cpu_model_tensors': tensor_accounting(list(model.parameters()) + list(model.buffers())),
        'correction_nnz_per_module_by_role': counts, 'seed': fixture['seed'],
        'width': cfg.width, 'validation_batch': examples.size,
        'core_calls_per_forward': 2 * cfg.operation_steps,
        'expected_score': fixture['scores']['dense' if kind == 'dense' else 'compact'],
        'c35_source_sha256': file_hash(c35.__file__),
    }
    return model, (a, b), references, examples.targets.cpu(), before, details


@torch.inference_mode()
def run_worker(fixture_path, variant):
    if variant not in VARIANTS:
        raise ValueError('Unknown variant')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is required')
    if os.environ.get('PYTORCH_NO_CUDA_MEMORY_CACHING') not in (None, '', '0'):
        raise RuntimeError('CUDA caching allocator must be enabled')
    from fold_lm.v05_benchmarks import gate_c_full_model_validation_boundary as c35
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision('highest')
    kind, mode = variant.split('_')
    print(f'[C38] {variant}: preparing CPU model/reference', file=sys.stderr, flush=True)
    model, batches, refs, targets, before, details = prepare_cpu(fixture_path, kind)
    gc.collect()
    torch.cuda.init()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    phases = {'baseline': snapshot()}
    if phases['baseline']['allocated_bytes'] != 0:
        raise RuntimeError('Unexpected live CUDA tensors before selected-model transfer')
    model = model.cuda().eval()  # No other comparison model ever moves to CUDA.
    phases['model_loaded'] = snapshot()
    model_bytes = tensor_accounting(list(model.parameters()) + list(model.buffers()))
    inputs = tuple(t.cuda() for t in batches[0])
    phases['inputs_ready'] = snapshot()
    side = torch.cuda.Stream()
    side.wait_stream(torch.cuda.current_stream())
    print(f'[C38] {variant}: warmup', file=sys.stderr, flush=True)
    with torch.cuda.stream(side):
        for _ in range(10):
            temp = model(*inputs)
            del temp
    torch.cuda.current_stream().wait_stream(side)
    phases['warmup'] = snapshot()
    graph, graph_output = None, None
    if mode == 'graph':
        print(f'[C38] {variant}: capture', file=sys.stderr, flush=True)
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=side):
            graph_output = model(*inputs)
        graph.replay()
    phases['ready'] = snapshot()
    # Reset only the peak counters, not the cache or live graph, for steady requests.
    torch.cuda.reset_peak_memory_stats()
    gaps = {'A': 0.0, 'B': 0.0}
    scores = []
    print(f'[C38] {variant}: 20 A/B requests and final A', file=sys.stderr, flush=True)
    for i in [j % 2 for j in range(20)] + [0]:
        for dst, src in zip(inputs, batches[i]):
            dst.copy_(src, non_blocking=False)
        if graph is not None:
            graph.replay()
            output = graph_output
        else:
            output = model(*inputs)
        cpu_output = output.cpu()  # CPU oracle checks cannot allocate extra GPU tensors.
        if not bool(torch.isfinite(cpu_output).all()):
            raise RuntimeError('Non-finite output')
        torch.testing.assert_close(cpu_output, refs[i], rtol=1e-4, atol=1e-5)
        key = 'A' if i == 0 else 'B'
        gaps[key] = max(gaps[key], float((cpu_output - refs[i]).abs().max()))
        if i == 0:
            score = c35.trajectory_score(cpu_output, targets, model.config.state_scale)
            if abs(score - details['expected_score']) > 1e-7:
                raise RuntimeError('Fixture score changed')
            scores.append(score)
        del output
    # Retain exactly one last output for BOTH eager and graph idle snapshots.
    if graph is None:
        last_output = model(*inputs)
    else:
        last_output = graph_output
    phases['steady_with_output'] = snapshot()
    last_cpu = last_output.cpu()
    torch.testing.assert_close(last_cpu, refs[0], rtol=1e-4, atol=1e-5)
    torch.cuda.empty_cache()  # Deliberate diagnostic trim, outside normal request execution.
    phases['retained_after_cache_trim'] = snapshot()
    for key, tensor in model.state_dict().items():
        if not torch.equal(tensor.cpu(), before[key]):
            raise RuntimeError('Model state changed: ' + key)
    steady, trimmed = phases['steady_with_output'], phases['retained_after_cache_trim']
    accounting = {
        'model_unique_storage_bytes': model_bytes['unique_storage_bytes'],
        'state_dict_archive_bytes': details['state_dict_archive_bytes'],
        'idle_allocated_bytes': steady['allocated_bytes'],
        'idle_reserved_bytes': steady['reserved_bytes'],
        'steady_peak_allocated_bytes': steady['peak_allocated_bytes'],
        'steady_peak_reserved_bytes': steady['peak_reserved_bytes'],
        'setup_peak_allocated_bytes': phases['ready']['peak_allocated_bytes'],
        'setup_peak_reserved_bytes': phases['ready']['peak_reserved_bytes'],
        'retained_after_trim_allocated_bytes': trimmed['allocated_bytes'],
        'retained_after_trim_reserved_bytes': trimmed['reserved_bytes'],
    }
    return {
        'variant': variant, 'pid': os.getpid(), 'fixture_sha256': FIXTURE_SHA,
        'device_name': torch.cuda.get_device_name(0), 'torch_version': str(torch.__version__),
        'cuda_version': torch.version.cuda, 'allocator_backend': torch.cuda.get_allocator_backend(),
        'allocator_config': {k: os.environ.get(k) for k in ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF')},
        'float32_matmul_precision': 'highest', 'details': details,
        'input_tensors': tensor_accounting(inputs), 'model_tensors': model_bytes,
        'output_tensors': tensor_accounting((last_output,)), 'phases': phases,
        'accounting': accounting, 'max_abs_cpu_reference_gap': gaps,
        'score_A': scores[-1], 'parity_passed': True, 'model_state_unchanged': True,
    }


def preserve_c37(result, previous):
    """Keep C37 raw records in the same fixed JSON without nesting repeated C38 runs."""
    if previous is None:
        retained = None
    elif previous.get('experiment_id') == 'C37-request-cost':
        retained = previous
    elif previous.get('experiment_id') == 'C38-memory':
        retained = previous.get('retained_C37_result')
    else:
        raise ValueError('Output contains another experiment; refusing to discard it')
    if retained is not None and retained.get('experiment_id') != 'C37-request-cost':
        raise ValueError('Invalid retained C37 result')
    return dict(result, retained_C37_result=retained, C37_result_retained=retained is not None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--output')
    parser.add_argument('--worker', choices=VARIANTS)
    args = parser.parse_args(argv)
    fixture = str(Path(args.fixture).resolve())
    if args.worker:
        print(PREFIX + json.dumps(run_worker(fixture, args.worker), allow_nan=False))
        return 0
    if not args.output:
        parser.error('--output is required for the parent runner')
    output = Path(args.output).resolve()
    previous = json.loads(output.read_text(encoding='utf-8-sig')) if output.exists() else None
    preserve_c37({}, previous)  # Reject an unrelated result before any workers run.
    started, workers = time.perf_counter(), []
    root = Path(__file__).resolve().parents[2]
    for index, variant in enumerate(VARIANTS, 1):
        print(f'[C38] {index}/4 {variant}: new worker process', flush=True)
        cmd = [sys.executable, '-u', '-m', 'fold_lm.v05_benchmarks.gate_c_graph_memory_accounting',
               '--fixture', fixture, '--worker', variant]
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=300)
        if proc.stderr:
            print(proc.stderr.rstrip(), flush=True)
        if proc.returncode:
            print(proc.stdout, flush=True)
            raise RuntimeError(f'{variant} worker failed: {proc.returncode}')
        payloads = [line[len(PREFIX):] for line in proc.stdout.splitlines() if line.startswith(PREFIX)]
        if len(payloads) != 1:
            raise RuntimeError('Expected one worker result')
        worker = json.loads(payloads[0])
        if worker.get('variant') != variant:
            raise ValueError('Worker identity mismatch')
        workers.append(worker)
        print(f'[C38] {index}/4 {variant}: PASS elapsed={time.perf_counter()-started:.1f}s', flush=True)
    summary = summarize(workers)
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True,
                                         stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    result = {
        'schema': 'fold-c38-isolated-graph-memory-v1', 'experiment_id': 'C38-memory', 'stage': 'V5-C',
        'commit_sha': commit, 'benchmark_source_sha256': file_hash(__file__),
        'fixture_sha256': FIXTURE_SHA, 'fresh_worker_per_variant': True,
        'summary': summary, 'workers': workers, 'elapsed_seconds': time.perf_counter()-started,
        'diagnostic_only': True, 'gate_c_candidate': False, 'production_runtime_modified': False,
        'retrained': False, 'performance_benchmark': False,
        'known_deviations': [
            'PyTorch allocator counters exclude CUDA context/driver/non-PyTorch allocations; NOT total VRAM',
            'Only one selected model on GPU during accounting; all oracles and targets stay on CPU',
            'C35 boundary policy, fixed 216-example composition fixture, original E-capable kernel',
            'One process run per variant, not a scaling experiment or statistical memory confidence interval',
            'Setup includes warmup and capture; steady peaks reset after setup; no peak counters are added together',
            'Idle snapshots retain model/static inputs/one output; graph variant also retains its private pool',
            'After-trim snapshot explicitly calls empty_cache; it is not normal request-time behavior',
            'torch.save state_dict archive size is diagnostic, not the canonical compressed serializer/model package',
            'CPU RAM/driver memory/timing and new task quality are not measured',
        ],
    }
    result = preserve_c37(result, previous)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, output)
    print(json.dumps({k: v for k, v in result.items() if k not in ('workers', 'retained_C37_result')}, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
