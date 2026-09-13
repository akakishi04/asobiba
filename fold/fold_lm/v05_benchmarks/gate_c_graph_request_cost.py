"""V5-C / C37: serial CPU-request cost; no production runtime changes.

Requires the existing C35 patch already installed locally. C35 is not yet
tracked on feat/sft-target-loss; accept only its measured LF/CRLF content hashes.
This runner fails rather than substituting an unknown boundary policy.

Run from fold/: python -m fold_lm.v05_benchmarks.gate_c_graph_request_cost
    <existing composition fixture> <result JSON>
CPU-ready A/B requests are strictly range-checked before copying into static
CUDA buffers; separately owned CPU outputs are finite-checked before returning.
No task labels enter the request callable. Kernel/weights/E remain unchanged.
This is not a production safety contract, Gate C pass, or live-traffic benchmark.
"""
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import torch

VARIANTS = ('dense_eager', 'triton_eager', 'dense_graph', 'triton_graph')
ROUNDS, REQUESTS, WARMUP = 8, 20, 10
SOURCE_HASHES = {
    '6c31c2aab5fbcf5dd6c04c2d929acce0ae5d04004bd0cb28610e3628b0d89573',  # CRLF
    '3edb16114882962b9e378c38a7dd6e84341c546b0d5aed1779e1a8c407c3caef',  # LF
}
FIXTURE_HASH = 'a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e'


def validate_request(data, spec, strict_validator):
    if not isinstance(data, tuple) or len(data) != len(spec):
        raise ValueError('Request must contain exactly three tensors')
    for tensor, (shape, dtype) in zip(data, spec):
        if (not isinstance(tensor, torch.Tensor) or tensor.device.type != 'cpu'
                or tuple(tensor.shape) != shape or tensor.dtype != dtype):
            raise ValueError('CPU input shape/dtype must match the captured contract')
    strict_validator(*data)  # Original input range checks, on CPU, inside timing.


def validate_output(out, shape):
    if (out.device.type != 'cpu' or tuple(out.shape) != shape
            or out.dtype != torch.float32 or not bool(torch.isfinite(out).all())):
        raise ValueError('Invalid or nonfinite CPU output')


def order_for_round(r):
    if type(r) is not int or r < 0:
        raise ValueError('Invalid round')
    offset = r % len(VARIANTS)
    return VARIANTS[offset:] + VARIANTS[:offset]


def summarize(records, rounds):
    if type(rounds) is not int or rounds <= 0:
        raise ValueError('Invalid rounds')
    table = {}
    for row in records:
        r, name, ms = row['round'], row['variant'], row['wall_ms']
        if (type(r) is not int or not 0 <= r < rounds or name not in VARIANTS
                or (r, name) in table or isinstance(ms, bool)
                or not math.isfinite(float(ms)) or ms <= 0):
            raise ValueError('Invalid/duplicate measurement')
        table[r, name] = float(ms)
    if set(table) != {(r, v) for r in range(rounds) for v in VARIANTS}:
        raise ValueError('Missing measurement')
    def stats(xs):
        return dict(median=statistics.median(xs), min=min(xs), max=max(xs))
    comparisons = {
        'dense_eager_to_graph_speedup': ('dense_eager', 'dense_graph'),
        'triton_eager_to_graph_speedup': ('triton_eager', 'triton_graph'),
        'triton_vs_dense_eager': ('triton_eager', 'dense_eager'),
        'triton_vs_dense_graph': ('triton_graph', 'dense_graph'),
    }
    return {
        'record_count': len(records),
        'wall_ms_per_request': {v: stats([table[r, v] for r in range(rounds)])
                                for v in VARIANTS},
        'paired_ratios': {k: stats([table[r, a] / table[r, b] for r in range(rounds)])
                          for k, (a, b) in comparisons.items()},
    }


