# C164 preregistration — Live query missing delivery

Registered 2026-09-16 JST, after C163 was formally accepted and recorded in commit `5b462d453ed1c6f826787c08be1cb1cebe15f847`.
C163 verdict: `experiment-ledger-addendum-c163-c164.md`. This document does not revise that verdict or the C160 negative.

## Formal state

**C164 — ACTIVE / NOT YET JUDGED**.
Experiment `C164-v5e-live-query-missing-delivery`.
Stage `V5-E-LIVE-QUERY-MISSING-DELIVERY`.
Branch `feat/sft-target-loss`. Use the commit containing this preregistration/module/tests/runner as explicit ExpectedHead, not the C163 execution HEAD.
Gate E remains **NOT PASSED**. No C165 is registered.

## One scientific question

Does the frozen query-originating live composition return a request-bound, payload-free **UNRESOLVED / MISSING_DELIVERY** when the actual fetched evidence is removed from its delivery envelope, while an otherwise matched normal-delivery continuation retains the accepted ANSWERED behavior?

C163 measured successful authorized cold recovery only. Its copied-fault emitter probes did not execute failed delivery through the entire query-originating cycle. C158's earlier preselected-record missing-delivery result does not establish this newer query-to-typed-result composition.

```text
raw query -> fresh frozen-ranker selection (shared prefix)
    |-- fresh cold state + real fetch + intact delivery
    |     -> admission/restoration -> readback -> ANSWER -> typed observed bit
    |
    `-- independent fresh cold state + real fetch + evidence removed from delivery
          -> MISSING admission -> reobserve unresolved -> STOP -> typed UNRESOLVED
