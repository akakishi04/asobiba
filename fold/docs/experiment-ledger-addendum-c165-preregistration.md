# C165 preregistration — Live query runtime permission denial

Registered 2026-09-16 JST after C164 was formally accepted and the authoritative handoff was advanced through C164.
C164 verdict: `experiment-ledger-addendum-c164-c165.md`. This document does not revise C160-C164.

## Formal state

**C165 — ACTIVE / NOT YET JUDGED**.
Experiment `C165-v5e-live-query-permission-denied`.
Stage `V5-E-LIVE-QUERY-PERMISSION-DENIED`.
Branch `feat/sft-target-loss`. Use the final commit containing this preregistration/module/tests/runner/handoff update as explicit ExpectedHead.
Gate E remains **NOT PASSED**. No C166 is registered.

## One scientific question

When the frozen query-originating composition's learned Controller proposes RETRIEVE for the selected missing reference, does setting **runtime permission to false** block every acquisition/search/publication and lead, after reobservation, to request-bound payload-free `UNRESOLVED / PERMISSION_DENIED`, while an otherwise matched allowed continuation retains the accepted ANSWERED behavior?

This directly tests the V5-E separation between **model proposal** and **runtime permission** on the raw-query composition. C158 already measured permission denial after a record had been preselected; it did not establish the newer raw-query -> live selection -> typed terminal path. C164 measured transport loss only after an authorized real fetch; it did not exercise authority denial before acquisition.

```text
raw query -> fresh frozen-ranker selection (shared prefix)
    |-- Permission(True)
    |     -> learned RETRIEVE -> authorized fetch/admission/projection/readback
    |     -> learned ANSWER -> typed observed bit
    |
    `-- Permission(False)
          -> learned RETRIEVE -> runtime PERMISSION_DENIED
          -> zero adapter fetch/search, zero acquisition debit, zero publication
          -> reobserve still unbound -> learned STOP
          -> typed UNRESOLVED / PERMISSION_DENIED
