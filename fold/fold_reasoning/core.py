"""Finite-budget hypothesis search over explicit FOLD-R port operations.

This is a deterministic reference scheduler. It consumes supplied structural
signatures and operations, not raw language; it does not claim learned latent
reasoning. The base capsule is shared; each hypothesis owns only W/b deltas.
"""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import time
import numpy as np
import torch
from fold_lm.capsule import compile_capsule
from .index import StructuralIndex


@dataclass(frozen=True)
class Budget:
    retrieve: int = 8
    frontier: int = 4
    depth: int = 3
    expansions: int = 64
    verifications: int = 32
    index_scan: int = 128
    probes: int = 2
    cache_entries: int = 32

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"budget.{name} must be a positive integer")
        if self.frontier > self.expansions:
            raise ValueError("frontier cannot exceed expansion budget")

    @classmethod
    def preset(cls, name):
        options = {"fast": dict(retrieve=2, frontier=1, depth=1, expansions=4, verifications=5),
                   "normal": {},
                   "deep": dict(retrieve=16, frontier=8, depth=6, expansions=256, verifications=128)}
        if name not in options:
            raise ValueError("unknown budget preset")
        return cls(**options[name])


@dataclass(frozen=True)
class Operation:
    key: str
    port: int
    eta_delta: float = 0.0
    precision_delta: float = 0.0

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key or type(self.port) is not int or self.port < 0:
            raise ValueError("invalid operation identifier/port")
        if not all(math.isfinite(x) for x in (self.eta_delta, self.precision_delta)):
            raise ValueError("operation deltas must be finite")


@dataclass
class Branch:
    path: tuple[str, ...]
    W: torch.Tensor
    b: torch.Tensor

    def extend(self, op: Operation):
        if op.port >= self.b.shape[-1]:
            raise ValueError("OUT_OF_SCOPE")
        W, b = self.W.clone(), self.b.clone()
        W[op.port, op.port] += op.precision_delta
        b[op.port] += op.eta_delta
        return Branch(self.path + (op.key,), W, b)

    def signature(self):
        # CPU reference scheduler: this synchronization is counted in latency.
        return self.W.detach().cpu().numpy().tobytes() + self.b.detach().cpu().numpy().tobytes()


class CapsuleTask:
    """Explicit numeric target task, scoped to fixed Q/U. No raw-text parser.

    Target is a declared design goal, not a hidden answer passed to a learner.
    Cloned base tensors must not be mutated during a solve. Search never commits
    a hypothetical update to the base or to the LM's persistent state.
    """
    def __init__(self, J, eta, Q, U, target, *, structure, semantics,
                 scope="demo", revision="0", schema="additive-chain-v1", tolerance=1e-8):
        self.J, self.eta, self.Q, self.U = (x.detach().clone() for x in (J, eta, Q, U))
        if self.J.ndim != 2 or self.eta.ndim != 1 or self.Q.ndim != 2 or self.U.ndim != 2:
            raise ValueError("one unbatched base task required")
        if not 1 <= self.J.shape[-1] <= 256 or not 1 <= self.U.shape[-1] <= 32 or not 1 <= self.Q.shape[0] <= 32:
            raise ValueError("reference task limits: 1..256 variables and 1..32 read/update ports")
        if not all(isinstance(x, str) and x for x in (scope, revision, schema)):
            raise ValueError("scope/revision/schema must be nonempty")
        self.target = torch.as_tensor(target, dtype=J.dtype, device=J.device).clone()
        if self.target.shape != (Q.shape[0],) or not torch.isfinite(self.target).all():
            raise ValueError("invalid target")
        if not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError("tolerance must be positive")
        self.structure, self.semantics = tuple(structure), tuple(semantics)
        self.scope, self.revision, self.schema = scope, revision, schema
        self.tolerance = tolerance
        self.capsule = compile_capsule(self.J, self.eta, self.Q, self.U)
        self.rank = U.shape[-1]
        self._K_lower = torch.linalg.cholesky(self.capsule.K)

    def root(self):
        return Branch((), self.J.new_zeros(self.rank, self.rank), self.J.new_zeros(self.rank))

    def binding(self):
        # No answer cache: target is deliberately omitted, then re-verified.
        h = hashlib.sha256(json.dumps([self.scope, self.revision, self.schema]).encode())
        for tensor in (self.J, self.eta, self.Q, self.U):
            a = tensor.detach().cpu().numpy()
            h.update(str((a.shape, a.dtype)).encode())
            h.update(a.tobytes())
        return h.hexdigest()

    @torch.inference_mode()
    def evaluate(self, branches):
        """One batched response; unsafe branches are excluded independently."""
        if not branches:
            return [], []
        W, b = torch.stack([x.W for x in branches]), torch.stack([x.b for x in branches])
        if W.shape[1:] != (self.rank, self.rank) or b.shape[1:] != (self.rank,):
            raise ValueError("OUT_OF_SCOPE")
        finite = torch.isfinite(W).all((-1, -2)) & torch.isfinite(b).all(-1)
        symmetric = (W - W.mT).abs().amax((-1, -2)) <= 1e-10
        # Replace invalid rows solely for validation, never report them as valid.
        safe_W = torch.where((finite & symmetric)[:, None, None], W, torch.zeros_like(W))
        I = torch.eye(self.rank, dtype=W.dtype, device=W.device)
        _, info = torch.linalg.cholesky_ex(I + self._K_lower.mT @ safe_W @ self._K_lower)
        valid = finite & symmetric & (info == 0)
        ids = valid.nonzero(as_tuple=False).flatten()
        values = [None] * len(branches)
        statuses = ["NUMERIC_UNSAFE"] * len(branches)
        if ids.numel():
            output = self.capsule.response(W[ids], b[ids], check=False)
            for i, value in zip(ids.tolist(), output):
                if torch.isfinite(value).all():
                    values[i] = value
                    statuses[i] = "SUPPORTED"
        return values, statuses