```

## Changed / held-constant variables

Changed scientific variable: **transport evidence delivery only**.
The normal callback returns the fetched Delivery object. The missing callback returns `replace(fetched, evidence=None)`, retaining request/scope/epoch/generation/stats. It does not return a bare None envelope, bypass the real fetch, modify a corpus, invent an exact-search miss, or change authority/budgets.

Held constant: all 24 C151 rankers and three C157 Controllers/checkpoints; same 1728 queries, 64 descriptors, feature vocabulary, two original C152 layouts, ranker CUDA float32/highest arithmetic, CPU Controller/two threads, original query-index-modulo-three router assignment, source-state iteration rule, selected-reference removal, initial stale bit `query_index % 2`, permission=true, budget(3 internal,1 acquisition), evidence clock/revision=1, unchanged C158 cycle and C163 terminal adapter/C159 emitter. The other 63 references remain. No model action override or fallback answer is allowed.

Training split: none; no new training.
Evaluation split: the same inspected C151 manifest, all original head/arm/layout/query combinations. No new language/task generalization claim.
Fresh seeds: **0**. Training steps: **0**.
Production runtime change: **none**. All new work is diagnostic-only.
Request IDs use `C164|seed|arm|layout|condition|case_id` for disjoint identity. The condition string is not a learned Controller feature, target label or policy input. Scientific condition/expected action/value/semantic labels enter the evaluator only; the cycle receives a transport callback.

## Paired-prefix execution and accounting

Compute **82944 fresh live rankings**, one for every 24-ranker x 2-layout x 1728-query combination. Each live selection feeds two separately executed cold continuations in fixed order: COLD_RECOVER, then COLD_MISSING_DELIVERY. They receive separate fresh WorkingState, BudgetState and cold EvidenceState constructions; neither adopts the other's final state, inbox, observations, output or readback. Immutable models/source snapshots are shared.

The shared ranking prefix is deliberate: this is **82944 matched pairs / 165888 live branch episodes**, not 165888 independent raw queries or twice the ranker scoring work. No saved C163 prediction replaces live selection.

| Metric | Normal delivery | Missing evidence delivery | Total |
|---|---:|---:|---:|
| Fresh cold branch episodes | 82944 | 82944 | 165888 |
| Controller decisions | 165888 | 165888 | 331776 |
| Authorized acquisitions | 82944 | 82944 | 165888 |
| Published/restored refs | 82944 | 0 | 82944 |
| Exact64 adapter calls | 165888 | 82944 | 248832 |
| Vectors scanned | 10616832 | 5308416 | 15925248 |
| Typed ANSWERED | 82944 | 0 | 82944 |
| Typed UNRESOLVED / MISSING_DELIVERY | 0 | 82944 | 82944 |
| Episodes per assigned Controller | 27648 each | 27648 each | 55296 each |

Shared live candidate scores: **5308416**. Ranker replay: **41472** plus **288 original12** cases. Old C159 emission replay: **6528**, separately accounted.
Expected raw actions total: RETRIEVE(2)=165888, ANSWER(0)=82944, STOP(5)=82944. No hardcoded expected action replaces a raw learned proposal.

Normal sequence: REFERENCE_UNBOUND -> RESOLVED, actions [2,0]. Missing sequence: REFERENCE_UNBOUND -> REFERENCE_UNBOUND, actions [2,5]. Both consume two internal steps and one acquisition, leaving budget(1,0). Missing delivery leaves the selected reference absent, no inbox publication, no readback, final value/reference None, and final presence/payload channels [0,0]. The pre-delivery trace still records the real fetched bit; that debug evidence is not an authorized returned answer.

The terminal UNRESOLVED output retains schema/request/scope identity; value, record_key, source_id, evidence_time and revision must all be None. It is not a bit zero, proof of nonexistence, semantic irrelevance judgment, or permission denial. Its `semantic_correct` is **null / not applicable**, not zero accuracy and not a new semantic success.

Normal branch per arm/layout: 20736 correctly bound outputs, semantic_correct **WITHIN_FACTOR 20727 / GLOBAL_CONCEPT 20736**. Preserve the known nine wrong selections per layout, including wrong-record same-bit cases. Normal observed zero/one totals remain **34992/47952**.

## Emitter controls and preservation

Reuse the unchanged C163 AuditedEmitter on each newly produced branch result: **165888 native controls + 165888 adapted outputs**. Every native tuple control must still reject MALFORMED_EVIDENCE; adapted normal outputs must be ANSWERED and adapted missing outputs UNRESOLVED.

Reuse the six native-input copied-fault guards on the first encountered source-record identity: **128 identities x 6 = 768 guard calls**. Because the normal branch is always first, representatives come from its first encounter, chosen independently of correctness/value. Never replace a failed representative with a later successful one; C163's unsuccessful probe records remain scientific failures. The same wrong-request/provenance/payload/ungrounded-answer/clock/duplicate-reference guards must retain their reasons and no-payload behavior.

New emitter calls total **332544**, separate from old C159's 6528 replay calls. These controls add diagnostic cost; no production-latency claim is made.

All historical core/C158/C159/C160/C161/C162/C163 source Git blobs remain fixed. Authoritative EvidenceState stays tuple-backed. No global monkeypatch is used: a local API copy substitutes only the explicit delivery callback while forwarding the other C158 cycle arguments unchanged.

## Prerequisite / artifacts

Pin accepted C163 summary:
`runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`
SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
Execution identity `d3cecf1c1221d2119a2e6ab172c69770bde46788`.

Validate its full accepted profile, all 48 live trace hashes/sizes, plan/controls and every consumed input hash. This verifies artifact identity; it is not a new replay of all C163 traces. Locate C159 and C151 only through this pinned input map. Reuse the established C160/C163 source loader, C159 recorded emission replay, C151 ranker replay, original catalogs and actual C153/C154/C155/C156 execution dependencies. Load frozen Controllers safely and check fingerprints; do not repeat the old C157 1990656-decision replay or regenerate missing artifacts.

Save a fixed plan with source/checkpoint identities, transport contrast, router schedule and all counts **before new measurements**. Save all branches, including failures, to **48 new gzip JSONL files x 3456 rows**. Each row includes condition, query/selection identity, raw actions/logits, compact final-state digest/count, native/adapted output checks, cycle assessment, output assessment and pass bit. Save guard records separately. Aggregate by condition/arm/layout/router and record independent underlying adapter-meter totals, not just inferred costs.

Rehash all consumed inputs and historical source blobs after execution; runner independently repeats input/blob/tree/HEAD postchecks. Use a fresh run directory; do not overwrite old artifacts. CUDA allocator peaks and total wall-clock are diagnostic fields, not whole-device footprint, independent quality evidence or production performance.

## PASS / VALID NEGATIVE / INVALID

**PASS:** full registered paired coverage; normal branch satisfies the **unchanged original C160 success gate** and frozen semantic boundary; missing branch satisfies every existing C158 missing-delivery cycle assessment and exact no-payload typed terminal contract; both have positive finite expected-action margins and exact action/budget/cost/router totals. All underlying meters agree, native controls/type/content/input checks and all 768 guards pass; no measured mutation/serialization failure; input/code/HEAD protections pass. Supports controlled query-originating UNRESOLVED for post-fetch evidence non-delivery, not general safety or Gate E completion.

**ACCEPTED VALID NEGATIVE / FAIL:** valid sources and execution, but finite wrong actions, answer leaks, incorrect UNRESOLVED reason/identity, publication despite missing delivery, hidden readback, wrong costs, changed semantic results, guard defects or measured model/output/content mutation. Save all outcomes and use CLI exit zero for valid scientific FAIL. Never change thresholds/models/coverage to make it pass.

**INVALID / RETRY C164:** missing/changed prerequisite files, wrong identity/schema/hash/code, checkpoint or source-replay mismatch, nonfinite arithmetic, unexpected execution exception, incomplete execution or outer tree/HEAD/postcheck failure. Restore validity and retry the same C164 under the same scientific conditions. Never recreate C160/C163 sources or relabel an accepted negative.

## Implementation and reviewer validation

Files:
- `fold_lm/v05_benchmarks/gate_e_c164_live_missing_delivery.py`
- `tests_lm/test_v05_c164_live_missing_delivery.py`
- `tools/run_c164.ps1`

Expected focused regression: **638 = 614 previous + 24 new helper tests**. The new test file includes five actual-C158-cycle/adapter wiring test methods with controlled runtime callbacks/test routers, plus 19 dependency-light contract tests. These are not formal learned-model integration measurements.

Reviewer compiled both new Python files and executed **19/19 dependency-light tests successfully** using a local harness with inspected contract excerpts/test doubles. The five actual dependency-wiring test methods were **not executed in the reviewer environment** because a complete repository checkout/dependency tree was unavailable. The reviewer does not claim byte-identical imports of the full historical modules or 24/24 execution. The full 638-test user regression, real artifact-backed CUDA/CPU experiment and Windows PowerShell script remain unexecuted. No C164 scientific result has been measured or claimed.

Runner uses `.venv-py31315\Scripts\python.exe`, explicit ExpectedHead, hash-pinned C163/C37/fixture and a fresh output directory. Progress includes `[C164] lineage/replay verified`, head/arm/layout/query counts, branch_episodes/failed/remaining, `=== C164 RESULT ===`, and `=== C164 POSTCHECK ===`.

Stop after C164 execution. Judge, interpret, audit and update ledger/handoff before considering C165. C160 remains ACCEPTED VALID NEGATIVE; C163 ACCEPTED PASS; Gate E NOT PASSED. Multi-Axis and PC-ALM/FHLC remain independent tracks.
