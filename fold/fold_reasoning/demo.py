"""Reproducible synthetic tasks; names/signatures are supplied, not learned."""
from __future__ import annotations
from dataclasses import asdict
import json
import platform
import time
import numpy as np
import torch
from .core import Budget, CapsuleTask, Operation, Reasoner
from .index import Record, StructuralIndex


def example(*, shift=2.0, device="cpu", revision="0", scope="demo"):
    dtype = torch.float64
    n = 6
    A = torch.eye(n, dtype=dtype, device=device)
    for i in range(1, n):
        A[i, i - 1] = -1
    target = torch.ones(n, dtype=dtype, device=device)
    target[0] = 0
    J, eta = A.mT @ A, A.mT @ target
    U = torch.eye(n, dtype=dtype, device=device)[:, :2]
    Q = torch.eye(n, dtype=dtype, device=device)[-2:]
    goal = (Q @ torch.linalg.solve(J, eta)) + shift
    task = CapsuleTask(J, eta, Q, U, goal, structure=(1, 0, 0, 0),
                       semantics=(1, 0), revision=revision, scope=scope)
    ops = [Operation("delay_origin", 0, 1), Operation("advance_origin", 0, -1),
           Operation("alter_second", 1, 0.5), Operation("unsafe_precision", 0, 0, -100)]
    records = [
        Record("rhythm-phase", "rhythm", "additive-chain-v1", (1, 0, 0, 0), (0, 1),
               ("delay_origin", "advance_origin")),
        Record("factory-line", "factory", "additive-chain-v1", (1, 0, 0, 0), (1, 0),
               ("alter_second",)),
        Record("wrong-mechanism", "factory", "queue-v1", (1, 0, 0, 0), (1, 0),
               ("unsafe_precision",)),
        Record("irrelevant", "random", "additive-chain-v1", (0, 1, 0, 0), (-1, 0),
               ("unsafe_precision",)),
    ]
    return task, StructuralIndex(records), ops


def demo(preset="normal", device="cpu"):
    start = time.perf_counter()
    task, index, operations = example(device=device)
    reasoner = Reasoner(index, operations, budget=Budget.preset(preset))
    cold = reasoner.solve(task)
    warm = reasoner.solve(task)
    direct_task, _, _ = example(shift=0, device=device)
    direct = reasoner.solve(direct_task)
    if device == "cuda":
        torch.cuda.synchronize()
    return {"kind": "synthetic_scheduler_demo", "learned_reasoning": False,
            "includes_setup_seconds": time.perf_counter() - start,
            "budget": asdict(reasoner.budget), "cold": cold, "warm": warm, "direct": direct,
            "note": "Separate from fold_lm; signatures/operators are hand-specified. No speed claim."}


def benchmark(trials=20, device="cpu"):
    if type(trials) is not int or not 1 <= trials <= 10000:
        raise ValueError("trials must be in [1, 10000]")
    torch.set_num_threads(1)
    # Warm up both paths before timing. Synchronize CUDA for honest wall time.
    demo(device=device)
    task, index, operations = example(device=device)
    engine = Reasoner(index, operations)
    branches = [task.root().extend(operations[i % 3]) for i in range(16)]
    batch_times, serial_times, errors = [], [], []
    def sync():
        if device == "cuda":
            torch.cuda.synchronize()
    for i in range(trials):
        results = {}
        order = ("batch", "serial") if i % 2 == 0 else ("serial", "batch")
        for mode in order:
            sync()
            start = time.perf_counter()
            if mode == "batch":
                values, _ = task.evaluate(branches)
            else:
                values = [task.evaluate([b])[0][0] for b in branches]
            sync()
            (batch_times if mode == "batch" else serial_times).append(time.perf_counter() - start)
            results[mode] = values
        errors.append(max(float((a - b).abs().max()) for a, b in zip(results["batch"], results["serial"])))
    search = engine.solve(task)
    reused = engine.solve(task)
    _, approx = index.search(task.structure, task.semantics, schema=task.schema)
    hits_a, _ = index.search(task.structure, task.semantics, schema=task.schema)
    hits_e, exact = index.search(task.structure, task.semantics, schema=task.schema, exact=True)
    expected = {h.record.key for h in hits_e}
    recall = len(expected & {h.record.key for h in hits_a}) / len(expected) if expected else None
    def timing(times):
        return {"median_seconds": float(np.median(times)), "p95_seconds": float(np.quantile(times, .95))}
    return {"kind": "synthetic_microbenchmark", "trials": trials,
            "environment": {"python": platform.python_version(), "torch": str(torch.__version__),
                            "numpy": np.__version__, "device": device, "cpu_threads": 1},
            "batch": timing(batch_times), "serial": timing(serial_times),
            "max_abs_error": max(errors), "branch_count": len(branches),
            "search": search, "reused": reused,
            "retrieval": {"approximate": approx, "exact": exact, "recall_on_four_records": recall},
            "numeric_payload": {"shared_capsule_bytes": sum(t.numel() * t.element_size()
                                    for t in vars(task.capsule).values()),
                                "branch_delta_bytes": sum((b.W.numel() + b.b.numel()) * b.W.element_size()
                                                           for b in branches),
                                "index_array_bytes": index.numeric_bytes()},
            "limitations": ["Not an LLM creativity/latency benchmark.",
                            "Tiny supplied signatures do not establish ANN recall at scale.",
                            "Timing excludes one-time capsule/index compilation; demo includes setup separately.",
                            "Numeric payload excludes retained base matrices, validation factorization, candidate tensors, Python and allocator overhead.",
                            "Program replay is not neural distillation or automatic program abstraction."]}


def write_report(report, path):
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    return text