class ProgramCache:
    """Bounded in-memory LRU of operator IDs, never executable Python or answers."""
    def __init__(self, capacity=32):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("positive cache capacity required")
        self.capacity, self.entries = capacity, OrderedDict()

    def get(self, key):
        value = self.entries.get(key)
        if value is not None:
            self.entries.move_to_end(key)
        return value

    def put(self, key, program):
        self.entries[key] = tuple(program)
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)

    def discard(self, key):
        self.entries.pop(key, None)


class Reasoner:
    def __init__(self, index: StructuralIndex, operations, *, budget=None):
        self.index = index
        supplied = tuple(operations)
        self.ops = {o.key: o for o in supplied}
        if not supplied or len(self.ops) != len(supplied):
            raise ValueError("nonempty, unique operations required")
        self.budget = budget or Budget()
        self.cache = ProgramCache(self.budget.cache_entries)
        raw = [asdict(o) for o in supplied]
        self.operator_version = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()

    def solve(self, task: CapsuleTask, *, use_cache=True, exact_index=False):
        budget = self.budget
        started = time.perf_counter()
        stats = {"expansions": 0, "verified_candidates": 0, "solve_batches": 0,
                 "cheap_rejected": 0, "duplicates": 0, "cache_rejected": 0,
                 "max_frontier": 1, "depth_reached": 0, "cache_entries": len(self.cache.entries),
                 "index": None, "retrieved": []}
        numerical_failures = 0
        best_error, best_path = None, ()

        def finish(status, route, branch=None, value=None):
            if task.J.device.type == "cuda":
                torch.cuda.synchronize(task.J.device)
            stats["seconds"] = time.perf_counter() - started
            stats["cache_entries"] = len(self.cache.entries)
            return {"status": status, "route": route, "program": list(branch.path) if branch else [],
                    "value": value.detach().cpu().tolist() if value is not None else None,
                    "best_error": best_error, "best_program": list(best_path), "metrics": stats}

        def verify(branches):
            nonlocal best_error, best_path, numerical_failures
            available = budget.verifications - stats["verified_candidates"]
            branches = branches[:available]
            if not branches:
                return [], None
            stats["verified_candidates"] += len(branches)
            stats["solve_batches"] += 1
            values, states = task.evaluate(branches)
            scored, winner = [], None
            for branch, value, state in zip(branches, values, states):
                if state != "SUPPORTED":
                    numerical_failures += 1
                    continue
                error = float((value - task.target).abs().max())
                if best_error is None or error < best_error:
                    best_error, best_path = error, branch.path
                scored.append((error, branch))
                if error <= task.tolerance and winner is None:
                    winner = (branch, value)
            return scored, winner

        root = task.root()
        _, winner = verify([root])
        if winner:
            return finish("SOLVED", "direct", *winner)
        key = (task.binding(), self.operator_version, self.index.fingerprint)
        if use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                if (len(cached) <= budget.depth and len(cached) <= budget.expansions
                        and stats["verified_candidates"] < budget.verifications):
                    branch = root
                    valid = True
                    for op_id in cached:
                        stats["expansions"] += 1
                        if op_id not in self.ops or self.ops[op_id].port >= task.rank:
                            valid = False
                            break
                        branch = branch.extend(self.ops[op_id])
                    if valid:
                        _, winner = verify([branch])
                        if winner:
                            return finish("SOLVED", "validated_program", *winner)
                stats["cache_rejected"] += 1
                self.cache.discard(key)
        hits, index_stats = self.index.search(
            task.structure, task.semantics, schema=task.schema,
            k=budget.retrieve, scan_limit=budget.index_scan, probes=budget.probes,
            exact=exact_index)
        stats["index"] = index_stats
        stats["retrieved"] = [h.record.key for h in hits]
        selected = []
        for hit in hits:
            for name in hit.record.operations:
                if name not in self.ops or self.ops[name].port >= task.rank:
                    stats["cheap_rejected"] += 1
                elif name not in selected:
                    selected.append(name)
        if not selected:
            return finish("OUT_OF_SCOPE", "search")
        frontier, seen = [root], {root.signature()}
        for depth in range(1, budget.depth + 1):
            stats["depth_reached"] = depth
            candidates = []
            remaining = budget.verifications - stats["verified_candidates"]
            if remaining <= 0:
                break
            for parent in frontier:
                for name in selected:
                    if stats["expansions"] >= budget.expansions or len(candidates) >= remaining:
                        break
                    stats["expansions"] += 1
                    child = parent.extend(self.ops[name])
                    signature = child.signature()
                    if signature in seen:
                        stats["duplicates"] += 1
                        continue
                    seen.add(signature)
                    candidates.append(child)
                if stats["expansions"] >= budget.expansions or len(candidates) >= remaining:
                    break
            if not candidates:
                break
            scored, winner = verify(candidates)
            if winner:
                if use_cache:
                    self.cache.put(key, winner[0].path)
                return finish("SOLVED", "search", *winner)
            scored.sort(key=lambda x: (x[0], x[1].path))
            # Retain distinct states; mechanism-level diversity is future work.
            frontier = [b for _, b in scored[:budget.frontier]]
            stats["max_frontier"] = max(stats["max_frontier"], len(frontier))
            if not frontier or stats["expansions"] >= budget.expansions:
                break
        stats["numeric_rejected"] = numerical_failures
        return finish("BUDGET_EXHAUSTED", "search")
