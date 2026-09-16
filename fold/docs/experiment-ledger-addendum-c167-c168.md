# C167 verdict and next-design boundary

Recorded 2026-09-16 JST after review of the user-uploaded C167 console log.
Preregistration: `experiment-ledger-addendum-c167-preregistration.md`.
Previous verdict: `experiment-ledger-addendum-c166-c167.md`.
This acceptance is recorded before any next experiment registration.

## 1. Formal verdict

**C167 — ACCEPTED PASS**.
Experiment `C167-v5e-live-query-warm-reference`.
Stage `V5-E-LIVE-QUERY-WARM-REFERENCE`.
Execution branch `feat/sft-target-loss`; HEAD `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`.
Diagnostic only; production runtime unchanged; **Gate E NOT PASSED**.
C160 remains **ACCEPTED VALID NEGATIVE**. C161-C166 retain their accepted verdicts.
No checkpoint, threshold, target, layout, case coverage or seed was changed to accept this result.

## 2. Evidence identity and execution validity

- Uploaded log: `貼り付けられたテキスト（1 点）(20260916-072025).txt`; 333,106 bytes.
- Uploaded-byte SHA256 independently computed by reviewer: `ce0a633df8dfa338046484766b38afa18f985b1e94789710857f97287c45922a`.
- Report: `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`.
- Full report SHA256 reported by runner: `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.
- Reference-presence plan SHA256: `24afcd65e73a7ff2c2d81accb9987e75a7dba40e5d85d8dc662a1a784ac6c70e`.
- Guard controls SHA256: `fd8ee32e98443b7ab3ec0bdf9bfd4c4672cb4ae7710bc2318938150e8be534a4`.
- Pinned C166 parent SHA256: `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.

Focused regression **725/725 PASS**, 11.161 seconds. All384 progress entries report failed=0; final branch count165,888.
24 frozen C151 rankers; three frozen C157 Controllers; training0/fresh seeds0.
C151 prerequisite replay41,472 plus original12 replay288; C159 recorded-emission replay6,528, separate from new measurement.
Reported environment: torch2.10.0+cu130, CUDA13.0, RTX4070 Ti SUPER, float32/highest rankers, CPU Controllers, two threads.

Postchecks preserve all698 declared input paths, C166 parent, C37, composition fixture, historical source blobs, output artifacts, tracked tree and execution HEAD. The input-path total includes the newly written plan, so it is not a claim of698 independent pre-existing datasets.
`diagnostic_execution_valid=true` and `run_execution_valid=True`; weight/output mutations and serialization failures0.
Existing C145 tensor-to-scalar warning occurs within a passing historical regression, not C167 invalidity.

Reviewer parsed the full uploaded console JSON and checked18 consistency groups covering identity/scope, registered totals, condition-level counts, state/budget audits, margins, semantic boundaries, emission controls, input-hash declarations, progress and outer postchecks. Reviewed the pinned C167 implementation and preregistration.
The reviewer initially used an LF-only string match for the regression footer; the uploaded bytes use CRLF. Only that reviewer-side line matcher was corrected. Source bytes, experiment metrics and decision criteria were not changed.
**Verification limit:** console `records` is omitted. No independent reconstruction of the complete report SHA256, re-read of the48 raw user-side traces, artifact-backed model replay or rerun of725 tests is claimed. Runner output integrity checks are not independent semantic replay.

## 3. Deciding metrics

| Metric | COLD_RECOVER | WARM_PRESENT | Total |
|---|---:|---:|---:|
| Branch episodes |82,944|82,944|165,888|
| Failed episodes |0|0|0|
| Controller decisions |165,888|82,944|248,832|
| Executed acquisitions |82,944|0|82,944|
| Publications/restorations |82,944|0|82,944|
| Exact64 adapter reads |165,888|82,944|248,832|
| Vectors scanned |10,616,832|5,308,416|15,925,248|
| Typed ANSWERED |82,944|82,944|165,888|
| Typed UNRESOLVED |0|0|0|