```

## Changed / held-constant variables

Changed scientific variable: **`Permission.allowed` only**.

The historical C160 selected-record helper still constructs `Permission(True)`. C165 supplies a local diagnostic cycle wrapper that verifies this unchanged base permission and substitutes the preregistered Boolean condition immediately at the explicit C158 cycle boundary. Every other cycle argument, delivery callback and runtime dependency is forwarded unchanged. No global monkeypatch is used.

Held constant: all 24 C151 rankers and three C157 Controllers/checkpoints; same 1,728 raw queries, 64 descriptors, feature vocabulary, two original C152 layouts, CUDA float32/highest ranker arithmetic, CPU Controllers/two threads, query-index-modulo-three router assignment, source-state iteration, selected-reference removal, initial stale bit `query_index % 2`, budget `(3 internal, 1 acquisition)`, evidence time/revision=1, identity delivery callback, unchanged C158 cycle, C163 observations-only terminal normalization and unchanged C159 emitter. The other 63 references remain.

Training split: none. Evaluation split: unchanged inspected C151 manifest. Fresh seeds **0**. Training steps **0**. Production runtime change **none**. No target labels/expected payloads/scenario names enter the Controller or permission decision; those exist only in evaluator/request identity.

Request scopes use `C165|seed|arm|layout|condition`; the condition string is identity only and is not a learned input.

## Paired-prefix execution and accounting

Compute **82,944 fresh live rankings** = 24 frozen ranker heads x 2 layouts x 1,728 queries. Each selected result feeds two separate fresh cold continuations in fixed order: allowed, then permission-denied. They do not share final state, inbox, working state, budget or output.

This is **82,944 matched ranking prefixes / 165,888 branch episodes**, not 165,888 independent raw queries. No C164/C163 saved prediction is substituted for live ranking.

| Metric | Allowed | Permission denied | Total |
|---|---:|---:|---:|
| branch episodes | 82,944 | 82,944 | 165,888 |
| Controller decisions | 165,888 | 165,888 | 331,776 |
| executed acquisitions | 82,944 | **0** | 82,944 |
| publications/restorations | 82,944 | **0** | 82,944 |
| exact64 adapter calls | 165,888 | **0** | 165,888 |
| vectors scanned | 10,616,832 | **0** | 10,616,832 |
| typed ANSWERED | 82,944 | 0 | 82,944 |
| typed UNRESOLVED/PERMISSION_DENIED | 0 | 82,944 | 82,944 |
| episodes per Controller | 27,648 | 27,648 | 55,296 |

Shared candidate scores remain **5,308,416**. Prerequisite ranker replay remains **41,472 + 288 original12**. Old C159 replay remains **6,528 calls**, reported separately.

Expected raw actions over both branches: RETRIEVE(2)=165,888, ANSWER(0)=82,944, STOP(5)=82,944. No evaluator action override is allowed.

Allowed sequence: `REFERENCE_UNBOUND -> RESOLVED`, actions `[2,0]`, two reads, one acquisition, one publication, final acquisition budget 0.

Permission-denied sequence: `REFERENCE_UNBOUND -> REFERENCE_UNBOUND`, actions `[2,5]`; first-step authority exactly `PERMISSION_DENIED`; **no fetch is dispatched**, no adapter meter increments, acquisition budget remains 1, no inbox entry/publication/readback, selected reference remains absent, final value/reference are None, and final presence/payload channels are `[0,0]`.

Permission-denied output must be schema/request/scope-bound `UNRESOLVED / PERMISSION_DENIED` with `value`, `record_key`, `source_id`, `evidence_time`, `revision` all None. It is not bit zero, proof of absence, transport failure, budget failure or semantic relevance abstention. Its semantic correctness is null/not-applicable.

Allowed branch semantic boundary remains exactly: every arm/layout 20,736 bound outputs; WITHIN_FACTOR 20,727 semantic correct per layout; GLOBAL_CONCEPT 20,736 per layout. Preserve the known nine wrong selections per layout and zero/one totals 34,992/47,952.

## Emitter controls and protection

Use unchanged C163 `AuditedEmitter` on each new branch result: **165,888 native tuple controls + 165,888 adapted candidate calls**. Every native control must still reject `MALFORMED_EVIDENCE`; adapted allowed outputs must be ANSWERED and adapted denied outputs must be UNRESOLVED/PERMISSION_DENIED.

As in C164, run six copied-fault guard probes on the first encountered normal source/record identity: 128 identities x 6 = **768 guard calls**. Normal branch executes first, so guard representatives are not selected after observing a denial outcome. Failed representatives are preserved as failures, never replaced.

New emitter calls total **332,544**, separate from the 6,528 historical C159 replay calls.

Historical core/C158/C159/C160/C161/C162/C163/C164 source Git blobs remain fixed. Authoritative EvidenceState remains tuple-backed; the existing diagnostic terminal normalization remains explicit and unchanged.

## Prerequisites / artifacts

Pin accepted C164 summary:
`runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`
SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
C164 execution identity `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`.

Validate the full C164 accepted profile, all 48 trace hashes/sizes, plan/controls and every consumed input hash. Locate and revalidate the pinned C163 ancestor, then reuse the established source loader, C159's 6,528 recorded-emission replay, C151's 41,472 + 288 ranking replay, original catalogs and actual C153-C156 dependencies. Load frozen Controllers and check fingerprints. Do not repeat the old 1,990,656-row C157 decision replay and do not regenerate missing artifacts.

Write the fixed permission plan before new measurement. Save **48 gzip trace files x 3,456 rows**, preserving both branch outcomes, full Controller actions/logits, authority result, compact final-state digest/count, emitter controls, cycle/output assessments and pass bit. Save the 768 guard records separately.

Rehash all consumed inputs, historical Git blobs, tracked tree and execution HEAD after measurement. Use a fresh run directory and never overwrite prior runs.

## PASS / VALID NEGATIVE / INVALID

**PASS:** full registered paired coverage; allowed branch preserves the unchanged C160/C163 successful path and frozen semantic boundary; denied branch passes the existing C158 permission-denied cycle assessment and exact typed no-payload contract; all 82,944 denied branches show authority=`PERMISSION_DENIED`, adapter calls=0, executed acquisitions=0, acquisition budget preserved, publications/readback=0, positive finite expected-action margins and action `[2,5]`. All independent meter totals, native controls, content/input checks, 768 guards, input/code/tree/HEAD protections pass with zero measured mutation/serialization defects.

PASS supports runtime permission enforcement on this fixed query-originating synthetic task only. It does not by itself pass Gate E.

**ACCEPTED VALID NEGATIVE / FAIL:** valid setup/replays but finite wrong actions, any unpermitted fetch/search or acquisition debit, wrong denial reason/identity, leaked stale/fetched payload, publication/readback despite denial, wrong costs, semantic drift on the allowed control, guard defects or measured mutation. Save all outcomes with CLI exit zero and do not change models, thresholds or coverage to obtain PASS.

**INVALID / RETRY C165:** wrong/missing parent/hash/schema/source/checkpoint, historical code drift, source/ranker replay mismatch, nonfinite arithmetic, unexpected execution exception, incomplete run or outer tree/HEAD/postcheck failure. Restore validity and retry C165 unchanged.

## Implementation / reviewer scope

Files:
- `fold_lm/v05_benchmarks/gate_e_c165_live_permission_denied.py`
- `tests_lm/test_v05_c165_live_permission_denied.py`
- `tools/run_c165.ps1`

Expected focused regression: **665 = 638 previous + 27 new helper tests**.

The new helper tests cover the explicit permission wrapper, forwarding of non-permission inputs, real C158-cycle-shaped allow/deny behavior with controlled runtime fixtures, no-fetch/no-budget-spend semantics, typed terminal reason/payload contract, known semantic-error preservation, aggregate accounting and guard/source failure gates. These helper tests are not the formal artifact-backed learned-model measurement.

Reviewer has source-reviewed the new implementation but has **not** executed the complete repository imports, the 665-test regression, the real 82,944-prefix CUDA/CPU experiment or Windows PowerShell runner in this environment. Formal C165 therefore has no result yet.

Runner environment remains `.venv-py31315\Scripts\python.exe`. Progress markers include `[C165] lineage/replay verified`, head/arm/layout/query counts with branch episodes/failed/remaining, `=== C165 RESULT ===`, and `=== C165 POSTCHECK ===`.

Stop after C165 execution. Judge -> scientific interpretation -> confound audit -> ledger/handoff update before any C166 design. C160 stays ACCEPTED VALID NEGATIVE; C164 stays ACCEPTED PASS; Gate E stays NOT PASSED. Multi-Axis and PC-ALM/FHLC remain independent tracks.
