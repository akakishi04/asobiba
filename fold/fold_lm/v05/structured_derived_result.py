"""Bounded derived-claim verifier; not an answer solver or evidence writer.

Only checks an explicitly supplied proof against a trusted current TaskView.
Unknown/stale/conflicting values are never filled in. No model or IO is used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from . import structured_task_input as inp

SCHEMA = "fold-structured-derived-result-v1"
RULES = ("OBSERVED_LEAF", "AND_BOTH", "OR_BOTH", "AND_LEFT_ZERO",
         "AND_RIGHT_ZERO", "OR_LEFT_ONE", "OR_RIGHT_ONE")
MAX_PROOF_STEPS = 7


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def expression_digest(view: inp.TaskView) -> str:
    """Order and fact identity are significant; no algebraic simplification."""
    return _digest(dict(nodes=[asdict(n) for n in view.nodes],
                        fact_ids=[f.fact_id for f in view.facts]))


def evidence_digest(view: inp.TaskView) -> str:
    """Conservative binding to ALL current fact views, not just claimed support.

    Resource counters are intentionally excluded; this is not authorization.
    """
    return _digest(dict(evidence_time=view.evidence_time, revision=view.revision,
                        facts=[asdict(f) for f in view.facts]))


@dataclass(frozen=True)
class Support:
    fact_index: int
    reference_id: str


@dataclass(frozen=True)
class ProofStep:
    node_index: int
    value: int
    rule: str
    premises: tuple[int, ...] = ()  # AST node indices, not proof-array offsets.


@dataclass(frozen=True)
class DerivedCandidate:
    schema: str
    request_id: str
    scope_id: str
    expression_sha256: str
    evidence_sha256: str
    evidence_time: int
    revision: int
    value: int
    supporting_references: tuple[Support, ...]
    proof: tuple[ProofStep, ...]


@dataclass(frozen=True)
class DerivedResult:
    schema: str
    request_id: str
    scope_id: str
    expression_sha256: str
    evidence_sha256: str
    evidence_time: int
    revision: int
    status: str
    reason: str
    derivation_kind: str = "BOOLEAN_LOCAL_PROOF"
    value: int | None = None
    supporting_references: tuple[Support, ...] = ()
    proof: tuple[ProofStep, ...] = ()
    checked_steps: int = 0


def bind_candidate(view: inp.TaskView, value: int, proof: tuple[ProofStep, ...],
                   supporting_references: tuple[Support, ...]) -> DerivedCandidate:
    """Bind a PROPOSED value/proof, without computing or validating its conclusion."""
    return DerivedCandidate(SCHEMA, view.request_id, view.scope_id,
        expression_digest(view), evidence_digest(view), view.evidence_time, view.revision,
        value, supporting_references, proof)


def _int(value, low, high) -> bool:
    return type(value) is int and low <= value <= high


def verify(view: inp.TaskView, candidate: object, *, max_steps: int = MAX_PROOF_STEPS) -> DerivedResult:
    """Fail closed without repairing claims. No expected answer/necessity interface.

    The caller owns current-view authentication and concurrent version checks.
    max_steps bounds rule evaluations, not IO or a claim of zero verification cost.
    REJECTED is not a learned abstention or proof that the task is unanswerable.
    """
    if type(view) is not inp.TaskView:
        raise TypeError("A trusted current TaskView is required")
    # Validate trusted configuration separately from untrusted candidate rejection.
    if inp.decode(inp.encode(view)) != view:
        raise ValueError("Invalid trusted view")
    if not _int(max_steps, 0, MAX_PROOF_STEPS):
        raise ValueError("Invalid verification capacity")
    ex, ev = expression_digest(view), evidence_digest(view)
    checked = 0
    def reject(reason):
        return DerivedResult(SCHEMA, view.request_id, view.scope_id, ex, ev,
            view.evidence_time, view.revision, "REJECTED", reason, checked_steps=checked)
    if type(candidate) is not DerivedCandidate or candidate.schema != SCHEMA:
        return reject("MALFORMED_CANDIDATE")
    c = candidate
    if (type(c.request_id) is not str or type(c.scope_id) is not str
            or (c.request_id, c.scope_id) != (view.request_id, view.scope_id)):
        return reject("REQUEST_SCOPE_MISMATCH")
    if (not _int(c.evidence_time, 0, inp.MAX_INTEGER)
            or not _int(c.revision, 0, inp.MAX_INTEGER)
            or (c.evidence_time, c.revision) != (view.evidence_time, view.revision)):
        return reject("CLOCK_MISMATCH")
    if type(c.expression_sha256) is not str or c.expression_sha256 != ex:
        return reject("EXPRESSION_MISMATCH")
    if type(c.evidence_sha256) is not str or c.evidence_sha256 != ev:
        return reject("EVIDENCE_MISMATCH")
    if not _int(c.value, 0, 1):
        return reject("INVALID_VALUE")
    if type(c.proof) is not tuple or not 1 <= len(c.proof) <= MAX_PROOF_STEPS:
        return reject("MALFORMED_PROOF")
    if len(c.proof) > max_steps:
        return reject("VERIFICATION_BUDGET_EXHAUSTED")
    if type(c.supporting_references) is not tuple or len(c.supporting_references) > inp.MAX_FACTS:
        return reject("MALFORMED_SUPPORT")
    support = {}
    for s in c.supporting_references:
        if (type(s) is not Support or not _int(s.fact_index, 0, len(view.facts)-1)
                or type(s.reference_id) is not str or not s.reference_id.strip()
                or s.fact_index in support):
            return reject("MALFORMED_SUPPORT")
        f = view.facts[s.fact_index]
        if f.status != "OBSERVED" or f.reference_ids != (s.reference_id,):
            return reject("SUPPORT_NOT_USABLE")
        support[s.fact_index] = s.reference_id
    if list(support) != sorted(support):
        return reject("NONCANONICAL_SUPPORT")
    proven = {}; ancestors = {}; used_facts = set(); previous = -1
    for step in c.proof:
        checked += 1
        if (type(step) is not ProofStep or not _int(step.node_index, 0, len(view.nodes)-1)
                or step.node_index <= previous or not _int(step.value, 0, 1)
                or type(step.rule) is not str or step.rule not in RULES
                or type(step.premises) is not tuple or len(step.premises) > 2
                or any(not _int(i, 0, step.node_index-1) for i in step.premises)
                or len(set(step.premises)) != len(step.premises)):
            return reject("MALFORMED_PROOF_STEP")
        previous = step.node_index
        n = view.nodes[step.node_index]
        if n.kind == "FACT":
            f = view.facts[n.fact]
            if step.rule != "OBSERVED_LEAF" or step.premises:
                return reject("RULE_MISMATCH")
            if f.status != "OBSERVED" or n.fact not in support:
                return reject("SUPPORT_NOT_USABLE")
            if step.value != (f.value ^ int(n.negate)):
                return reject("LEAF_VALUE_MISMATCH")
            used_facts.add(n.fact)
        else:
            both = step.rule == n.kind + "_BOTH"
            side = "LEFT" if "_LEFT_" in step.rule else "RIGHT"
            short_rule = n.kind + "_" + side + ("_ZERO" if n.kind == "AND" else "_ONE")
            want = (n.left, n.right) if both else ((n.left,) if side == "LEFT" else (n.right,))
            if (not both and step.rule != short_rule) or step.premises != want:
                return reject("RULE_MISMATCH")
            if any(i not in proven for i in want):
                return reject("UNPROVEN_PREMISE")
            if both:
                value = (proven[n.left] & proven[n.right]) if n.kind == "AND" else (proven[n.left] | proven[n.right])
            else:
                value = 0 if n.kind == "AND" else 1
                if proven[want[0]] != value:
                    return reject("NONCONTROLLING_PREMISE")
            if step.value != value:
                return reject("DERIVATION_VALUE_MISMATCH")
        proven[step.node_index] = step.value
        ancestors[step.node_index] = {step.node_index}.union(
            *(ancestors[i] for i in step.premises))
    root = len(view.nodes)-1
    if previous != root or proven[root] != c.value:
        return reject("CONCLUSION_MISMATCH")
    if ancestors[root] != set(proven):
        return reject("UNUSED_PROOF_STEP")
    if used_facts != set(support):
        return reject("UNUSED_SUPPORT")
    return DerivedResult(SCHEMA, view.request_id, view.scope_id, ex, ev,
        view.evidence_time, view.revision, "VERIFIED_DERIVED", "VALID_LOCAL_PROOF",
        value=c.value, supporting_references=c.supporting_references, proof=c.proof,
        checked_steps=checked)
