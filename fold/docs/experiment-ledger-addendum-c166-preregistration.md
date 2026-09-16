# C166 preregistration — Live query acquisition-budget exhaustion

Registered 2026-09-16 JST after C165 acceptance and authoritative handoff update.
C165 verdict: `experiment-ledger-addendum-c165-c166.md`; acceptance-only handoff commit `76b91ebe07a7e710f0be239e54b9105161c3e84e`.
Historical C160-C165 results, implementations and preregistrations are not revised.

## Formal state / stage

**C166 — ACTIVE / NOT YET JUDGED**.
Experiment `C166-v5e-live-query-budget-exhausted`.
Stage `V5-E-LIVE-QUERY-BUDGET-EXHAUSTED`; branch `feat/sft-target-loss`.
Use the final registration HEAD containing code/tests/runner/preregistration/handoff as ExpectedHead, not the C165 execution HEAD.
Diagnostic only; **Gate E NOT PASSED**. No C167 is registered.

## One scientific question

With runtime permission allowed and normal delivery fixed, does changing only the initial acquisition allowance from one to zero block all evidence-acquisition dispatch, preserve the exhausted budget, and produce payload-free typed `UNRESOLVED / BUDGET_EXHAUSTED` after the learned Controller's RETRIEVE proposal and subsequent STOP?

C165 tested permission denial with a nonempty acquisition budget. C158 tested budget exhaustion from preselected records. Neither establishes this exact raw-query-originating, typed-terminal budget contrast.

```text
raw query -> fresh frozen ranking (one shared prefix)
  |-- BudgetState(3,1), Permission(True)
  |     -> RETRIEVE -> AUTHORIZED -> fetch/admit/project/readback -> ANSWERED(bit)
  `-- BudgetState(3,0), Permission(True)
        -> RETRIEVE -> BUDGET_EXHAUSTED -> no fetch/publication
        -> reobserve -> STOP -> UNRESOLVED/BUDGET_EXHAUSTED
```

## Changed / held-constant variables

Changed scientific variable: **initial `BudgetState.acquisitions_remaining`, integer 1 versus 0**.

The historical C160 helper still requests its registered `(3,1)` constructor arguments. A local diagnostic API factory verifies those unchanged arguments and constructs an actual core BudgetState with acquisition allowance 1 or 0. This happens before the unchanged C158 cycle; the budget returned by `execute_selected` and supplied to the evaluator is the actual effective initial budget, not an unchanged allowance-one proxy. The factory does not replace the core class globally or change internal debit methods. Every other API object, including Permission and cycle, is identical.

Held constant: 24 frozen C151 rankers (12 seeds 20261721..20261732 x two arms), three frozen C157 Controllers (20261741..20261743), checkpoints, 1,728 queries, 64 descriptors, C151 manifest/splits/vocabulary, two C152 layouts, CUDA float32/highest ranking, CPU Controllers/two threads, query-index-modulo-three router schedule, selected-reference-only removal, 63 other references, stale bit `query_index % 2`, internal budget=3, evidence time/revision=1, initial internal step=7, Permission(True), identity delivery, C158 cycle, C163 observations-only output normalization and C159 emitter.

Training split: none. Evaluation split: existing C151 manifest unchanged. Fresh seeds=0; training steps=0. No model, production runtime, historical source, threshold or target-case selection change. Expected target/value/condition labels enter post-execution evaluation only; condition strings in request scopes are identity, not learned inputs.

The Controller still sees initially advertised acquisition availability; budget enforcement is a separate runtime check after its proposal. This does not test a model that independently understands a numeric budget or avoids making an unaffordable initial proposal.

## Coverage / accounting fixed before measurement

82,944 fresh rankings = 24 heads x 2 layouts x 1,728 queries. Each prefix feeds two fresh independent cold continuations, allowance-one first then allowance-zero. No final state, inbox, working state, budget or output is shared between continuations. This is **165,888 branch episodes, not 165,888 independent raw queries**. Historical saved predictions are not substituted for live selection.

| Metric | Allowance one | Allowance zero | Total |
|---|---:|---:|---:|
| Episodes | 82,944 | 82,944 | 165,888 |
| Controller decisions / internal debits | 165,888 | 165,888 | 331,776 |
| Executed acquisitions | 82,944 | 0 | 82,944 |
| Publications/restorations | 82,944 | 0 | 82,944 |
| Exact64 adapter calls | 165,888 | 0 | 165,888 |
| Vectors scanned | 10,616,832 | 0 | 10,616,832 |
| Typed ANSWERED | 82,944 | 0 | 82,944 |
| Typed UNRESOLVED/BUDGET_EXHAUSTED | 0 | 82,944 | 82,944 |
| Episodes per Controller | 27,648 | 27,648 | 55,296 |

Shared candidate scores=5,308,416. Raw actions: RETRIEVE(2)=165,888; ANSWER(0)=82,944; STOP(5)=82,944. Expected sequences: allowance-one `[2,0]`; allowance-zero `[2,5]`. Both consume two of three internal steps and finish at internal step9/internal remaining1. Allowance-one acquisition budget goes1->0; allowance-zero stays0->0 without debit, negative allowance or replenishment.

Prerequisite C151 ranker replay=41,472 + 288 original12. Historical C159 replay=6,528 emitter calls, separate from new episodes/emissions. No new C157 1,990,656-decision replay is introduced.

## Exact output / behavior boundary

Allowance-one retains the unchanged C160 successful-path gate: 82,944 bound ANSWERED; values zero34,992/one47,952; every arm/layout has20,736 bound outputs, with WITHIN_FACTOR semantic_correct20,727 and GLOBAL_CONCEPT20,736. Known nine control errors x two layouts are retained, not repaired or reclassified.

Allowance-zero requires every first authority to equal BUDGET_EXHAUSTED. No real fetch, adapter call, acquisition debit, admission, inbox publication or readback. Selected reference remains absent; all other63 references and external clocks remain unchanged. Stale presence/payload are cleared; final value/reference are None. Both the original and effective initial budget are traceable; only the effective `(3,0)` is assessed as the starting state.

Output must be schema/request/scope-bound `UNRESOLVED / BUDGET_EXHAUSTED`, with value/key/source/time/revision all None. PERMISSION_DENIED or MISSING_DELIVERY is not an acceptable substitute. Exhausted semantic_correct is null/not applicable. No bit-zero answer or proof of target nonexistence is inferred.

Use unchanged C163 AuditedEmitter: 165,888 native tuple controls plus165,888 adapted candidate emissions. All native controls retain MALFORMED_EVIDENCE; adapted reasons are OBSERVED_VALUE82,944 and BUDGET_EXHAUSTED82,944. The first allowance-one source/record representatives generate128 x6 copied-fault controls=768, with no replacement after failure. New emitter calls total332,544, separate from C159's6,528 replay.

## Input / output protection

Pin accepted C165 report:
`runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`.
SHA256 `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
Execution HEAD `4dfc1634ea4a18f70390807011a83f60654e1b00`.

