"""Versioned, lossless bounded task input. No solver, policy or evidence writer.

A new consumer must explicitly opt in; legacy four-lane Controller input is not
silently widened or reinterpreted. Opaque binding IDs stay outside numeric data.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TypeVar

SCHEMA = "fold-structured-task-input-v1"
MAX_FACTS, MAX_NODES, MAX_INTEGER = 4, 7, 2**24 - 1
STATUSES = ("UNOBSERVED", "OBSERVED", "STALE", "CONFLICT", "INVALID",
            "SOURCE_UNBOUND", "SNAPSHOT_MISMATCH", "REFERENCE_MISMATCH")
OUTCOMES = ("NONE", "AUTHORIZED", "PERMISSION_DENIED", "BUDGET_EXHAUSTED",
            "MISSING_DELIVERY", "ATTEMPT_LIMIT", "INVALID_EVIDENCE")
TOOLS = ("RETRIEVE", "OBSERVE", "ASK_USER")
KINDS = ("FACT", "AND", "OR")
FEATURE_WIDTH = 72  # header4 + nodes7*6 + facts4*4 + runtime10
T = TypeVar("T")


def _integer(x, low=0, high=MAX_INTEGER):
    if type(x) is not int or not low <= x <= high:
        raise ValueError("Exact bounded integer required")
    return x


def _text(x):
    if type(x) is not str or not x.strip():
        raise ValueError("Nonempty string required")


def _tuple(x):
    if type(x) is not tuple:
        raise TypeError("Immutable tuple required")


@dataclass(frozen=True)
class Node:
    kind: str
    fact: int = -1
    left: int = -1
    right: int = -1
    negate: bool = False

    def __post_init__(self):
        if self.kind not in KINDS or type(self.negate) is not bool:
            raise ValueError("Invalid node kind/negation")
        for x in (self.fact, self.left, self.right):
            _integer(x, -1, MAX_NODES-1)
        if self.kind == "FACT":
            if not 0 <= self.fact < MAX_FACTS or self.left != -1 or self.right != -1:
                raise ValueError("Leaf must refer to one fact")
        elif self.fact != -1 or self.left < 0 or self.right < 0 or self.negate:
            raise ValueError("Binary node requires children; NOT applies only to leaves")


@dataclass(frozen=True)
class Fact:
    fact_id: str
    status: str = "UNOBSERVED"
    value: int | None = None
    reference_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _text(self.fact_id); _tuple(self.reference_ids)
        if self.status not in STATUSES:
            raise ValueError("Unregistered fact-read status")
        for x in self.reference_ids:
            _text(x)
        if len(self.reference_ids) > 2 or len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("At most two distinct support identities per fact")
        if self.status == "OBSERVED":
            _integer(self.value, 0, 1)
            if len(self.reference_ids) != 1:
                raise ValueError("Usable observation needs one binding identity")
        elif self.value is not None:
            raise ValueError("Unusable/missing fact must not carry a hidden or stale payload")
        if self.status == "UNOBSERVED" and self.reference_ids:
            raise ValueError("Unobserved fact cannot claim observed support")
        if self.status == "CONFLICT" and len(self.reference_ids) != 2:
            raise ValueError("Conflict must retain two competing support identities")


@dataclass(frozen=True)
class Resources:
    internal_remaining: int = 3
    acquisitions_remaining: int = 1
    available: tuple[bool, ...] = (True, False, False)
    permitted: tuple[bool, ...] = (True, False, False)
    last_outcome: str = "NONE"
    internal_step: int = 7

    def __post_init__(self):
        for x in (self.internal_remaining, self.acquisitions_remaining, self.internal_step):
            _integer(x)
        for mask in (self.available, self.permitted):
            _tuple(mask)
            if len(mask) != len(TOOLS) or any(type(x) is not bool for x in mask):
                raise ValueError("Three explicit Boolean tool flags required")
        if self.last_outcome not in OUTCOMES:
            raise ValueError("Unregistered runtime outcome")


@dataclass(frozen=True)
class TaskView:
    request_id: str
    scope_id: str
    nodes: tuple[Node, ...]
    facts: tuple[Fact, ...]
    resources: Resources = Resources()
    evidence_time: int = 1
    revision: int = 1

    def __post_init__(self):
        _text(self.request_id); _text(self.scope_id)
        if not self.request_id.startswith(self.scope_id + "|"):
            raise ValueError("Request/scope mismatch")
        _tuple(self.nodes); _tuple(self.facts)
        if not 1 <= len(self.nodes) <= MAX_NODES or not 1 <= len(self.facts) <= MAX_FACTS:
            raise ValueError("Bounded nonempty expression and fact table required")
        if any(type(n) is not Node for n in self.nodes) or any(type(f) is not Fact for f in self.facts):
            raise TypeError("Typed expression nodes and facts required")
        if type(self.resources) is not Resources:
            raise TypeError("Resources required")
        _integer(self.evidence_time); _integer(self.revision)
        if len({f.fact_id for f in self.facts}) != len(self.facts):
            raise ValueError("Duplicate fact identity")
        parents = [0] * len(self.nodes)
        operators = 0
        for i, node in enumerate(self.nodes):
            if node.kind == "FACT":
                if node.fact >= len(self.facts):
                    raise ValueError("Unknown fact index")
            else:
                operators += 1
                for child in (node.left, node.right):
                    if child >= i:
                        raise ValueError("Children must precede their parent")
                    parents[child] += 1
        if operators > 3 or parents != [1]*(len(parents)-1)+[0]:
            raise ValueError("One connected ordered tree required; no DAG, unused node or implicit pooling")


@dataclass(frozen=True)
class Binding:
    request_id: str
    scope_id: str
    fact_ids: tuple[str, ...]
    reference_ids: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class PolicyInput:
    schema: str
    features: tuple[int, ...]
    binding: Binding


def encode(view: TaskView) -> PolicyInput:
    """Copy visible fields, never evaluate the expression or infer dependency."""
    if type(view) is not TaskView:
        raise TypeError("TaskView required")
    x = [len(view.nodes), len(view.facts), view.evidence_time, view.revision]
    for i in range(MAX_NODES):
        if i >= len(view.nodes):
            x.extend([0]*6)
        else:
            n = view.nodes[i]
            x.extend((1, KINDS.index(n.kind)+1, n.fact+1, n.left+1, n.right+1, int(n.negate)))
    for i in range(MAX_FACTS):
        if i >= len(view.facts):
            x.extend([0]*4)
        else:
            f = view.facts[i]
            x.extend((1, STATUSES.index(f.status)+1, int(f.value is not None), f.value if f.value is not None else 0))
    r = view.resources
    x.extend((r.internal_remaining, r.acquisitions_remaining, *map(int, r.available),
              *map(int, r.permitted), OUTCOMES.index(r.last_outcome), r.internal_step))
    if len(x) != FEATURE_WIDTH:
        raise RuntimeError("Feature layout implementation mismatch")
    return PolicyInput(SCHEMA, tuple(x), Binding(view.request_id, view.scope_id,
        tuple(f.fact_id for f in view.facts), tuple(f.reference_ids for f in view.facts)))


def decode(packet: PolicyInput) -> TaskView:
    """Strict reference decoder; rejects noncanonical masks, padding and payloads."""
    if type(packet) is not PolicyInput or packet.schema != SCHEMA or type(packet.binding) is not Binding:
        raise ValueError("Explicit structured-v1 packet required")
    _tuple(packet.features)
    x, b = packet.features, packet.binding
    if len(x) != FEATURE_WIDTH:
        raise ValueError("Wrong feature width")
    for value in x:
        _integer(value)
    nn, nf, et, rev = x[:4]
    _integer(nn, 1, MAX_NODES); _integer(nf, 1, MAX_FACTS)
    _tuple(b.fact_ids); _tuple(b.reference_ids)
    if len(b.fact_ids) != nf or len(b.reference_ids) != nf:
        raise ValueError("Binding table length mismatch")
    nodes=[]
    for i in range(nn):
        _, kind, fact, left, right, neg = x[4+i*6:10+i*6]
        _integer(kind, 1, len(KINDS)); _integer(neg, 0, 1)
        nodes.append(Node(KINDS[kind-1], fact-1, left-1, right-1, bool(neg)))
    facts=[]
    for i in range(nf):
        _, status, present, value = x[46+i*4:50+i*4]
        _integer(status, 1, len(STATUSES)); _integer(present, 0, 1)
        facts.append(Fact(b.fact_ids[i], STATUSES[status-1], value if present else None, b.reference_ids[i]))
    ir, ar, *rest = x[62:]
    av, pe, out, step = rest[:3], rest[3:6], rest[6], rest[7]
    for v in av+pe:
        _integer(v, 0, 1)
    _integer(out, 0, len(OUTCOMES)-1)
    view=TaskView(b.request_id, b.scope_id, tuple(nodes), tuple(facts),
                  Resources(ir,ar,tuple(map(bool,av)),tuple(map(bool,pe)),OUTCOMES[out],step),et,rev)
    if encode(view) != packet:
        raise ValueError("Noncanonical masks/padding or disguised unknown payload")
    return view


def deliver(view: TaskView, consumer: Callable[[PolicyInput], T]) -> T:
    """Versioned consumption boundary, not a neural policy or automatic adapter."""
    if getattr(consumer, "input_schema", None) != SCHEMA:
        raise TypeError("Consumer must explicitly accept structured-v1; legacy four-lane reuse forbidden")
    return consumer(encode(view))
