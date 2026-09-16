# Gate E structured evaluation contract v0.1

Recorded 2026-09-17 JST following the user's instruction to proceed.
**Scope / metric design contract. Not a final numerical preregistration or a Gate verdict.**
C167 remains ACCEPTED PASS; C160 remains ACCEPTED VALID NEGATIVE; Gate E NOT PASSED.
C168 is a separately preregistered input diagnostic, not this final evaluation.

## 1. Authority and claim

Basis: `development-roadmap-v0.5.md` section7, `information-acquisition.md`,
`gate-e-acceptance-gap-audit-after-c167.md`, and accepted C151-C167 evidence.
The roadmap's five criteria are retained, not replaced by accumulating local PASS results.
New decisions below operationalize a **bounded structured-task** evaluation. They are
forward-looking choices, not capabilities inferred from the old logs.

A future PASS would mean that the registered candidate uses sufficient evidence,
acquires answer-critical information when useful and permitted, avoids unnecessary
acquisition/questioning, preserves useful answer coverage, and respects runtime limits
on the declared finite task suite. It would not establish general language mastery.

General language generation, Vision, FOLD-R capsule integration, long-context prefix
reuse, arbitrary durable revisions/retractions and production rollout are not added
as implicit Gate E requirements. Structured ASK_USER selection is not fluent question
generation. Simulated OBSERVE is not image recognition.

## 2. Finite scope

Use Boolean structured tasks with at most four fact variables and at most three binary
AND/OR operators; NOT may apply to leaves. Names, expression, known facts and evidence
metadata are visible. Missing values are not present in candidate inputs. The exact
expression inventory and split sizes must be locked in the later deciding manifest.
Facts carry record identity, provenance, observation time/revision and validity state.
A changed or absent fact is not automatically false. A conclusion derivable from known
facts is not an observation of the unknown fact.

The following **nine families** are the complete family-level scope for v0.1:

| Family | Required comparison |
|---|---|
| Sufficient / already known | Correct resolution without reacquiring or reasking known items. |
| Answer-critical hidden fact | Same visible input, different hidden completions; one permitted observation resolves the distinction. |
| Conclusion-irrelevant missing fact | Unobserved fields vary while the conclusion stays fixed; no unnecessary acquisition. |
| Conflicting evidence | Same-target/time competing observations; clarify or preserve conflict rather than silently choosing. |
| Stale evidence | Explicit freshness metadata; use a current permitted observation or return the remaining limitation. |
| Noisy / malformed evidence | Declared reliability/validation cases; do not treat invalid payloads as observations. |
| Unavailable acquisition | Missing delivery, permission denial and exhausted acquisition budget, with matched available controls. |
| Sufficient but reasoning-hard | All needed facts visible; bounded multistep expressions need computation, not fabricated missing information. |
| User-only information | A structured field can only be requested from the user interface; ASK_USER selects that field and avoids repeated requests. |

These are task-level semantics within a fixed episode, not a new durable memory system.
Families and valid examples must not be removed after a deciding result. Any expansion
requires a new contract version; failures of an old version remain accepted evidence.

## 3. Baselines and shared conditions

Register three policies: the candidate; a no-new-acquisition/internal-compute baseline;
and a simple fixed acquisition policy that requests unobserved task fields in canonical
visible-name order until resolved, unavailable or budget-limited. The latter must not
receive necessity labels or hidden values. An always-unresolved policy is a diagnostic
collapse control, not the main quality baseline.

Use the same visible inputs, permitted evidence, time/scope rules, tool envelopes,
runtime guards, maximum internal/observational budgets and scoring for each policy.
Missing actions for a baseline are explicitly disabled, not simulated as successful
retrieval. Specify and account for any symbolic evaluator or answer component shared
with a baseline; do not label a hand-coded solver as learned FOLD reasoning.

Do not construct an artificially unguarded baseline simply to make hallucination look
better. Measure both proposed assertions before a common guard and emitted assertions
after it. If the baseline is already at a zero-assertion-error floor, strict reduction
cannot be demonstrated; the final manifest must state the predeclared floor rule or
mark that comparative claim not demonstrated, rather than manufacturing a positive win.

