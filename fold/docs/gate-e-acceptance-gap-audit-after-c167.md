# Gate E acceptance-gap audit after C167

Date: 2026-09-16 JST.
**Status: DESIGN REVIEW / DRAFT NEXT EXPERIMENT, not preregistration, not a Gate verdict.**
C167 was accepted in `5b0f37028f82e987e399da60bf40c17e69de5fcf` before this document.
C167 ACCEPTED PASS; C160 ACCEPTED VALID NEGATIVE; Gate E NOT PASSED.
**C168 is NOT REGISTERED. No new benchmark, training or runtime modification is authorized by this draft.**

## 1. Sources and authority

Read at execution ref `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`:

- `development-roadmap-v0.5.md`, especially opening principle and V5-E/V5-F/V5-G/V5-H boundaries.
- `information-acquisition.md`, explicitly a capability design rather than implemented API.
- `experiment-ledger-addendum-c167-preregistration.md` and accepted C163-C167 chain.
- `../fold_lm/v05_benchmarks/gate_e_c167_live_warm_reference.py`.
- `../fold_lm/v05_benchmarks/gate_e_c160_live_query_result.py`, `execute_selected`.
- `../fold_lm/v05_benchmarks/gate_e_c156_request_reobservation.py`, `reobserve` and `control_inputs`.

Measured results are in `experiment-ledger-addendum-c167-c168.md` and its pinned uploaded log/report. This document maps evidence and proposes future measurements; it does not silently expand or replace the roadmap.

## 2. Roadmap criteria and what is actually supported

The roadmap says numerical thresholds are fixed after baseline acquisition and BEFORE the final comparison. It does not specify a fixed remaining C count or say that C167 is the final Gate E trial.

| Gate E property, original wording | Accepted evidence relevant to it | Remaining gap |
|---|---|---|
| 必要情報がある場合、内部反復だけで架空の事実を生成する率が下がる。 | C159/C163-C166 validate typed observed-value binding and no payload on tested unavailable paths. | No same-suite comparative hallucination-rate measurement against an internal-compute/no-acquisition baseline is supplied by C167. Operationalize the roadmap wording explicitly before final measurement; do not silently substitute a different condition. |
| 取得後の最終品質が取得前より改善する。 | Cold recovery produces bound outputs; failed delivery/denied/exhausted cases stop without payload. | Define matched pre/post quality, denominator and comparable baseline. Separate intervention outcomes from an independently measured final Gate comparison. |
| 既知情報の聞き直しと不要質問が対照より増えない。 | C167 warm references avoid redundant acquisition with matched output quality. | Human questioning is not exercised. Missing information irrelevant to the conclusion, task ambiguity and query-criticality inference are not established by warm reference presence. |
| 全てを「分かりません」にしてcoverageを捨てる解へ崩壊しない。 | Answerable branches in C163-C167 answer; unavailable branches in C164-C166 stop as registered. | Define useful resolution/coverage across a mixed task suite and across each task family; do not score abstention as semantic correctness. |
| model proposalとruntime permissionが分離される。 | C165 directly measures proposed RETRIEVE with zero denied acquisition; C166 separately measures acquisition-budget exhaustion. | Preserve these hard constraints in the eventual combined evaluation. This is runtime enforcement, not proof that the model understands arbitrary permission or cost policies. |

Gate E's listed data families also include hidden-condition pairs, one-observation resolution, conclusion-irrelevant missing fields, stale/conflicting/noisy/unavailable evidence and information-sufficient but reasoning-hard cases. Local reference existence and provenance tests do not automatically cover every one of those semantic cases.

General natural-language mastery, Vision, arbitrary durable memory updates and warm long-context session reuse must not be added as new implicit Gate E prerequisites. They have separate later-stage/design boundaries. A scoped structured-task Gate can be meaningful, but its claim and exclusions must be explicit; ASK_USER routing must not be confused with full natural-language question generation.

## 3. Source finding: dependency is currently stipulated, not inferred

C156 `control_inputs` documents channels `base, dependency, evidence_present, value`, followed by untouched data. `reobserve` replaces only presence/value channels2/3 and advances the internal step.

C160 `execute_selected` constructs:

```python
np.array([[1., 1., 1., float(old_bit), .125, -.25, .375, -.5]])
```

Therefore dependency channel1 is initialized to1. C167 reuses this helper and changes only initial selected-reference membership. Its cycle wrapper forwards the working input unchanged. This is consistent with C167's preregistered task, not a newly discovered execution defect.

**Inference limited to the inspected path:** C167 demonstrates reacting to the presence of a selected, stipulated-required reference. It does not demonstrate deriving whether a missing item matters to the query. Simply setting dependency=0 from an evaluator's correct relevance label would test a downstream router under oracle metadata, not learned necessity judgment.

This source finding does not claim all earlier C experiments lack dependency variation, nor that FOLD's architecture can never learn it. It concerns this query-originating composition path.

## 4. Finite final-evaluation contract to specify next

This is a proposed contract structure, not numerical preregistration.

### Task scope and baselines

Use a bounded structured task family first. Declare visible inputs, permitted tools, evidence sources and time/scope semantics. Include each roadmap data family once in a finite coverage matrix; do not append new families after seeing the deciding results.

