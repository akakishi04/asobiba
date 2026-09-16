# C159 verdict -> C160 live query-to-terminal-result composition

Reviewed/preregistered 2026-09-16 JST. V5-E diagnostic integration only.

## C159 — ACCEPTED PASS

Execution commit: `741ca66e93e389ffc7e90688dc924e04695da778`.
Evidence: user's complete console log `貼り付けられたテキスト（1 点）(20260915-234901).txt`.
Reviewer-computed uploaded-log SHA256: `07cad7d3d8ea27d56b3626c01737cc23b242c029513ac4f96fe536f3f945832b`.
Local report: `runs/c159-v5e-terminal-result-9e2b2e3e1f9c42bda1f33d7d49fa3cd7/summary.json`.
Runner-printed report SHA256: `522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6`.
The reviewer parsed the uploaded console JSON and checked registered counts and postchecks against the source/plan. Full local terminal JSONL and upstream artifacts were not uploaded for independent replay. The uploaded-log hash is NOT the report hash.

| Measurement | Observed |
|---|---:|
| Focused regression | 508/508 |
| Source episodes / emitter calls | 1,920 / 6,528 |
| Base ANSWERED / UNRESOLVED | 768 / 1,152 |
| Observed answer zero / one | 324 / 444 |
| Unresolved missing delivery / permission / budget | 384 / 384 / 384 |
| WRONG_REQUEST rejected | 1,920 |
| WRONG_PROVENANCE rejected | 768 |
| PAYLOAD_DISAGREEMENT rejected | 768 |
| FORCED_UNGROUNDED_ANSWER rejected | 1,152 |
| Failed cases / mutations / JSON failures | 0 / 0 / 0 |

All reported source/protected/tree/HEAD checks pass and `run_execution_valid=True`. The old C145 scalar warning occurs in a passing test, not in C159 output validation. Reported total diagnostic time 3.6804853 seconds is not model inference latency. The three output files share one content hash because the deterministic record-level returns/controls match; each remains bound to its different source-router trace in report metadata. This is not three independent language tasks.

Supported: trusted recorded C158 terminal readback becomes a request/snapshot-bound typed result; observed zero is not unresolved; four registered output faults are rejected without usable payload. Not supported: a live model/adapter cycle in this run, a learned answer head, semantic relevance recognition, language generation, cryptographic source authentication or durable/network publication. C159's ANSWERED is a validated copy of an observed bit. Gate E remains NOT PASSED.

## C160 — ACTIVE, awaiting user execution

Experiment: `C160-v5e-live-query-to-terminal-result`.
Stage: `V5-E-LIVE-QUERY-TO-TERMINAL-RESULT`.

**Question:** with all learned weights fixed, can the existing query selector, authorized recovery cycle and typed emitter execute together from raw query text to an observed-bit result, preserving selected identity and the known relevance-error boundary?

The changed variable is **execution composition**: live query selection feeds the existing C158 cold-recovery cycle, whose fresh terminal state immediately feeds the existing C159 emitter. This is not new model training or a component redesign. C159 validated recorded outputs; C158 started from preselected records. Those limitations are replaced by one same-process, query-originating path on the existing controlled task.

```text
original query text + current persisted catalog descriptors
-> frozen C151 SharedRetrievalContentHead (C147 composition)
-> actual argmax candidate, not an expected address
-> new diagnostic request bound to that selected handle/snapshot
-> live C158 COLD_RECOVER cycle using a frozen C157 Controller
-> real exact64 acquisition -> C153 admission -> C154 projection
-> C155/C156 exact64 readback and working-state refresh
-> same frozen Controller ANSWER action -> C159 emit_terminal
-> typed observed 0/1 with request/source binding
```

The query ID is retained only as identity, never decoded into a target or passed into the neural selectors. Expected descriptor/key/payload are used only in source replay checks and post-execution evaluation. There is no target-key correction, semantic oracle, inference alias dictionary or fallback to a stored query prediction. Snapshot.values is evaluator-only; it is never passed to recovery or output emission.

### Fixed models, data and coverage

- All **24 C151 rankers**, both WITHIN_FACTOR and GLOBAL_CONCEPT, seeds 20261721..20261732; identical frozen checkpoints, 49 features/hidden 64/residual 1.
- All **three C157 Controllers**, seeds 20261741..20261743, frozen; no ranker or router training and zero fresh seeds.
- Same pinned C151 manifest: 64 descriptors x 27 alias expressions = 1,728 queries, same training-only fixture vocabulary. This remains the repeatedly inspected synthetic task, not new language/task generalization.
- Both original C152 persisted layouts/catalogs, not regenerated copies. C153's protected input map supplies the catalog hashes that later readback experiments no longer needed.
- Router assignment is **zero-based manifest query index modulo 3**, identical across ranker arms/seeds/layouts. Each ranker sees all three routers, 576 queries/router/layout. Each query executes with ONE router, not the full three-router Cartesian product. Every descriptor's 27 variants give nine queries per router. No score/correctness-dependent assignment.
- Only **authorized COLD_RECOVER** is newly run. Denial, missing delivery, warm-state and exhausted-budget behavior retain their earlier scoped evidence, not new C160 measurements.
- Cold state removes only the selected reference from a trusted full 64-reference state; other 63 refs remain. This is not an initially empty knowledge/world state. Previous working presence and alternating stale bit must be cleared before the Controller's first proposal.
- Same C158 maximum one authorized acquisition and three decisions; expected action sequence RETRIEVE -> ANSWER, two internal debits and one acquisition debit. Fixed snapshot evidence time/revision remain 1. No new external-world observation epoch.
- Rankers run CUDA float32/highest; Controllers run CPU float32, two threads, as in their accepted reference paths. Keep one ranker at a time, not all 24 resident. No production changes.

