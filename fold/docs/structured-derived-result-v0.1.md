# Structured derived result v0.1

Recorded 2026-09-17 JST after C170 acceptance `77bebd715ae18215546c7d4e1cf5414d04f663a6`.
Implements the derived-result boundary proposed in `structured-task-interface-v0.1.md`.
This is hand-written reference infrastructure,not learned reasoning or a Gate verdict.
The C170 input schema and C159 observed-value emitter remain unchanged.

## Trust boundary and meaning

A trusted current `TaskView` plus an explicitly proposed `DerivedCandidate` enters
`verify(view,candidate,max_steps=7)`. The verifier accepts no hidden values,expected
answers,necessity labels,provider callbacks or evidence writer. It never invents a proof
or substitutes a correct conclusion for a rejected proposal.

A result is `VERIFIED_DERIVED / VALID_LOCAL_PROOF` or `REJECTED / reason`.
Only a verified result carries a value,supports and proof. Rejection carries value=None
and empty support/proof;it is not a learned STOP,bit0,nonexistence,or logical impossibility.
`derivation_kind=BOOLEAN_LOCAL_PROOF` and a separate result schema distinguish this
claim from C159 `OBSERVED_VALUE`. Even a leaf expression is returned via this derived
contract when that contract is used;C159's observed path is not silently repurposed.

The current view must be supplied by trusted runtime infrastructure. Its OBSERVED status
and support strings are not authenticated by this checker. Hash binding is not a signature
or evidence of real-world truth. C170 supplies only aggregate evidence time/revision and
opaque support IDs;per-source authentication and concurrent snapshot/commit control must
be established by the future live bridge. This checker checks identity against its input,
not a live external source. It cannot detect a dishonest trusted producer.

## Binding

Candidate and result carry request/scope,evidence time/revision,an expression SHA256,
and an evidence-view SHA256. Expression digest covers all ordered nodes and ordered fact
IDs. Evidence digest covers all current fact views,including status,value,reference IDs,
time and revision. A changed unused fact conservatively invalidates the old evidence digest.
Resource counters are excluded:changing permission or budget alone does not make a valid
static conclusion false. This read-only check grants no permission to acquire or publish.
The caller must revalidate the current snapshot at a later authoritative commit boundary.

## Bounded proposed proof

At most7 typed `ProofStep`s,one per used AST node,in ascending node-index order. Premises
are AST node indices and must refer to prior proven direct children. The final step proves
the actual root. Every proof step must contribute to that root;unused steps are rejected.
No arbitrary execution,recursion into user code or dynamic expression compilation exists.

Allowed rules:

- OBSERVED_LEAF: current fact is OBSERVED,exact support matches,value equals that observation
  with the leaf's declared NOT applied. No value can be read from unusable fact status.
- AND_BOTH / OR_BOTH: both actual direct children were proven;check the declared Boolean operation.
- AND_LEFT_ZERO / AND_RIGHT_ZERO: the selected actual child was proven0;the other need not be observed.
- OR_LEFT_ONE / OR_RIGHT_ONE: the selected actual child was proven1;the other need not be observed.

Supports are canonical ascending fact-index/reference-ID pairs,one per used observed fact.
Repeated occurrences may use the same fact support but must prove distinct AST nodes.
Missing,duplicate,unused,wrong-index,wrong-source or unusable support is rejected.

Example: A=1 and B=UNOBSERVED can support A OR B=1 using the observed A leaf and an
OR_LEFT_ONE step. B remains UNOBSERVED/value=None. The conclusion is not a new B observation.

These local rules are sound for their declarations but **not a complete Boolean prover**.
For example,A OR NOT A with A unobserved has a definite truth value but needs a case-split/
excluded-middle rule not included in v0.1. An empty proof remains rejected even for that
true conclusion. C171 explicitly records this limitation rather than scoring it as task
impossibility. Adding such rules requires a separate version/evaluation;no completeness
claim for the final Gate E family inventory is made.

## Costs and errors

max_steps is an exact integer0..7 provided by the caller;malformed capacity or an invalid
trusted TaskView raises a configuration error. Candidate faults yield REJECTED. A proof
longer than7 is malformed;one longer than the supplied capacity is rejected with
VERIFICATION_BUDGET_EXHAUSTED before evaluating any rules. checked_steps counts actual
attempted rule evaluations,including a failing step. It never exceeds capacity.

View/schema/hash/support validation also costs CPU work and is not included in checked_steps.
This is a read-only capacity-limited checker,not integrated internal-budget debit or action
dispatch. C171 reports rule counts and batch wall time;it does not claim free verification
or full-model latency/VRAM savings. Bounded node/fact counts do not bound arbitrary opaque
string byte lengths;an external producer must bound metadata for production use.

## Evaluation / next boundary

C171 uses benchmark-only symbolic proof fixtures and independent exhaustive Boolean
completion scoring. Neither is a learned policy. The future learner must generate its
own proposed claims/proofs;measure pre-guard errors and emitted results under a common
checker. Do not feed solutions/necessity labels from this verifier into a candidate's
inference path or construct an unguarded baseline to manufacture a quality improvement.

The remaining named action dispatch,learned task reader/control,actual evidence-status
bridge and nine-family comparative Gate evaluation remain separate work. No existing
code,checkpoint,preregistration or negative result is changed by this opt-in module.