Compare the same candidate system against a no-acquisition/internal-compute baseline and a simple fixed acquisition policy with matched permission/budget ceilings. An always-unresolved policy is a degenerate-control reference, not a useful quality baseline. Which baselines are scientifically necessary must be fixed before the deciding run. Distinguish externally stipulated dependency features from features inferred from visible task content.

Historical C151-C167 fixtures/checkpoints may provide development and regression evidence. Reusing their cases is not an independent held-out generalization test. A new deciding fixture requires an explicit generation/split manifest; no new data or seeds are introduced by this draft.

### Metrics and denominators

Measure separately: unsupported factual assertions, bound task-answer quality, pre/post acquisition improvement, unnecessary acquisition/ASK_USER count, useful resolved coverage, wrong abstention on answerable cases, missingness reason, authority/budget violations, acquisition/internal-step/IO costs.
Report per family and paired condition, not only an overall average. A returned value with wrong record identity remains wrong. Ground-truth relevance/necessity belongs only in training labels or post-execution scoring. UNRESOLVED is neither bit0 nor a proof of nonexistence.

### Decision rules

Hard runtime violations should remain zero in the declared finite suite. A quality win must not be purchased by loss of coverage or unbounded calls. Comparative quality/hallucination/noninferiority margins, sample counts, pairing and statistical decision rules must be specified after a separate baseline-development measurement and before evaluating the deciding holdout. No arbitrary97%/99% cutoff is justified by C167.

A sufficient final declaration is a versioned manifest covering task families, implementation/checkpoints, baselines, metrics, denominators, numerical rules, exclusions and stopped-run handling. Then execute and judge that manifest. A valid negative is retained; it cannot trigger removal of failed families or relaxation of thresholds. Bug repair or a new candidate requires separately identified evidence, never relabeling the old run.

## 5. Next C candidate — task-necessity observability preflight

**Working design only: proposed C168, NOT REGISTERED / NO RUNNER.**
Proposed question: can the present query-to-Controller input representation distinguish a missing fact that changes the answer from a missing fact that does not, without a correct dependency label supplied by the evaluator?

This removes one limitation identified above: necessity is currently fixed in the harness. Do not simultaneously add new checkpoints, train a necessity head, change the emitter or introduce dynamic memory semantics.

### Illustrative paired task

Use a bounded logical task with visible expression `a OR b` and b unobserved:

- a=1: the answer is1 for either hidden value of b; acquiring b is unnecessary.
- a=0: the answer depends on b; acquisition is informative when allowed and available.

These are proposed task examples, not measured FOLD outputs. The truth-table evaluator supplies labels after input construction; it must not supply dependency or the hidden value to the model. To avoid inventing capabilities, a new visible-expression encoder is not assumed to exist. Whether the existing interface can legally carry the expression and known a is part of the preflight.

### Proposed method and controls

Construct a fixed finite case manifest BEFORE any new scoring. Track which visible task fields survive the current input path. Compare the actual model-visible tensors and runtime-visible availability across pairs. Count exact input equivalence classes with incompatible required actions; retain concrete counterexamples. Labels are consulted only after grouping.

A clearly labeled symbolic full-visible-input reference should distinguish the pairs, providing a task-validity control; it is not the learned model. A within-current-task control verifies that the original selected-bit cases still encode consistently. An input-collision diagnostic may not require any new model forward, training or retrieval, but exact counts and implementation must be registered before execution.

If two otherwise identical allowed/budgeted inputs require different actions, a deterministic Controller cannot distinguish them from those inputs. That is an interface-information limitation, not evidence that larger hidden width or longer training would solve it. Conversely, absence of such collisions in the finite set is only a necessary condition for a future learned solution, not proof that the current Controller already solves the task.

### Proposed verdict interpretation

- PASS would mean the registered finite cases are represented without conflicting required-action classes and all source/task-validity controls pass; it would NOT mean learned necessity discrimination or Gate E completion.
- VALID NEGATIVE would include a valid representation collision or systematic loss of an answer-critical visible field. Retain it before proposing a separate input-representation or learned-head intervention.
- INVALID would cover malformed fixtures, source/schema drift, evaluator leakage or incomplete execution; restore execution validity and retry the same registered C.

Exact fixture/schema, case counts, source pins, test count and runnable implementation are still unresolved. Therefore no C168 experiment ID/stage/ExpectedHead/command is finalized here. This is an actionable design boundary, not an active benchmark or a reason to rerun C167.

## 6. Planning correction and stop

The preceding chat's suggestion that Gate E is in its final few local trials is not supported by a fixed final-evaluation specification. The measured acquisition mechanism has advanced; the remaining experiment count and Gate acceptance date are unknown. Do not present percentages or a guaranteed number of Cs.

Next work is to finalize the bounded acceptance contract and the observability-preflight manifest. The review does not add a permanent new approval requirement: an agent may finish that concrete design and registration under the existing workflow, provided all scientific/implementation prerequisites are specified. No new run is requested by this document. C168 remains unregistered; C167 remains accepted; Gate E remains not passed. Multi-Axis and PC-ALM/FHLC remain separate tracks.
