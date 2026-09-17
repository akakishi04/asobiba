# Structured acquisition lifecycle v0.1

Recorded 2026-09-17 JST after C172 acceptance in `544f6adceae37481cb414f0db8abce9929ec31da`.
Opt-in bounded single-owner reference implementation, not production deployment.
C170 input, C171 verifier and C172 action runtime remain unchanged.

## One connection

```text
C172 named proposal -> reserved pending intent
 -> owner rechecks current task identity, permission, availability and internal capacity
 -> one synchronous registered provider invocation
 -> bounded snapshot witness and reply binding validation
 -> publish ONLY the requested usable fact in TaskView, or retain old facts on failure
 -> clear pending/staged work -> fresh C170 policy view
 -> separately supplied candidate -> unchanged C172/C171 proof-checked answer
```

`structured_acquisition_lifecycle.py` adds AcquisitionOwner, SourceBinding, Endpoint,
FetchRequest, Delivery, AdmittedFact, DispatchResult and FileSnapshotProvider.
The owner adopts C172 returned RuntimeState; callers cannot hand dispatch an old snapshot.
An owner starts without inherited pending work. It records reservation task/evidence
identity when its apply() receives PENDING. This is not a durable import/recovery API.

## Trusted versus untrusted boundaries

Source bindings and provider callbacks are installed by the trusted runtime, never by a
policy. The callback receives selected fact identity, tool and request/scope/intent, plus
registered source metadata, not expression truth, expected action or hidden answer labels.
The policy-facing path remains C170 encode(state.view). Owner objects, registry, raw
snapshot witnesses and debug receipts are not model input. Adapter trust is not a claim
that arbitrary Python callback code is sandboxed.

FileSnapshotProvider reads only its configured local path, at most4097 bytes to detect
an over4096-byte source. It requires the configured SHA256 and a strict JSON snapshot
with at most4 unique fact records, integer bits, provider identity and fixed time/revision.
No approximate search, hidden fallback, network or alternate-path lookup. Reads/bytes
include unsuccessful attempts. validated_records counts only successfully parsed full
files, not all parser operations or all validation CPU work.

Delivery carries the original bounded source document as a runtime-private witness.
Admission rechecks its hash, strict schema and requested record/value, in addition to
request/scope/tool/intent/provider/epoch/reference binding. Thus changing0 to1 while
keeping a plausible source ID is not accepted. A false MISSING claim against a present
record is rejected. Witness validation is hand-written and deliberately repeats bounded
parsing; it is not free and does not prove a source's real-world truth.

Only an AdmittedFact receipt, without the full witness, is retained after success. Only
the requested fact's usable value/support enters TaskView; other source values do not.
Source hash and reference IDs bind the runtime snapshot, not an evaluator's target value.
The fixed source is a synthetic episode snapshot, not live world observation or a new
production memory store. Evidence time/revision stay fixed; fact/evidence digest and
runtime transition change. No core EvidenceState or durable database write is implemented.

## Dispatch state and costs

A nonempty matching intent is required. No pending, wrong intent, busy reentrant call,
insufficient room for2 internal units, or version/clock exhaustion causes no provider call
and no declared cost; the legitimate pending intent is retained where applicable.
Reservation identity compares request/scope, expression and full fact view. Resource
snapshots are rechecked independently, so revoking permission after reservation blocks IO.
Valid pre-dispatch stale/denied/unavailable/attempt-limit/source-epoch outcomes clear local
pending and staged work, charge1 internal unit, and do not refund the reserved acquisition.

A provider attempt consumes2 internal units:1 dispatch plus1 bounded receipt validation.
No further acquisition unit is deducted: C172 already reserved it. Before IO the owner
marks the intent used and denies reentrant dispatch/apply/refresh. Expected ProviderFailure
or OSError closes the attempt as unresolved without value; an unexpected exception closes
spent work, resets busy state, and propagates to invalidate the experiment. No automatic retry.
At most4 dispatches per owner by default; configuration is bounded1..16. Receipts and used
intent records therefore remain bounded. No concurrent access or crash/restart guarantee.

The complete CPU cost of parsing/hashing and neural compute is not represented by these
abstract units. Byte/read counts and wall-clock are separate. Counters never claim that a
reservation or callback is a successful read. Replayed callbacks can perform no new IO.

## Publication, failure and proof invalidation

FOUND needs an exact integer bit matching the authenticated snapshot witness and selected
record. Publish one OBSERVED Fact with the derived snapshot-reference identity. Receipt
and new RuntimeState are owned together in this sequential object; there is no durable
transaction or concurrent CAS. Staged candidates are cleared at completion, including
failed completion; derived values are never inserted as observed facts.

Missing delivery, actual record miss, wrong binding, invalid values or failed source checks
leave all existing facts untouched. They return no unverified evidence payload. Missing
record is RECORD_UNBOUND, not fact0, falsehood or real-world nonexistence. Pending is cleared
for a completed attempt; a retry requires a fresh C172 proposal and remaining budget.
A previously valid proof must be rebound/recomputed against the new fact digest. C171
rejects its old evidence binding even if its numerical conclusion happens to remain true.

refresh(view) is a trusted scheduler/test hook: same request/scope/fact identities, no
budget increase, no clock regression, no closed session or in-flight refresh. It models
pre-dispatch authority or task invalidation, not policy editing of observations. The
caller owns evidence authentication; this hook is not a new inference mechanism.

## Deliberate exclusions

C173 registers local-file endpoints for RETRIEVE, OBSERVE and ASK_USER to exercise their
shared envelope/lifecycle. OBSERVE is not Vision; ASK_USER does not send a real message or
wait for a human. This synchronous prototype is not a full asynchronous reply protocol,
transport cancellation, process fencing or session persistence mechanism.
Proofs/actions in its benchmark are scripted fixtures; no learned necessity, question
selection, proof generation, C151 ranking or FOLD model quality is measured. This connects
existing contracts without reopening their historical criteria or passing Gate E.
