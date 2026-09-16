# Structured task interface v0.1 — consolidated design after C169

Recorded 2026-09-17 JST after acceptance of C169 in `8658cd7a9468413fa3ee68696e72d1c0fe02c7ff`.
**Design decisions plus a first input-contract implementation; not a learned capability or Gate verdict.**
Authority: `gate-e-evaluation-contract-v0.1.md`, `experiment-ledger-addendum-c169-c170.md`, `AGENTS.md`.
The accepted C158-C169 implementations and results stay immutable. C170 tests the input boundary only.

## 1. One coherent separation

```text
visible TaskView (expression + declared fact read views)
       + runtime-owned Resources snapshot
       -> explicit versioned policy input
       -> future learned task/control component
       -> typed ActionProposal
       -> runtime revalidation and bounded handler
       -> observed evidence OR derived candidate, never interchangeable
       -> bound result / unresolved with reasons
```

This is not a replacement architecture for the FOLD shared core, compression, or memory.
It is the missing task-facing boundary for a bounded structured Gate E prototype.
Do not stuff task data into the old ignored tail channels, assign the evaluator's correct
dependency bit, or reuse a checkpoint under changed channel semantics without evaluation.

| C169 evidence | Design response | Implemented in C170? |
|---|---|---|
| D1 lacks operator/known-fact route | Explicit ordered expression and fact table | Yes |
| D2 truncates tail and mean-pools slots | New schema with all declared fields delivered, no legacy pooling adapter | Yes, to a capture consumer; no learned reader yet |
| D3 collapses unresolved statuses in learned input | Fact read status and value mask separate; preserve unusable evidence identities without exposing its value | Yes, as supplied views |
| D4 only availability reaches current decision | Explicit tool availability, permission and resource snapshot; authority still runtime-owned | View only; no execution change |
| D5 unsupported dispatch indices1/3/4 | Versioned named proposals with explicit handlers; no guessed old-index remapping | Design only |
| D6 observed-bit-only emitter | Separate derived-result/proof contract; leave C159 observation guard intact | Design only |

The absence of new action/proof execution is intentional. Correct input delivery does
not close D5/D6 or make the full extension ready. Those obligations are recorded here
rather than rediscovered in further unchanged-source diagnostic experiments.

## 2. Implemented input types

Module `fold_lm/v05/structured_task_input.py` is opt-in and has no import-time execution,
model, solver, network access, acquisition callback, evidence writer or checkpoint loader.
All public views are frozen dataclasses using tuples and exact validated scalar types.

**TaskView:** request/scope identity, evidence time/revision, ordered expression nodes,
fact table and resource snapshot. No correct dependency, expected answer, hidden value
or evaluation label field. The expression is already structured; this is not a natural-
language parser or a claim that C151 understands logical expression text.

**Node:** FACT / AND / OR; explicit fact-table index or preceding left/right node indices;
NOT only on a leaf. At most4 facts,7 nodes and3 binary operators. Root is the final node.
Require a connected tree with one parent per non-root node; reject DAG sharing, cycles,
disconnected nodes, unknown indices and silent truncation. Repeated facts are represented
by separate leaf occurrences. Preserve syntactic order; do not simplify or solve expressions.

**Fact:** opaque fact ID, read status, optional usable value and up to2 support identities.
Statuses: UNOBSERVED, OBSERVED, STALE, CONFLICT, INVALID, SOURCE_UNBOUND,
SNAPSHOT_MISMATCH, REFERENCE_MISMATCH. OBSERVED needs integer0/1 (not Boolean/float)
and one support identity. Other statuses require value=None; stale or conflicting raw
payloads stay in the separate evidence store, not a current usable-value channel.
UNOBSERVED has no support; CONFLICT retains two distinct competing support identities.
These names describe supplied read views. The adapter does not authenticate sources or
infer whether evidence is stale/conflicting. Fixtures declare those states in C170;
a future live bridge must derive them from actual authority/provenance/read results.

**Resources:** remaining internal/observation budget, internal step, separate availability
and permission flags for RETRIEVE / OBSERVE / ASK_USER, and last runtime outcome.
This is a snapshot for the policy, not authorization. Execution must recheck authoritative
state so a stale policy view cannot increase permissions or reuse spent budget.
The snapshot may represent permission granted but no provider, or an available provider
without permission; do not merge these axes. Zero internal budget remains representable.

## 3. Numeric consumption contract

Schema `fold-structured-task-input-v1`, **72 exact integer features**:

| Offsets (zero-based) | Content |
|---|---|
| 0..3 | actual node/fact counts, evidence time, revision |
| 4..45 |7 node slots x6: slot mask, kind code, fact index+1, left+1, right+1, negation |
| 46..61 |4 fact slots x4: slot mask, read-status code, usable-value mask, value placeholder |
| 62..71 |internal/acquisition remaining,3 availability flags,3 permission flags,last-outcome code,internal step |

Zero padding is canonical. An unknown value uses value mask0 and placeholder0; it is
not a false observation. Reject nonzero padding, bad masks, Boolean-as-integer, invalid
codes, hidden placeholders and out-of-range indices. Integers are bounded by2^24-1 so
conversion to float32 can preserve their exact integer values; C170 itself uses Python
integers, not a GPU tensor. That bound is this prototype schema, not a production clock.

Request/scope, fact names and support identities are retained in an immutable Binding
sidecar, not numerically hashed into features. Expression indices refer to its fact table.
Renaming opaque IDs can preserve numeric features while changing binding, deliberately.
Thus losslessness means numeric visible task state plus the binding sidecar roundtrip;
it does not mean a learned model sees every character of a provenance identifier.
No storage/VRAM win is inferred from72 scalars; Python objects and binding metadata cost
additional memory. No categorical scalar ordering is asserted to be a good learned encoding.

`encode(TaskView)` never evaluates Boolean logic. `decode(PolicyInput)` reconstructs and
re-encodes to reject noncanonical packets. `deliver(view, consumer)` requires the consumer
to explicitly declare this schema; no implicit conversion to C157's old four-channel lane.
The C170 consumer records the complete packet. A trained consumer remains unimplemented.
A future neural reader needs its own controlled experiment; preserving inputs before a
reader does not prove separability after its normalization/pooling/learned projection.

This is not a universal leak detector: trusted producers must supply only legitimately
visible data and provenance. The strict schema blocks named/typed hidden-payload routes;
it cannot prevent a malicious producer encoding answers into an arbitrary identifier.

## 4. Action execution design — not implemented by C170

Define a new versioned ActionProposal with named action and explicit arguments, task/scope
identity and expected evidence/resource revision. Do not equate names with legacy indices
1/3/4 without an explicit mapping and tests. Advertise only handlers actually implemented.
Runtime must separately validate proposal schema, arguments, handler availability,
permission, budget, attempt limits and expected versions before side effects.

COMPUTE changes only working/derived state and consumes internal work. RETRIEVE and
OBSERVE consume registered external-operation budgets and return provenance-bound outcomes.
ASK_USER creates a typed request for a specific task field and records a pending request;
absence of a reply is not evidence, and the same request must not be silently repeated.
ANSWER proposes a claim; it does not bypass output verification. STOP returns unresolved
state without asserting falsehood or nonexistence. Unsupported handlers fail closed with
an explicit outcome, not automatic substitution by a different action.

For the eventual learner compare raw proposals and actually executed actions separately.
A mask supplied from true necessity would be an oracle; a mask from real availability or
runtime permission is an operational constraint. Record which kind is used and any action
suppression, and keep hard enforcement outside the model in either case.

## 5. Observed versus derived results — not implemented by C170

Keep existing C159 OBSERVED_VALUE unchanged. Introduce a separate future derived-candidate
contract with expression identity/digest, request/scope, evidence revision, conclusion,
support identities and a bounded derivation. A derived conclusion is not an observation
of a missing fact. Example: A=1 proves A OR B=1 without observing B; no B value may be
written into EvidenceState merely because the conclusion is known.

Validate support identities, times/scopes and a declared restricted derivation rule set
against admissible observed evidence. Reject invented/invalid support and disagreement;
do not weaken the old observed-bit guard or relabel an altered final_value as derivation.
A future reference proof checker is hand-written infrastructure, not learned reasoning.
Do not give its solution or necessity labels to the candidate, and measure pre-guard
candidate errors so a common checker cannot manufacture a model-quality win.
Hypotheses, partial computations and verified derived claims stay distinct from observations.

## 6. Execution sequence / experimental boundary

C170 is the first input-transport intervention: one versioned TaskView-to-consumer contract,
including associated status/resource fields and strict guards, with no learned policy or
old runtime modification. It is not another inventory of known missing code.
All contract subchecks run as one small batch; no new user execution per individual field.

After its formal judgment, integrate the future learned/task-control and typed action/
derived-result paths under explicit separate hypotheses. No fixed remaining-C count is
promised. Do not consume final holdout data or tune a checkpoint before separate baseline-
development, split, candidate and numerical criteria are registered as required by the
existing nine-family Gate E contract. The scope is unchanged; Gate E remains NOT PASSED.