@torch.inference_mode()
def main():
    from fold_lm.v05_benchmarks import gate_c_full_model_validation_boundary as c35
    from fold_lm.v05_benchmarks.gate_c_runtime_fixture import load_runtime_fixture
    from fold_lm.v05_benchmarks.gate_c_cuda_event_fixture_benchmark import _load_initializations

    if len(sys.argv) != 3:
        raise SystemExit('Usage: python -m fold_lm.v05_benchmarks.gate_c_graph_request_cost FIXTURE OUTPUT_JSON')
    fixture_path, result_path = map(Path, sys.argv[1:3])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    source_hash = c35._file_hash(c35.__file__)
    if source_hash not in SOURCE_HASHES:
        raise RuntimeError('C35 source changed; recheck before timing')
    if c35._file_hash(fixture_path) != FIXTURE_HASH:
        raise RuntimeError('The saved C35/C36 fixture changed')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable')
    if os.environ.get('CUDA_LAUNCH_BLOCKING') not in (None, '', '0'):
        raise RuntimeError('CUDA_LAUNCH_BLOCKING must be disabled')
    started = time.perf_counter()
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision('highest')

    print('[C37] loading unchanged fixture; no training', flush=True)
    fixture = load_runtime_fixture(fixture_path, device='cuda')
    if fixture['task'] != 'composition':
        raise ValueError('Only composition is supported')
    init = _load_initializations(str(fixture_path))
    models = c35.make_models(fixture['models']['dense'], init)
    cfg, examples = models['dense_checked'].config, fixture['validation']
    a = tuple(t.cpu().clone() for t in (
        examples.initial_values, examples.operations, examples.operands))
    b = ((a[0] + 1) % (cfg.max_initial + 1), 1 - a[1],
         (a[2] + 1) % (cfg.max_operand + 1))
    batches = (a, b)
    spec = tuple((tuple(t.shape), t.dtype) for t in a)
    output_shape = (examples.size, cfg.operation_steps + 1)
    strict = models['dense_checked']._validate
    e_counts = {role: [int(w.correction_nnz) for w in getattr(init, role).encoded_weights]
                for role in ('up', 'down')}
    if not all(n > 0 for ns in e_counts.values() for n in ns):
        raise ValueError('Expected correction E in every module')
    for data in batches:
        validate_request(data, spec, strict)

    calls, references, snapshots, scores, gaps, retained = {}, {}, {}, {}, {}, []
    for kind in ('dense', 'triton'):
        model, checked = models[kind + '_boundary'], models[kind + '_checked']
        snapshots[kind] = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        for i, data in enumerate(batches):
            references[kind, i] = checked(*(t.to('cuda') for t in data)).cpu()
        if torch.allclose(references[kind, 0], references[kind, 1], rtol=1e-4, atol=1e-5):
            raise RuntimeError('Input B must change the expected output')
        static = tuple(t.to('cuda') for t in a)
        side = torch.cuda.Stream()
        side.wait_stream(torch.cuda.current_stream())
        print(f'[C37] {kind}: warmup/capture', flush=True)
        with torch.cuda.stream(side):
            for _ in range(WARMUP):
                model(*static)
        torch.cuda.current_stream().wait_stream(side)
        torch.cuda.synchronize()
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=side):
            graph_output = model(*static)
        graph.replay()
        torch.cuda.synchronize()

        def make_request(use_graph, m=model, g=graph, x=static, y=graph_output):
            def request(data):
                validate_request(data, spec, strict)
                for dst, src in zip(x, data):
                    dst.copy_(src, non_blocking=False)
                if use_graph:
                    g.replay()
                    out = y
                else:
                    out = m(*x)
                result = out.cpu()  # Wait for GPU and return separately owned CPU output.
                validate_output(result, output_shape)
                return result
            return request

        calls[kind + '_eager'] = make_request(False)
        calls[kind + '_graph'] = make_request(True)
        retained.append((model, graph, side, static, graph_output))

    def check(name, i, out):
        kind = name.split('_')[0]
        torch.testing.assert_close(out, references[kind, i], rtol=1e-4, atol=1e-5)
        key = name + (':A' if i == 0 else ':B')
        gaps[key] = max(gaps.get(key, 0.0), float((out-references[kind, i]).abs().max()))
        if i == 0:
            score = c35.trajectory_score(out, examples.targets.cpu(), cfg.state_scale)
            if abs(score-fixture['scores']['dense' if kind == 'dense' else 'compact']) > 1e-7:
                raise RuntimeError('Fixture score changed')
            scores[name] = score

    for name in VARIANTS:
        for i in (0, 1, 0):
            out = calls[name](batches[i])
            check(name, i, out)
        for i in range(WARMUP):
            calls[name](batches[i % 2])

    records = []
    for r in range(ROUNDS):
        order = order_for_round(r)
        for name in order:
            torch.cuda.synchronize()  # Outside the request timer.
            t0 = time.perf_counter()
            outputs = [calls[name](batches[i % 2]) for i in range(REQUESTS)]
            wall_ms = (time.perf_counter()-t0)*1000.0 / REQUESTS
            # Ground-truth/parity comparisons are benchmark oracles, not request work.
            for i, out in enumerate(outputs):
                check(name, i % 2, out)
            records.append(dict(round=r, variant=name, order=list(order), wall_ms=wall_ms))
            elapsed = time.perf_counter()-started
            eta = elapsed/len(records)*(ROUNDS*len(VARIANTS)-len(records))
            print(f'[C37] {len(records)}/{ROUNDS*len(VARIANTS)} {name} '
                  f'request={wall_ms:.4f}ms elapsed={elapsed:.1f}s eta={eta:.1f}s', flush=True)
    for kind in ('dense', 'triton'):
        for k, v in models[kind + '_boundary'].state_dict().items():
            if not torch.equal(v.cpu(), snapshots[kind][k]):
                raise RuntimeError('Model state changed')
    result = {
        'schema': 'fold-c37-serial-cpu-request-v1', 'experiment_id': 'C37-request-cost',
        'stage': 'V5-C', 'fixture_sha256': FIXTURE_HASH, 'c35_source_sha256': source_hash,
        'benchmark_script_sha256': c35._file_hash(__file__), 'device_name': torch.cuda.get_device_name(0),
        'torch_version': str(torch.__version__), 'cuda_version': torch.version.cuda,
        'seed': fixture['seed'], 'width': cfg.width, 'validation_batch': examples.size,
        'core_calls_per_request': 2*cfg.operation_steps, 'rounds': ROUNDS,
        'requests_per_sample': REQUESTS, 'float32_matmul_precision': 'highest',
        'input_bytes_per_request': sum(t.numel()*t.element_size() for t in a),
        'output_bytes_per_request': examples.size*(cfg.operation_steps+1)*4,
        'correction_nnz_per_module_by_role': e_counts, 'fixture_scores_A': scores,
        'max_abs_gap_vs_checked': gaps, 'model_states_unchanged': True,
        'summary': summarize(records, ROUNDS), 'records': records,
        'elapsed_seconds': time.perf_counter()-started,
        'retrained': False, 'production_runtime_modified': False, 'gate_c_candidate': False,
        'known_deviations': [
            'Serial fixed-shape CPU requests, alternating prebuilt A/B; not real traffic',
            'Timed: CPU metadata/range checks, 3 blocking H2D copies, eager/replay, D2H output, CPU finite check',
            'Untimed: input creation, fixture load, capture, warmup, parity and task-score oracles',
            'Not the original per-operation validation contract; invalid intermediates can be missed',
            'Pageable CPU tensors, no copy/compute overlap or pinned-memory tuning',
            'Each request contains 216 examples only for the standard fixture; no tokens/s claim',
            'Graph/eager allocation and scheduling differ; no peak or total VRAM claim',
        ],
    }
    temp = result_path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, result_path)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
