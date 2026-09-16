# C166 verdict and handoff boundary

Recorded 2026-09-16 JST from the user-uploaded console log, before any C167 registration.
Preregistration: `experiment-ledger-addendum-c166-preregistration.md`.
Previous verdict: `experiment-ledger-addendum-c165-c166.md`.

## 1. Formal verdict

**C166 — ACCEPTED PASS**.
Experiment `C166-v5e-live-query-budget-exhausted`.
Stage `V5-E-LIVE-QUERY-BUDGET-EXHAUSTED`.
Execution branch `feat/sft-target-loss`; HEAD `dc1f315cac66d1963f8e0d08bb897457affbe94a`.
Diagnostic only, production runtime unchanged. **Gate E NOT PASSED**.
C160 remains **ACCEPTED VALID NEGATIVE**. C161-C165 retain their accepted verdicts.
No thresholds, checkpoints, case coverage, layouts or seeds were changed to accept C166.

## 2. Evidence identity / execution validity

- Uploaded file: `貼り付けられたテキスト（1 点）(20260916-064004).txt`, 316,961 bytes.
- SHA256 independently computed from uploaded bytes: `a607be254bdbd681ffa75538b549bb6ecbfe73c60200c9c88c19f1e755ee5d49`.
- Report: `runs/c166-v5e-live-budget-exhausted-94d4977de28e464aa298c02f1f63bf06/summary.json`.
- Report SHA256 reported by runner: `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.
- Budget plan SHA256: `0946b2ef10a92346449d484590b0a753e91561906b14af710dbdebe4b1041eaf`.
- Guard controls SHA256: `0cd6072abd850d5a7976bd8bf4c029b50e0a6dd670e2fa2a2c792fc6c7254d81`.
- Accepted C165 parent SHA256: `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.

Focused regression **695/695 PASS**, 9.012 seconds. All 384 progress entries report failed=0; final branch count165,888. C151 prerequisite replay41,472 plus original12 replay288; C159 recorded-emission replay6,528. These are separate from new live episodes.

24 frozen rankers, three frozen Controllers, training0/fresh seeds0. Reported environment: torch2.10.0+cu130, CUDA13.0, RTX4070 Ti SUPER, float32/highest rankers, CPU Controllers, two threads; runner `.venv-py31315/Scripts/python.exe`.

All647 consumed inputs, C165 parent, C37, protected composition fixture, historical source blobs, tracked tree and execution HEAD pass postchecks. Weight/output mutations and serialization failures are0. Both `diagnostic_execution_valid=true` and `run_execution_valid=True`.
The existing C145 tensor-to-scalar warning occurs within a passing historical test; it is not execution invalidity.

## 3. Deciding metrics

| Metric | Allowance1 | Allowance0 | Total |
|---|---:|---:|---:|
| Branch episodes |82944|82944|165888|
| Failed episodes |0|0|0|
| Controller decisions |165888|165888|331776|
| Executed acquisitions |82944|0|82944|
| Publications/restorations |82944|0|82944|
| Exact64 adapter calls |165888|0|165888|
| Vectors scanned |10616832|0|10616832|
| ANSWERED |82944|0|82944|
| UNRESOLVED/BUDGET_EXHAUSTED |0|82944|82944|

Shared live ranking prefixes82,944; candidate scores5,308,416. Raw actions RETRIEVE165,888/ANSWER82,944/STOP82,944. Each Controller handles27,648 episodes per condition/55,296 total.
Allowance0 audits: budget_exhausted_authority82,944; initial_acquisition_budget_zero82,944; acquisition_budget_preserved82,944; no_overbudget_fetch82,944. Initial/final acquisition budget0; two internal decisions paid, final internal remaining1/internal step9 under the existing episode assessor.
Minimum Controller margins: normal6.142457485198975; exhausted5.3444743156433105.

Normal outputs: zero34,992/one47,952. Every arm/layout has20,736 bound outputs. Per layout WITHIN_FACTOR semantic_correct20,727; GLOBAL_CONCEPT20,736. Nine known control errors x two layouts remain18 instances, not18 new error types. Exhausted semantic_correct=null/not applicable and no payload.

Native tuple controls165,888 all reject MALFORMED_EVIDENCE; adapted calls165,888 return82,944 OBSERVED_VALUE and82,944 BUDGET_EXHAUSTED. Content/input preservation checks165,888 each. Guards768/768 PASS over128 source-record identities. Independent adapter meters match all cycle costs.

## 4. Scientific interpretation

```text
raw query -> fresh frozen selection -> learned RETRIEVE proposal
    |-- permissionTrue, acquisition allowance1
    |     -> authorized fetch/admission/reference restoration/readback
    |     -> learned ANSWER -> bound observed-bit result
    `-- permissionTrue, acquisition allowance0
          -> runtime BUDGET_EXHAUSTED -> no acquisition/debit/publication
          -> reobserve still unbound -> learned STOP
          -> typed payload-free UNRESOLVED/BUDGET_EXHAUSTED
```

The initial acquisition allowance alone explains the measured contrast within this registered diagnostic. Effective actual BudgetState(3,0), not an allowance-one evaluator proxy, is used on the exhausted branch. Correctly stopping does not assert bit0 or target nonexistence.
The result supports bounded runtime budget enforcement, not learned numerical budget comprehension, optimal resource allocation or prevention of the initial unaffordable model proposal. Internal decision cost remains charged.

## 5. Confound audit / non-claims

Models/checkpoints/queries/catalog/permission/transport/clocks/terminal bridge remain fixed. Fresh independent state/working/inbox/budgets per continuation prevent normal-branch recovery from being reused as the exhausted result. Normal-first order is fixed, not counterbalanced. Shared ranking prefixes do not create165,888 independent tasks.

Zero exhausted adapter calls does not mean zero ranking, source-validation file access or internal computation. This is not an OS isolation or confidential-catalog test. Authentic irrelevant selected records remain semantic errors; no evaluator target repair is allowed.

Warm already-bound raw-query behavior, initially empty memory, relevance abstention, generated answers, dynamic epochs, durable publication and production rollout are not established by C166. Model proposal, runtime enforcement and deterministic typed emission are distinct claims. Gate E remains NOT PASSED; Multi-Axis and PC-ALM/FHLC remain independent research tracks.

Reported diagnostic wall time670.9576574999955 seconds, peak CUDA allocated11,956,224 bytes/reserved25,165,824 bytes include this diagnostic's validation/replay/control work and are not production latency or full-model VRAM measurements.

## 6. Reviewer scope / next boundary

Reviewer parsed the uploaded JSON and complete console tail, calculated the uploaded-byte hash, checked384 progress rows, and compared metrics/source/preregistration/postchecks. Console `records` is omitted. No independent full report hash reconstruction, raw48-trace replay, user-side input rehash or learned-model rerun is claimed.

This file records C166 acceptance only. The authoritative handoff is to be advanced through C166 before the next C is registered. Subsequent C167 design must remove one remaining limitation while preserving all historical results.
