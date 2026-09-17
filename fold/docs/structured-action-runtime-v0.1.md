# Structured action runtime v0.1

Recorded 2026-09-17 JST after C171 acceptance. Opt-in single-owner reference boundary,
not a learned controller, complete acquisition runtime or production rollout.
Authority: `structured-task-interface-v0.1.md`, `structured-derived-result-v0.1.md`,
`gate-e-evaluation-contract-v0.1.md`. Historical C170/C171 modules stay unchanged.

## Separation and implemented boundary

```text
trusted RuntimeState + version-bound ActionProposal
 -> validate schema/arguments/current state
 -> explicit resource enforcement
 -> local candidate staging / proof-checked answer / unresolved stop
 OR one reserved acquisition intent
```

New module `fold_lm/v05/structured_action_runtime.py`; schema
`fold-structured-action-runtime-v1`. Named actions are ANSWER, COMPUTE, RETRIEVE,
OBSERVE, ASK_USER, STOP. These are not a reinterpretation of old numeric indices.
No external provider, file/network call, observation writer, model or solver callback
exists in this module. No import-time work. RuntimeState is trusted owner-side state;
an untrusted actor must not replace it with a fabricated authoritative snapshot.

## Types and current-state binding

Frozen RuntimeState holds unchanged C170 TaskView, transition counter, optional staged
DerivedCandidate, optional AcquisitionIntent, terminal and full last_reason. Proposal
carries schema/request/scope/expected_state_sha256/action and only the legal arguments.
The state digest covers task syntax, fact views and supports, resource flags/counters,
transition number, staged candidate, pending intent and terminal. Changing any of these
requires a fresh proposal. A stale or replayed proposal is rejected without effects.

The digest is a consistency token, NOT a signature, access-control capability or
concurrency primitive. The trusted caller must adopt the returned state before accepting
the next proposal; calling twice on the same old snapshot is outside this sequential
contract. No crash durability, cross-process CAS, cancellation RPC or persisted receipt.
A future neural policy must consume an explicit view of pending/terminal/outcomes too;
C170's 72-field packet alone is not claimed to implement that learned consumption.

## Action handlers

| Action | Implemented behavior |
|---|---|
| COMPUTE | Stage a caller-proposed bounded immutable derived candidate, without proving, fixing or solving it. This is the COMPUTE handoff, not a reasoning algorithm. |
| ANSWER | Validate the staged candidate against the current TaskView using unchanged C171 verify; return VERIFIED_DERIVED and close only if verification succeeds. |
| RETRIEVE / OBSERVE / ASK_USER | Validate target, pending state, permission, provider availability and budget; reserve one acquisition unit and return a named PENDING intent. No fact/value is acquired. |
| STOP | Close as UNRESOLVED, clear local staged/pending work, assert no value. Allowed at zero internal budget. No reservation refund. |

A staged candidate's shape is validated without semantic verification. A well-shaped
wrong conclusion remains wrong and is later rejected, never repaired. ANSWER has no
inline candidate argument, so callers cannot bypass staging. Successful derived output
keeps its proof/support and does not promote it to an observation.

One pending acquisition is allowed. A fresh duplicate, cross-tool request, COMPUTE or
ANSWER while pending is denied. STOP discards the local intent; the reserved unit stays
spent. This is a conservative bounded prototype policy, not an optimal cost policy.
The external transport/completion/reply/admission bridge is NOT implemented. In particular
an intent is neither a completed fetch nor permanent authorization to execute later.
A future transport must check current authority again and match the outstanding intent.
ASK_USER does not send a message, observe a reply or solve the pending-request lifecycle.

## Validation and accounting

Early schema/argument/binding/stale/closed-state rejection has zero declared internal
units and returns the same state. Internal budget0 or bounded version/clock exhaustion
also returns unchanged state. Parsing/hashing still costs CPU time; zero declared units
is not zero wall-clock work. Callers must bound untrusted submissions separately.

STOP charges0 units and advances transition counter; it does not advance internal_step.
Every other current well-formed attempt with internal capacity charges1 internal unit,
including permission/provider/budget denial, missing candidate and pending-work denial.
Each such transition increments internal_step and transition counter. Failed proposals
cannot repeatedly consume external tokens or execute transport.

For external actions the checks after the internal budget check are: existing pending,
permission, availability, already OBSERVED target, acquisition allowance. Unusable views
may be requested, but their values remain None and their status is not silently changed.
Permission and availability are separate axes. Numerical necessity labels never enter
this boundary, so avoiding a request for an already OBSERVED fact is not inferred query
relevance. A conclusion-irrelevant unknown fact can still be requested by a poor policy.

ANSWER additionally charges actual C171 checked_steps. Effective max_steps is the minimum
of configured capacity, remaining internal units after the dispatch unit, and remaining
integer clock headroom. Insufficient capacity rejects before rule evaluation, without
inventing a proof. This charges the declared abstract proof work, not neural inference,
all Python validation/hash overhead or real-time CPU duration.

Last detailed outcome remains in RuntimeState.last_reason and ActionResult. Only outcomes
already legal under C170 map into its unchanged Resources.last_outcome enum; other details
use NONE there. No silent expansion of the historical input schema or old checkpoint.
ActionResult separates internal_charged, acquisition_reserved, verifier_calls, checked_steps,
intent and derived result. No value/support/proof is exposed as a successful answer on
rejection; unverified candidate state remains distinct from public answer content.

## Remaining obligations

C172 is a bounded action-boundary implementation test, not closure of every D5 behavior.
Real provider admission/re-observation, user replies, policy learning, proposal quality,
complete proof rules, proof authenticity and final nine-family Gate E comparisons remain
separate. Do not turn PENDING into ANSWERED or claim a scripted proposal is learned control.
Next work should connect real episode outcomes and a separately evaluated task policy;
do not repeat this known scope as another unchanged-source inventory.
