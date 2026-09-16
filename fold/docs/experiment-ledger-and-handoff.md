# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts/preregistrations remain unchanged.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER;
  `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`:
  `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`:
  `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this file,
  `docs/experiment-ledger-addendum-c167-c168.md`,
  **`docs/experiment-ledger-addendum-c168-preregistration.md`** and
  **`docs/gate-e-evaluation-contract-v0.1.md`**.
- Judge -> ledger/handoff -> next C. One scientific question per C. Preserve valid
  negatives; invalid executions retry the same registered conditions/number.
- Latest accepted execution C167 at `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`;
  acceptance `5b0f37028f82e987e399da60bf40c17e69de5fcf`.
  Design-only parent HEAD `2f1f3a06e9c4499db34ad1e9aea8b4225fc8e095`.
  Use the final C168 registration commit as ExpectedHead. Do not rerun C167.

## Formal state / architecture boundary

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.
**C167 ACCEPTED PASS. C168 ACTIVE / NOT YET JUDGED. C169 NOT REGISTERED.**
Priority remains operational VRAM headroom, peak/resident VRAM, latency/throughput,
artifact size. C168 does not measure performance of a full model.

```text
learned Control Lane -> runtime permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve -> typed answer/unresolved
```

Retrieval head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`;
persisted adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains separate design, not implemented here.

## Accepted evidence / history

Full through-C167 evidence and artifact-chain index remain authoritative in this file
at `2f1f3a06e9c4499db34ad1e9aea8b4225fc8e095`, in the acceptance-only handoff at
`5b0f37028f82e987e399da60bf40c17e69de5fcf`, and in chained addenda. Those histories
are not superseded by this shorter active-work index.

C151 PASS:24 paired heads/four splits; WITHIN_FACTOR20,727/20,736 and
GLOBAL_CONCEPT20,736/20,736; nine control errors in S2/20261726, synthetic ranker
 tuning closed. C152-C157 connect persisted retrieval/admission/state/readback/
reobservation/frozen Controller, with distinct claims. C154 classification caveat
remains `experiment-ledger-addendum-c154-pcalm-review.md`.

C158 preselected-record live cycle and C159 stored-terminal emitter PASS.
**C160 ACCEPTED VALID NEGATIVE**,546 tests,82,944 completed cycles but ANSWERED0;
never relabel. C161 localized MALFORMED_EVIDENCE; C162 offline tuple/list differential;
C163 live observations-only bridge:82,944 bound outputs. C164 delivery missing,
C165 permission denied and C166 budget exhausted PASS within their registered scopes.

**C167 ACCEPTED PASS**,725/725 regression:82,944 shared rankings x cold/warm
=165,888 episodes;zero failures;82,944 matched outputs.248,832 decisions,82,944
acquisitions/restorations,248,832 exact64 reads/15,925,248 vectors. Warm pays one read
and one decision, no acquisition/publication;state unchanged,budget(2,1). Cold
budget(1,0).768 guards and698 declared input-path checks plus output/code/tree/HEAD
checks pass. Margins cold6.142457485198975/warm9.29835307598114.

Each answered condition/layout retains binding20,736 per arm and semantic
WITHIN_FACTOR20,727/GLOBAL_CONCEPT20,736. C167 known errors36=9 x2 layouts x2
conditions, not36 error types. Each condition0=34,992/1=47,952. Unresolved is not
bit0/nonexistence; unresolved semantic_correct=null.

C167 report `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`.
SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.
Plan `24afcd65e73a7ff2c2d81accb9987e75a7dba40e5d85d8dc662a1a784ac6c70e`.
Controls `fd8ee32e98443b7ab3ec0bdf9bfd4c4672cb4ae7710bc2318938150e8be534a4`.
Uploaded log `ce0a633df8dfa338046484766b38afa18f985b1e94789710857f97287c45922a`.
Reviewer checked console/source/preregistration and uploaded-byte hash; omitted records
prevent independent complete-report reconstruction or raw-trace/model replay claims.
Keep C167 summary and48 traces; C168 does not need to consume/replay those traces.