Validate full C165 identity/profile, all48 trace hashes/sizes and3456-row declarations, plan/controls and input hashes. Follow pinned C164/C163 ancestors through established loaders, replay C159 and C151 as above, and load all frozen checkpoints. Do not regenerate missing source artifacts. C165 trace bytes are hash-checked, not claimed to be independently replayed.

Historical Git blobs for core and C158-C165 remain fixed. C165 module blob is `083c4c11bfbc2ab120fc87d8a3d32009a74fbc76`; the inherited earlier source set is unchanged. C37 and the protected composition fixture remain fixed.

Write `budget-plan.json` before new measurement. Save48 gzip trace files x3456 rows, including actual initial budget, all actions/logits/authorities, compact final-state digest/count, cycle/output/budget assessments, both emitter outcomes and pass bit. Save768 guards. Use a new UUID run directory; preserve prior runs. Recheck all consumed input hashes and code/tree/HEAD after execution in both Python and PowerShell.

## Formal decision rule

**PASS:** every registered count, normal successful-path gate, known semantic boundary, exhausted-branch C158 assessment, exact payload-free output, initial-zero/final-zero budget audit, positive finite expected-action margins, independent meter totals, native controls,768 guards and input/code/tree/HEAD protections pass, with zero measured mutations/serialization failures.

**ACCEPTED VALID NEGATIVE / FAIL:** valid setup but finite wrong raw action, any over-budget fetch/debit/publication, wrong/no-payload output, incorrect reason, restored selected reference under exhaustion, wrong budget/cost/coverage, changed normal semantics, guard failure or measured mutation. Preserve all outcomes; CLI exits0 to permit collection. Do not alter thresholds/checkpoints/cases to obtain PASS.

**INVALID / RETRY C166:** missing/wrong source/hash/schema/fixture/checkpoint, source-code drift, prerequisite replay failure, nonfinite computation, unexpected exception, incomplete execution or outer protection/tree/HEAD failure. Restore execution validity without changing the science; retry the same C number. No automatic next-C run.

## Interpretation limits

PASS is a bounded runtime budget-enforcement result on this fixed synthetic query-to-terminal path, not general reasoning quality, optimal resource allocation or a full Gate E pass. No permission policy, transport semantics, new evidence epoch, initially empty memory, semantic abstention, generated answer, durability or production rollout is added.

Zero allowance-zero adapter cost does not mean zero computation/file access: shared candidate ranking, prerequisite reads and the two internal decisions still occur. Fixed normal-first order is not counterbalanced. Repeated episodes are not independent task generalization. Diagnostic timing/allocator data is not production performance.

## Implementation / reviewer scope / execution

New files: `fold_lm/v05_benchmarks/gate_e_c166_live_budget_exhausted.py`, `tests_lm/test_v05_c166_live_budget_exhausted.py`, `tools/run_c166.ps1`.
Focused regression **695 expected =665 previous +30 new**.

Reviewer compiled both new Python files and executed23 dependency-light helper tests using the new helper/test AST with inspected contract excerpts/test doubles. Seven actual C158-cycle/C163-emitter integration test methods were not executed in that excerpt harness. No complete repository import/regression695, real artifact-backed CUDA/CPU run, or Windows PowerShell execution is claimed. These helper checks are not the C166 scientific result.

Runner uses `.venv-py31315/Scripts/python.exe`, `-C165Summary` and `-ExpectedHead`. Progress: `[C166] lineage/replay verified; acquisition-budget-only plan fixed; training=0`, per-head/arm/layout query/episode/failed/remaining counts, `=== C166 RESULT ===`, `=== C166 POSTCHECK ===`, `run_execution_valid=True`.

Stop for formal judgment and ledger/handoff update before any C167. C160 stays ACCEPTED VALID NEGATIVE; C165 stays ACCEPTED PASS; Gate E stays NOT PASSED. Multi-Axis and PC-ALM/FHLC remain independent research tracks.