82,944 fresh shared ranking prefixes;5,308,416 candidate scores;82,944 matched observed-output pairs with distinct request/scope identities. These are165,888 condition executions, not165,888 independent questions.
Independent adapter meters agree with reported calls/vectors. Each Controller has27,648 episodes per condition,55,296 total.
Raw actions: RETRIEVE82,944; ANSWER165,888; STOP0.
Minimum Controller margin: cold6.142457485198975; warm9.29835307598114.

Every warm branch passes initial-state audit, initial-budget audit, no-reacquisition, acquisition-budget preservation, one-ANSWER and unchanged-state checks:82,944 each.
Warm pays one exact64 dereference and one internal step; final budget(2 internal,1 acquisition), internal step8. Cold final budget(1,0), step9, as assessed against the unchanged cycle contract.

Native controls165,888 all retain MALFORMED_EVIDENCE. Adapted emissions165,888 all ANSWERED/OBSERVED_VALUE. Contents and inputs preserved165,888 each. Guards768/768 PASS over128 source-record bindings; no failures.

For EACH condition and EACH layout: WITHIN_FACTOR20,727/20,736 semantic correct; GLOBAL_CONCEPT20,736/20,736; binding20,736/20,736 in every arm/layout.
Known control errors occur36 times=9 x2 layouts x2 answered conditions, not36 new error types. Per-condition values:0=34,992;1=47,952. Total0=69,984;1=95,904. Matching a bit from the wrong record is still a semantic error.

Timing825.2087280999986 seconds includes prerequisite checks/replay/controls/serialization. CUDA peak allocated11,956,224 bytes/reserved25,165,824 bytes is small-diagnostic allocator accounting, not full-model VRAM or isolated query latency.

## 4. Scientific interpretation

```text
raw query -> frozen live ranker -> selected record
    |-- cold selected reference absent -> RETRIEVE -> acquire/admit/restore
    |                                  -> paid readback -> ANSWER -> typed observed bit
    `-- warm selected reference present -> paid dereference -> ANSWER -> same observed bit
```

Within the pinned synthetic task, initially available provenance-bound references eliminate redundant acquisition and a second Controller decision without reducing measured binding/semantic quality relative to cold recovery.
Warm is not free: ranking and a real exact64 dereference remain. This is not a cached generated answer or warm language-session/prefix reuse.
C167 supports the narrow no-reacquisition part of Gate E. It does not establish semantic necessity of missing information, unnecessary human-question reduction, hallucination-rate improvement against an internal-compute baseline, broad uncertainty competence or final Gate E acceptance.

## 5. Confound audit

Only initial selected-reference membership changes; other63 references, models/checkpoints, queries, layouts, permissionTrue, initial budget(3,1), clocks/revision, stale working input, delivery and emitter remain fixed.
Warm starts from a fresh immutable copy of the pinned full fixture, not the preceding cold final state. Mutable working/inbox/budget or acquired results are not reused.
Cold then warm order and the shared ranking prefix are explicit. This is not randomized-order performance evidence or independent replication across tasks. Warm has64 references versus cold63 by design; this trial alone does not disentangle every possible response to reference count from semantic relevance. Additional tests should be justified by a specific remaining Gate E claim, not invented solely because this trial passed.
No semantic target enters Controller/acquisition/emitter; correctness is scored after output. C160's known errors and negative result remain intact.

## 6. Ledger/handoff update

Advance accepted evidence through C167; archive its execution/prerequisite identity and limits. Historical source and prior preregistrations remain unchanged. No new runtime implementation or scientific execution is included in this acceptance commit.

## 7. Next-design boundary

**C168 is NOT REGISTERED. No new experiment is active at this acceptance boundary.**
The immediately preceding user question concerns the actual Gate E exit condition. Before adding further long local contrasts, map the roadmap's five Gate E properties to measured evidence, identify unmeasured comparative claims, and specify a finite final-evaluation contract. This is design work, not a retroactive C167 condition or a claim that Gate E is close to passing.
A subsequent next-experiment design must name one unresolved scientific question, observable inputs, controls and preregistered decision rules. Do not treat a draft as ACTIVE or provide a nonexistent runner. Preserve the standard judgment -> ledger/handoff -> next-design order.