### Prerequisite and replay checks

Pin C159/C151 report hashes; locate C158/C157/C154/C153 reports only through their trusted ancestor hashes. Reaggregate all 1,920 C158 stored episodes with the existing C159 loader, and replay all 6,528 deterministic C159 emissions against all three stored terminal JSONL files. This is output/source verification, not an old live-loop rerun.

Use the existing C155 loader to reaggregate all 48 source-state streams. Same-layout reference maps must agree; no representative is chosen using a payload or correctness score. Verify original catalog/record hashes, all source checkpoint bytes/configurations/fingerprints and the C151 manifest/split plan against existing generators. Replay all 41,472 C151 rankings and 288 original12 results with the original float32 CUDA arithmetic: exact predictions/rival identities, scores/margins atol 1e-5. Then separately recompute live candidate scores in each disk catalog's actual order. Reordered selection identity must match the reproduced ranker; no prediction substitution occurs.

Save `query-cycle-plan.json` before any new ranking/cycle measurement, with the pinned manifest, all model IDs, layouts, one scenario and router assignment. C157's old 1,990,656-row action evaluation is NOT separately rerun here; unchanged Controller bytes/fingerprints and earlier accepted replay remain the reference. Missing or changed inputs are not reconstructed, migrated or silently rebound.

### Registered size and interpretation

```text
24 rankers x 2 layouts x 1,728 queries = 82,944 live query episodes
Live ranker candidate scores = 82,944 x 64 = 5,308,416
Expected live Controller decisions / internal debits = 165,888
Expected authorized acquisitions / reference restorations = 82,944 each
Expected adapter calls = 165,888 (acquisition + readback)
Expected vectors scanned by adapter = 10,616,832
Expected typed ANSWERED outputs = 82,944
Expected episodes per frozen Controller = 27,648
```

The old ranking replay and C159 emission replay are reported separately from new measurements. The adapter is independently metered; per-query duplicate record reads are not collapsed into a payload cache. Descriptor/unit vector computation retains the existing C147 behavior. Exact scans and these large repeated counts are not evidence of efficient production retrieval or many independent reasoning tasks.

For EACH layout, all 20,736 outputs/arm must preserve selected record/source/value. GLOBAL_CONCEPT must additionally have 20,736 correct target-record outputs; WITHIN_FACTOR must preserve the original 20,727 correct / 9 irrelevant outputs. Across both layouts this is 18 known semantic errors, not 18 newly discovered failures. Matching an incidental 0/1 payload from a wrong record is still semantically wrong. `failed_episodes` measures cycle/output integrity, while `arms.*.*.semantic_correct` measures target correctness; the final gate checks BOTH. A downstream oracle "repair" of the control errors is not a success.

The emitter is deterministic, not a learned answer-content model. This pipeline tests a single-record observed-bit lookup with trusted snapshot metadata, not free-form answering, relational reasoning, open-set detection, relevance-based abstention or unknown-token understanding. The standard Controller still sees presence/value/availability channels; it cannot repair an irrelevant ranker choice.

Save per-query text/ID, selected key/position, assigned router, every live action/logit/working state, runtime costs, admission/projection results, typed output and assessments in 48 gzip JSONL files with hashes/sizes. Avoid serializing all 64 final refs per query: keep full decision traces plus final-state digest/reference count, with reconstruction source states pinned. These are diagnostic artifacts, not production session storage or a public schema.

### PASS / FAIL / INVALID

**PASS:** all new live cycles preserve registered action sequences, positive finite Controller margins, selected identity/provenance/payload, clocks, budgets and exact costs; all typed outputs are bound and JSON-stable; all model/output/input protections pass. All source-scope semantic counts above must remain exact. All 24 rankers, two layouts and three assigned routers are required.

**VALID NEGATIVE / FAIL:** valid setup but finite wrong live actions, wrong output/clock/budget/cost, state/output/model mutation, missing publication or end-to-end relevance counts not matching registered boundaries. Preserve per-case outputs and return scientific FAIL with CLI exit 0. Do not retrain, select checkpoints, shrink coverage or rewrite the gate after execution.

**INVALID:** wrong source/hash/schema/lineage/fixture, incompatible checkpoint, missing snapshot, source-output/ranker replay mismatch, nonfinite arithmetic or unexpected execution/outer guard exception. Retry C160 after restoring validity, not by regenerating missing artifacts. C159's accepted scope stays unchanged.

Gate E remains NOT PASSED regardless of this one result. PC-ALM/FHLC and Multi-Axis remain independent tracks. C161 is not registered.

## Reviewer verification

**38/38 new CPU helper tests passed** under PyTorch 2.10.0+cpu; Python compilation passed. Tests cover exhaustive-shaped toy ranking/reordering, labels excluded from selector interfaces, deterministic router coverage, request/selected-ref construction, controlled cycle/emitter wiring, independent read counters, preservation of wrong/rejected outputs, zero/None and identity/relevance separation, compact trace immutability and strict gate boundaries. Fabricated 1,920 source rows exercise all 6,528 output-replay comparisons and detect byte tampering and internally inconsistent rehashed output.

Test doubles isolate the NEW wiring. They do not exercise real C151 weights, C157 weights or the complete C153-C159 dependency chain. Existing helper signatures/usage were inspected at the pinned source commit; no full dependency archive or user checkpoint/state artifacts were locally available. No formal C160 result or independent rerun of C159 is claimed. Full **546 tests = 508 + 38**, real CUDA/CPU integration and PowerShell execution remain unexecuted by the reviewer.
