"""Opt-in, sequential structured action boundary. No transport or evidence writer.

COMPUTE stages a supplied unverified candidate, not a hidden symbolic solver.
External actions reserve an intent, not a successful acquisition. The trusted owner
must adopt returned state and must reauthorize any later transport separately.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json

from . import structured_task_input as task
from . import structured_derived_result as proof

SCHEMA = "fold-structured-action-runtime-v1"
ACTIONS = ("ANSWER", "COMPUTE", "RETRIEVE", "OBSERVE", "ASK_USER", "STOP")


def _integer(value, low=0, high=task.MAX_INTEGER):
    return type(value) is int and low <= value <= high


def _text(value):
    return type(value) is str and bool(value.strip())


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def candidate_shape(c):
    """Immutable bounded wire shape only. Do NOT verify a conclusion while staging."""
    if type(c) is not proof.DerivedCandidate:
        return False
    if not all(_text(getattr(c, name)) for name in
               ("schema", "request_id", "scope_id", "expression_sha256", "evidence_sha256")):
        return False
    if not (_integer(c.evidence_time) and _integer(c.revision) and _integer(c.value, 0, 1)):
        return False
    if type(c.proof) is not tuple or len(c.proof) > proof.MAX_PROOF_STEPS:
        return False
    if type(c.supporting_references) is not tuple or len(c.supporting_references) > task.MAX_FACTS:
        return False
    for s in c.supporting_references:
        if type(s) is not proof.Support or not _integer(s.fact_index, 0, 3) or not _text(s.reference_id):
            return False
    for s in c.proof:
        if (type(s) is not proof.ProofStep or not _integer(s.node_index, 0, 6)
                or not _integer(s.value, 0, 1) or not _text(s.rule)
                or type(s.premises) is not tuple or len(s.premises) > 2
                or any(not _integer(i, 0, 6) for i in s.premises)):
            return False
    return True


@dataclass(frozen=True)
class AcquisitionIntent:
    intent_id: str
    request_id: str
    scope_id: str
    action: str
    fact_index: int
    fact_id: str
    origin_state_sha256: str


@dataclass(frozen=True)
class RuntimeState:
    view: task.TaskView
    transition: int = 0
    staged: proof.DerivedCandidate | None = None
    pending: AcquisitionIntent | None = None
    terminal: str | None = None
    last_reason: str = "NONE"

    def __post_init__(self):
        if type(self.view) is not task.TaskView or task.decode(task.encode(self.view)) != self.view:
            raise ValueError("Trusted canonical TaskView required")
        if not _integer(self.transition) or not _text(self.last_reason):
            raise ValueError("Invalid trusted runtime version/reason")
        if self.staged is not None and not candidate_shape(self.staged):
            raise ValueError("Staged candidate must be immutable and bounded")
        if self.terminal not in (None, "ANSWERED", "UNRESOLVED"):
            raise ValueError("Invalid trusted terminal")
        if self.terminal is not None and (self.pending is not None or self.staged is not None):
            raise ValueError("Closed state must not retain pending work")
        if self.pending is not None:
            p = self.pending
            if (type(p) is not AcquisitionIntent or p.action not in task.TOOLS
                    or not _integer(p.fact_index, 0, len(self.view.facts)-1)
                    or p.fact_id != self.view.facts[p.fact_index].fact_id
                    or (p.request_id, p.scope_id) != (self.view.request_id, self.view.scope_id)
                    or not _text(p.intent_id) or not _text(p.origin_state_sha256)):
                raise ValueError("Invalid trusted pending intent")


@dataclass(frozen=True)
class ActionProposal:
    schema: str
    request_id: str
    scope_id: str
    expected_state_sha256: str
    action: str
    fact_index: int = -1
    candidate: proof.DerivedCandidate | None = None


@dataclass(frozen=True)
class ActionResult:
    schema: str
    request_id: str
    scope_id: str
    action: str | None
    status: str
    reason: str
    internal_charged: int = 0
    acquisition_reserved: int = 0
    verifier_calls: int = 0
    checked_steps: int = 0
    intent: AcquisitionIntent | None = None
    derived: proof.DerivedResult | None = None


@dataclass(frozen=True)
class Transition:
    state: RuntimeState
    result: ActionResult


def state_digest(state: RuntimeState) -> str:
    if type(state) is not RuntimeState:
        raise TypeError("Trusted runtime state required")
    return _sha(asdict(state))


def propose(state: RuntimeState, action: str, *, fact_index: int = -1,
            candidate: proof.DerivedCandidate | None = None) -> ActionProposal:
    """Attach current identity, not authority or an expected correct action."""
    return ActionProposal(SCHEMA, state.view.request_id, state.view.scope_id,
                          state_digest(state), action, fact_index, candidate)


def step(state: RuntimeState, proposal: object, *, max_proof_steps: int = 7) -> Transition:
    """One bounded transition; never call a provider, solve a task or write evidence.

    Early malformed/stale/closed/zero-budget rejections do not change state.
    Every other non-STOP attempt costs one internal unit, including denial; ANSWER
    additionally pays actual verifier rule evaluations. STOP can terminate at zero
    budget; it cancels a local pending intent with no reservation refund.
    """
    if type(state) is not RuntimeState:
        raise TypeError("RuntimeState required")
    # Revalidate caller-owned state. This does not authenticate a remote producer.
    if replace(state) != state or not _integer(max_proof_steps, 0, proof.MAX_PROOF_STEPS):
        raise ValueError("Invalid trusted configuration")
    view, r = state.view, state.view.resources
    name = proposal.action if type(proposal) is ActionProposal and type(proposal.action) is str else None

    def unchanged(reason, status="REJECTED"):
        return Transition(state, ActionResult(SCHEMA, view.request_id, view.scope_id, name, status, reason))

    if type(proposal) is not ActionProposal or proposal.schema != SCHEMA:
        return unchanged("MALFORMED_PROPOSAL")
    p = proposal
    if not all(_text(v) for v in (p.request_id, p.scope_id, p.expected_state_sha256)):
        return unchanged("MALFORMED_PROPOSAL")
    if name not in ACTIONS:
        return unchanged("UNSUPPORTED_ACTION")
    if not _integer(p.fact_index, -1, len(view.facts)-1):
        return unchanged("INVALID_ARGUMENT")
    if name in task.TOOLS:
        legal = p.fact_index >= 0 and p.candidate is None
    elif name == "COMPUTE":
        legal = p.fact_index == -1 and candidate_shape(p.candidate)
    else:
        legal = p.fact_index == -1 and p.candidate is None
    if not legal:
        return unchanged("INVALID_ARGUMENT")
    if (p.request_id, p.scope_id) != (view.request_id, view.scope_id):
        return unchanged("REQUEST_SCOPE_MISMATCH")
    if p.expected_state_sha256 != state_digest(state):
        return unchanged("STALE_STATE")
    if state.terminal is not None:
        return unchanged("SESSION_CLOSED")
    if state.transition == task.MAX_INTEGER:
        return unchanged("VERSION_LIMIT", "DENIED")
    if name == "STOP":
        updated = replace(state, transition=state.transition+1, terminal="UNRESOLVED",
                          staged=None, pending=None, last_reason="STOP_REQUESTED")
        return Transition(updated, ActionResult(SCHEMA, view.request_id, view.scope_id,
                                                name, "UNRESOLVED", "STOP_REQUESTED"))
    if r.internal_remaining == 0:
        return unchanged("INTERNAL_BUDGET_EXHAUSTED", "DENIED")
    if r.internal_step == task.MAX_INTEGER:
        return unchanged("INTERNAL_STEP_LIMIT", "DENIED")

    def finish(status, reason, *, reserved=0, staged=state.staged,
               pending=state.pending, terminal=None, derived=None, checked=0, calls=0):
        debit = 1 + checked
        outcome = ("AUTHORIZED" if reserved else reason if reason in task.OUTCOMES else "NONE")
        resources = replace(r, internal_remaining=r.internal_remaining-debit,
            acquisitions_remaining=r.acquisitions_remaining-reserved,
            internal_step=r.internal_step+debit, last_outcome=outcome)
        updated = RuntimeState(replace(view, resources=resources), state.transition+1,
                               staged, pending, terminal, reason)
        return Transition(updated, ActionResult(SCHEMA, view.request_id, view.scope_id,
            name, status, reason, debit, reserved, calls, checked,
            pending if reserved else None, derived))

    if state.pending is not None:
        return finish("DENIED", "PENDING_ACQUISITION")
    if name in task.TOOLS:
        index = task.TOOLS.index(name)
        if not r.permitted[index]:
            return finish("DENIED", "PERMISSION_DENIED")
        if not r.available[index]:
            return finish("DENIED", "PROVIDER_UNAVAILABLE")
        if view.facts[p.fact_index].status == "OBSERVED":
            return finish("DENIED", "ALREADY_OBSERVED")
        if r.acquisitions_remaining == 0:
            return finish("DENIED", "BUDGET_EXHAUSTED")
        token = state_digest(state)
        intent = AcquisitionIntent(_sha((token, name, p.fact_index)), view.request_id,
            view.scope_id, name, p.fact_index, view.facts[p.fact_index].fact_id, token)
        return finish("PENDING", "ACQUISITION_RESERVED", reserved=1, pending=intent)
    if name == "COMPUTE":
        return finish("STAGED", "UNVERIFIED_CANDIDATE", staged=p.candidate)
    if state.staged is None:
        return finish("REJECTED", "NO_CANDIDATE")
    capacity = min(max_proof_steps, r.internal_remaining-1, task.MAX_INTEGER-r.internal_step-1)
    result = proof.verify(view, state.staged, max_steps=capacity)
    if result.status == "VERIFIED_DERIVED":
        return finish("VERIFIED_DERIVED", result.reason, staged=None, terminal="ANSWERED",
                      derived=result, checked=result.checked_steps, calls=1)
    return finish("REJECTED", result.reason, staged=None, checked=result.checked_steps, calls=1)