## Gate E design boundary

`gate-e-acceptance-gap-audit-after-c167.md` is the historical gap review and draft.
`gate-e-evaluation-contract-v0.1.md` now fixes a finite nine-family structured-task
scope, baseline choices, metric meanings/denominators and later-stage exclusions.
It is **not final numerical preregistration**. Candidate/checkpoints, exact splits,
counts, baseline-development results, statistical/numerical rules and output schema
must be fixed before a deciding Gate run. Final-evaluation readiness is BLOCKED.
No arbitrary97%/99% threshold or remaining-C count is inferred from past local passes.

The current C160 helper stipulates dependency=1; C156 updates presence/value. C167
therefore does not infer task necessity from visible logical expression/known A.
Runtime enforces authority/budget. Zero adapter calls excludes shared ranking and
prerequisite IO. Warm is not free or a language-session cache. No general language,
Vision,durable memory,learned semantic abstention or generated-answer claims follow.
Do not add these later-stage goals as new implicit Gate E prerequisites.

## Active C168 — Task-necessity input observability

`C168-v5e-task-necessity-input-observability`;
`V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY`.
**ACTIVE / NOT YET JUDGED.** No formal run has been performed by the reviewer.

Question: does the existing **post-selection input boundary** convey the distinction
between critical and irrelevant missing facts for a bounded logical extension probe?
Not raw AND/OR text through C151; not a trained classifier or complete live cycle.
Operator/known-A fields remain explicitly unsupported audit-side task fields; do not
silently inject their correct dependency label or invent an expression encoder.

8 challenge rows:AND/OR x known A0/1 x nuisance stale0/1, B unobserved, availableTrue.
4 source controls:missing selected bit x availableFalse/True x stale0/1.
12 actual pre-forward captures through C160 initialization,C156 reobserve,C158
_decision's input construction. A callback captures tensors and aborts before learned
forward. Synthetic64-reference fixture, selected B removed, no payload store.
0 checkpoints/neural forwards/ranker/retrieval/acquisition/full cycles/emissions/
training/fresh seeds in benchmark; regression activity is accounted separately.

Group exact tensors and runtime context before labels. Retain conflicting necessity
classes, minority-count error lower bound and8 operator/A-only pairs. Symbolic full-
visible reference and original availability controls validate the task/harness, not
learned ability. PASS requires zero conflicts/lost critical pairs; a valid collision
is ACCEPTED VALID NEGATIVE. Source/schema/leakage/incomplete/outer protection failure
is INVALID and retries C168 unchanged. No repair inside C168 and no Gate E promotion.

Pin accepted C167 summary; preserve C37/fixture/source/tree/HEAD. No recursive698-input
replay or new GPU workload. Save fresh UUID input-plan and complete summary/captures.
Files: `fold_lm/v05_benchmarks/gate_e_c168_necessity_observability.py`,
`tests_lm/test_v05_c168_necessity_observability.py`, `tools/run_c168.ps1`.
Focused regression **749 expected=725+24**. Reviewer compiled Python and passed20
unit tests;4 actual-repository integration tests,full749,artifact-backed CLI and
Windows PowerShell unexecuted. No formal C168 result yet.
Runner args `-C167Summary -ExpectedHead`; Python `.venv-py31315\Scripts\python.exe`.
Return the complete log even for scientific FAIL with execution validity True.
**C168 judgment and ledger update precede C169.**

## Independent tracks / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate unimplemented candidates.
Shared-Basis,local credit,KV/context,ranking,retrieval,admission,EvidenceState,
readback,reobservation,Controller,typed return and learned ANSWER remain distinct.
No production clocks,cross-source revisions/retractions,durable recovery or rollout
is implemented by C168. `fold/fold_memory.py` is a QuadraticMemory reference, not
this V5-E store. Prior checkpoint/threshold/target/error boundaries remain fixed.
