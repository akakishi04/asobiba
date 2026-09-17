"""Single-owner synchronous acquisition bridge for bounded structured episodes.

C172 still owns proposals/reservations; C171 still owns proof checking. This opt-in
bridge reads a registered tiny snapshot, validates the reply, and publishes a fact
view, never a derived conclusion. No network, model, durable store or async worker.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from . import structured_task_input as task
from . import structured_derived_result as proof
from . import structured_action_runtime as action

SCHEMA = "fold-structured-acquisition-v1"
SOURCE_SCHEMA = "fold-structured-source-v1"
MAX_SOURCE_BYTES = 4096
MAX_DISPATCHES = 16


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def text(value) -> bool:
    return type(value) is str and 0 < len(value) <= 256 and bool(value.strip())


def integer(value) -> bool:
    return type(value) is int and 0 <= value <= task.MAX_INTEGER


@dataclass(frozen=True)
class SourceBinding:
    provider_id: str
    source_sha256: str
    evidence_time: int = 1
    revision: int = 1

    def __post_init__(self):
        if (not text(self.provider_id) or type(self.source_sha256) is not str
                or len(self.source_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.source_sha256)
                or not integer(self.evidence_time) or not integer(self.revision)):
            raise ValueError("Trusted bounded source binding required")


@dataclass(frozen=True)
class FetchRequest:
    intent_id: str
    request_id: str
    scope_id: str
    action: str
    fact_id: str
    source: SourceBinding


@dataclass(frozen=True)
class Delivery:
    schema: str
    intent_id: str
    request_id: str
    scope_id: str
    action: str
    fact_id: str
    source: SourceBinding
    status: str
    value: int | None = None
    reference_id: str | None = None
    source_document: str | None = None  # Runtime-only witness, never a policy feature.


@dataclass(frozen=True)
class AdmittedFact:
    intent_id: str
    request_id: str
    scope_id: str
    action: str
    fact_id: str
    source: SourceBinding
    value: int
    reference_id: str


@dataclass(frozen=True)
class Endpoint:
    source: SourceBinding
    fetch: Callable[[FetchRequest], object]

    def __post_init__(self):
        if type(self.source) is not SourceBinding or not callable(self.fetch):
            raise ValueError("Explicit source and trusted adapter required")


@dataclass(frozen=True)
class DispatchResult:
    schema: str
    intent_id: str | None
    status: str
    reason: str
    internal_charged: int = 0
    provider_calls: int = 0
    fact_publications: int = 0
    evidence: AdmittedFact | None = None


class ProviderFailure(ValueError):
    """Expected provider failure, with no usable evidence."""


def reference_id(source: SourceBinding, fact_id: str) -> str:
    return "snapshot-ref:" + digest((asdict(source), fact_id))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProviderFailure("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_source(raw: bytes, source: SourceBinding) -> dict[str, int]:
    """Validate the bounded witness against a runtime-pinned snapshot, not an answer label."""
    if type(raw) is not bytes or type(source) is not SourceBinding:
        raise ProviderFailure("MALFORMED_SOURCE")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ProviderFailure("SOURCE_SIZE_LIMIT")
    if hashlib.sha256(raw).hexdigest() != source.source_sha256:
        raise ProviderFailure("SOURCE_HASH_MISMATCH")
    try:
        doc = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProviderFailure("MALFORMED_SOURCE") from exc
    if (type(doc) is not dict or set(doc) !=
            {"schema", "provider_id", "evidence_time", "revision", "records"}
            or doc["schema"] != SOURCE_SCHEMA or doc["provider_id"] != source.provider_id
            or not integer(doc["evidence_time"]) or not integer(doc["revision"])
            or (doc["evidence_time"], doc["revision"]) !=
               (source.evidence_time, source.revision)
            or type(doc["records"]) is not list or not 1 <= len(doc["records"]) <= 4):
        raise ProviderFailure("SOURCE_CONTRACT_MISMATCH")
    records = {}
    for row in doc["records"]:
        if (type(row) is not dict or set(row) != {"fact_id", "value"}
                or not text(row["fact_id"]) or row["fact_id"] in records
                or type(row["value"]) is not int or row["value"] not in (0, 1)):
            raise ProviderFailure("INVALID_SOURCE_RECORD")
        records[row["fact_id"]] = row["value"]
    return records


class FileSnapshotProvider:
    """Bounded actual file read. Path/hash are registered outside policy inputs.

    This is a tiny exact reference provider, not C151 ranking or C155's vector
    index. Read/byte counters include failed attempts; validated_records counts only
    fully validated files. No fallback to another source.
    """
    def __init__(self, path: Path, source: SourceBinding):
        if type(source) is not SourceBinding:
            raise TypeError("SourceBinding required")
        self.path, self.source = Path(path), source
        self.reads = self.bytes_read = self.validated_records = 0

    def __call__(self, request: FetchRequest) -> Delivery:
        if type(request) is not FetchRequest or request.source != self.source:
            raise ProviderFailure("REQUEST_SOURCE_MISMATCH")
        self.reads += 1
        with self.path.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
        self.bytes_read += len(raw)
        records = parse_source(raw, self.source)
        self.validated_records += len(records)
        value = records.get(request.fact_id)
        return Delivery(SCHEMA, request.intent_id, request.request_id, request.scope_id,
            request.action, request.fact_id, self.source, "FOUND" if value is not None else "MISSING",
            value, reference_id(self.source, request.fact_id) if value is not None else None,
            raw.decode("utf-8"))


def view_identity(view: task.TaskView) -> str:
    return digest((view.request_id, view.scope_id,
                   proof.expression_digest(view), proof.evidence_digest(view)))


class AcquisitionOwner:
    """Sequential owner adopts C172 transitions before any provider invocation.

    Do not give this owner, refresh(), or adapters to an untrusted policy. This is
    not a thread/process lock, durable receipt service, or cryptographic authority.
    Provider callbacks are synchronous trusted adapters; reentrant work is denied.
    """
    def __init__(self, state: action.RuntimeState, endpoints: Mapping[str, Endpoint], *,
                 max_dispatches: int = 4):
        if type(state) is not action.RuntimeState or state.pending is not None:
            raise ValueError("Start from a trusted state without an inherited pending intent")
        if type(max_dispatches) is not int or not 1 <= max_dispatches <= MAX_DISPATCHES:
            raise ValueError("Explicit bounded dispatch limit required")
        if any(k not in task.TOOLS or type(v) is not Endpoint for k, v in endpoints.items()):
            raise ValueError("Registered named endpoints required")
        self._state = state
        self._endpoints = MappingProxyType(dict(endpoints))
        self._limit = max_dispatches
        self._used: tuple[str, ...] = ()
        self._receipts: tuple[AdmittedFact, ...] = ()
        self._reservation: tuple[str, str] | None = None
        self._busy = False

    @property
    def state(self):
        return self._state

    @property
    def receipts(self):
        return self._receipts

    @property
    def dispatched_intents(self):
        return self._used

    def apply(self, proposal: object) -> action.Transition:
        if self._busy:
            v = self._state.view
            return action.Transition(self._state, action.ActionResult(action.SCHEMA,
                v.request_id, v.scope_id, None, "DENIED", "TRANSPORT_BUSY"))
        transition = action.step(self._state, proposal)
        self._state = transition.state
        if transition.result.acquisition_reserved:
            self._reservation = (self._state.pending.intent_id, view_identity(self._state.view))
        elif self._state.pending is None:
            self._reservation = None
        return transition

    def refresh(self, view: task.TaskView) -> None:
        """Trusted scheduler hook, not a policy action or an observation authenticator.

        Used to invalidate stale reservations / revoke authority before dispatch.
        Never replenishes budgets; not available during synchronous provider work.
        """
        old = self._state.view
        if (self._busy or self._state.terminal is not None or type(view) is not task.TaskView
                or (view.request_id, view.scope_id, tuple(f.fact_id for f in view.facts)) !=
                   (old.request_id, old.scope_id, tuple(f.fact_id for f in old.facts))
                or view.resources.internal_remaining > old.resources.internal_remaining
                or view.resources.acquisitions_remaining > old.resources.acquisitions_remaining
                or view.resources.internal_step < old.resources.internal_step
                or view.evidence_time < old.evidence_time or view.revision < old.revision
                or self._state.transition == task.MAX_INTEGER):
            raise ValueError("Invalid trusted refresh")
        self._state = replace(self._state, view=view, transition=self._state.transition+1)

    def dispatch(self, intent_id: str) -> DispatchResult:
        state = self._state
        def reject(reason, status="REJECTED"):
            return DispatchResult(SCHEMA, intent_id if text(intent_id) else None, status, reason)
        if self._busy:
            return reject("TRANSPORT_BUSY", "DENIED")
        if not text(intent_id):
            return reject("INVALID_INTENT")
        p = state.pending
        if p is None:
            return reject("NO_PENDING_INTENT")
        if p.intent_id != intent_id or self._reservation is None or self._reservation[0] != intent_id:
            return reject("INTENT_MISMATCH")
        r = state.view.resources
        if (r.internal_remaining < 2 or r.internal_step > task.MAX_INTEGER-2
                or state.transition == task.MAX_INTEGER):
            return reject("INTERNAL_BUDGET_EXHAUSTED", "DENIED")

        def finish(status, reason, *, calls=0, evidence=None):
            debit = 1 + calls
            resources = replace(r, internal_remaining=r.internal_remaining-debit,
                internal_step=r.internal_step+debit,
                last_outcome=reason if reason in task.OUTCOMES else "NONE")
            facts = state.view.facts
            if evidence is not None:
                facts = tuple(task.Fact(f.fact_id, "OBSERVED", evidence.value,
                    (evidence.reference_id,)) if i == p.fact_index else f for i, f in enumerate(facts))
            view = replace(state.view, facts=facts, resources=resources)
            updated = replace(state, view=view, pending=None, staged=None,
                              transition=state.transition+1, last_reason=reason)
            self._state = updated
            self._reservation = None
            if evidence is not None:
                self._receipts += (evidence,)
            return DispatchResult(SCHEMA, intent_id, status, reason, debit, calls,
                                  int(evidence is not None), evidence)

        if view_identity(state.view) != self._reservation[1]:
            return finish("REJECTED", "STALE_RESERVATION")
        i = task.TOOLS.index(p.action)
        if not r.permitted[i]:
            return finish("DENIED", "PERMISSION_DENIED")
        endpoint = self._endpoints.get(p.action)
        if not r.available[i] or endpoint is None:
            return finish("DENIED", "PROVIDER_UNAVAILABLE")
        if len(self._used) >= self._limit or intent_id in self._used:
            return finish("DENIED", "ATTEMPT_LIMIT")
        source = endpoint.source
        if (source.evidence_time, source.revision) != (state.view.evidence_time, state.view.revision):
            return finish("REJECTED", "SOURCE_EPOCH_MISMATCH")
        request = FetchRequest(intent_id, p.request_id, p.scope_id, p.action, p.fact_id, source)
        # Claim BEFORE invoking any adapter; duplicate/reentrant work cannot issue a second call.
        self._used += (intent_id,)
        self._busy = True
        try:
            try:
                delivery = endpoint.fetch(request)
            except (ProviderFailure, OSError):
                return finish("UNRESOLVED", "PROVIDER_FAILURE", calls=1)
            except Exception:
                # Preserve spent work and suppress replay even on an unexpected adapter exception.
                finish("UNRESOLVED", "UNEXPECTED_PROVIDER_EXCEPTION", calls=1)
                raise
            if delivery is None:
                return finish("UNRESOLVED", "MISSING_DELIVERY", calls=1)
            if (type(delivery) is not Delivery or delivery.schema != SCHEMA
                    or type(delivery.source) is not SourceBinding
                    or any(type(getattr(delivery, k)) is not str for k in
                           ("intent_id", "request_id", "scope_id", "action", "fact_id", "status"))
                    or (delivery.intent_id, delivery.request_id, delivery.scope_id, delivery.action,
                        delivery.fact_id, delivery.source) !=
                       (request.intent_id, request.request_id, request.scope_id, request.action,
                        request.fact_id, request.source)):
                return finish("REJECTED", "DELIVERY_BINDING_MISMATCH", calls=1)
            if type(delivery.source_document) is not str or len(delivery.source_document) > MAX_SOURCE_BYTES:
                return finish("REJECTED", "INVALID_EVIDENCE", calls=1)
            try:
                records = parse_source(delivery.source_document.encode("utf-8"), source)
            except (ProviderFailure, UnicodeError):
                return finish("REJECTED", "INVALID_EVIDENCE", calls=1)
            actual = records.get(p.fact_id)
            if (delivery.status == "MISSING" and delivery.value is None
                    and delivery.reference_id is None and actual is None):
                return finish("UNRESOLVED", "RECORD_UNBOUND", calls=1)
            if (delivery.status != "FOUND" or type(delivery.value) is not int
                    or delivery.value not in (0, 1) or actual is None or delivery.value != actual
                    or type(delivery.reference_id) is not str
                    or delivery.reference_id != reference_id(source, p.fact_id)):
                return finish("REJECTED", "INVALID_EVIDENCE", calls=1)
            receipt = AdmittedFact(delivery.intent_id, delivery.request_id, delivery.scope_id,
                delivery.action, delivery.fact_id, delivery.source, delivery.value, delivery.reference_id)
            return finish("PUBLISHED", "OBSERVATION_ADMITTED", calls=1, evidence=receipt)
        finally:
            self._busy = False