## 4. Metrics and denominators

Report every family, matched condition and a macro-average across the nine families.
Never hide a failed family in a larger easy family. Report the raw numerator/denominator.

- **Unsupported assertion:** an asserted fact/conclusion not entailed by admissible
  observations and the declared task rules. Record pre-guard and post-guard counts,
  per-episode rates, and the rate among assertions. A guessed true bit can still be
  unsupported. A valid derived result is not hallucination merely because B is unknown.
- **Useful correct resolution:** correct task conclusions divided by all cases, plus
  the same ratio on cases answerable using the permitted episode budget. Wrong record
  identity, source binding or missing required proof is an error even if the bit matches.
- **Answer coverage / wrong abstention:** answered portions and unjustified abstentions,
  separately from correctness. UNRESOLVED is not bit0, nonexistence or a correct answer.
- **Acquisition benefit:** paired pre/post useful correctness on cases whose necessary
  information is available; include failure cases and record gain versus internal-only.
- **Unnecessary acquisition / questions:** attempts, executions, duplicate requests and
  user turns per registered opportunity. Necessity labels are evaluator-only; an item
  being absent does not alone make its acquisition necessary.
- **Hard boundaries / costs:** permission/budget violations; observation/provenance
  corruption; hypothesis-to-observation promotion; paid internal steps, acquisitions,
  adapter/IO calls, scanned candidates and wall-clock. A blocked proposal and an
  executed forbidden operation are distinct metrics.

A logical result must use a future explicitly derived-result contract with supporting
references; do not repurpose C159's OBSERVED_VALUE to call an AND/OR conclusion an
observed B. This output contract is not implemented by C168.

## 5. Relation to the five roadmap properties

Keep the first criterion's original wording, 「必要情報がある場合、内部反復だけで
架空の事実を生成する率が下がる。」. For measurement distinguish (a) already observed
sufficient information, (b) externally available but not yet observed critical facts,
and (c) unavailable facts. Report all three; do not silently switch the denominator.
Compare unsupported assertion rates with internal-only under common guard conditions.

The second property uses paired pre/post resolution gain. The third uses known-item
reasking and unnecessary-request rates versus the fixed policy. The fourth requires
mixed-suite and per-family useful coverage, not just selective accuracy. The fifth
requires separation of proposal from execution and zero hard permission violations
in the declared suite; acquisition-budget violations must also be zero.

## 6. Data separation and final registration boundary

C151-C167 cases are development/regression evidence, not a new independent holdout.
C168's four logical cases are also explicitly development diagnostics. A future split
manifest must identify independent task/assignment/template units and group paired
hidden completions into one split. Renaming variables is not independent semantic
replication. No test labels may enter a ranker, dependency channel, query, memory index
or model-visible metadata.

**Fixed now:** scope above, baselines, metric meanings/denominators, per-family reporting,
zero hard violations, no leakage, preservation of negatives, later-stage exclusions.

**Required before any deciding run:** candidate code/checkpoint identity; exact fixture
and split hashes; sample counts and dependence units; a separate baseline-development
measurement; numerical improvement/noninferiority/coverage margins; paired/statistical
rules and multiplicity treatment where applicable; budget values; output schema;
source/fault schedules; stopping and invalidity rules. These are NOT filled with
arbitrary97%/99% cutoffs. Until all exist, final evaluation readiness is **BLOCKED**,
not provisionally passed. No final holdout evaluation or training is launched here.

Then freeze the deciding manifest, execute once under that identity and judge.
Valid negatives remain results. A changed candidate needs separate evidence; a broken
execution retries the same registered number without moving the scientific boundary.

## 7. Immediate experiment boundary

C168 checks one prerequisite: whether the existing selected-record-to-Controller path
carries the visible distinctions required for necessity discrimination. It adds no
expression encoder, necessity head, answer solver, new checkpoint or dynamic memory.
See `experiment-ledger-addendum-c168-preregistration.md`. Further C numbers are not
registered until C168 is judged and ledger/handoff updated. The remaining C count is
unknown; this finite scope is not a promise of a fixed number of experiments.
