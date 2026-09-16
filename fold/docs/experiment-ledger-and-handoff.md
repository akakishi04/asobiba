# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and current addendum. Judge -> ledger/handoff -> next C. One scientific question per C; invalid executions retry the same number; valid negatives stay accepted evidence.
- Latest accepted execution: **C166**, HEAD `dc1f315cac66d1963f8e0d08bb897457affbe94a`. Acceptance recorded in `a651c3765618d0c52927e1c7dcdcdc29b96a8b3c`, before the next experiment is registered.

## Gate status / architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.
Priority remains operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

Production retrieval head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`;
persisted adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains separate design, not implemented by these diagnostics.

## Accepted evidence through C166

C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity. C141 PASS oracle localization; C142 PASS small supervised alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive attribution. C145-C148 include accepted negative interventions; C149 PASS arithmetic attribution. C150 PASS original synthetic split. Earlier detailed claims remain in chained addenda.

- **C151 PASS**,298 tests: four splits x three paired initializations; WITHIN_FACTOR20,727/20,736 and GLOBAL_CONCEPT20,736/20,736. Nine control errors in S2/20261726; synthetic ranker tuning closed; no independent task/language generalization.
- **C152 PASS**,322 tests:24 frozen heads/two layouts;82,944 exact64 reads with selected identity/provenance/payload/cost preserved.
- **C153 PASS**,346 tests:82,944 reads,580,608 deliveries,414,720 invalid rejections,82,944 admissions and duplicate rejections each; immutable diagnostic inbox, not durability.
- **C154 PASS**,363 tests:3,072 ADDED/79,872 ALREADY_PRESENT,3,072 conflicts rejected;48 states x64 refs. Classification caveat: `experiment-ledger-addendum-c154-pcalm-review.md`.
- **C155 PASS**,388 tests:12,288 resolver cases/four statuses;3,072 reads/196,608 vectors;zero/one1,296/1,776.
- **C156 PASS**,412 tests:82,944 requests x4 conditions=331,776 views; zero/unresolved separated, no stale payload/external-clock advance.
- **C157 PASS**,440 tests:three Controllers, seeds20261741..20261743,900 updates each;1,990,656 recorded-input decisions;minimum margin5.344475269317627.
- **C158 PASS**,475 tests:preselected-record warm/recover/missing/denied/exhausted live cases;1,920 episodes/3,456 decisions,768 acquisitions,384 restorations,1,536 calls/98,304 vectors. Not raw-query selection.
- **C159 PASS**,508 tests:stored-terminal emitter;1,920 terminals ->6,528 emissions,ANSWERED768/UNRESOLVED1,152,4,608 controls rejected.
- **C160 ACCEPTED VALID NEGATIVE**,546 tests,execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`:82,944 complete live cycles but ANSWERED0/failed82,944. Never retroactively relabel.
- **C161 PASS**,558 tests:all82,944 stored cycle assessments pass; single post-cycle rejection MALFORMED_EVIDENCE.
- **C162 PASS**,588 tests:82,944 digest-verified offline tuple/list pairs; native rejection/list-bound output,768 guards pass; reconstruction, not original heap capture.
- **C163 PASS**,614 tests:82,944 raw-query live cycles yield bound ANSWERED after observations-only normalization; native controls reject.165,888 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors;768 guards/494 input checks pass.
- **C164 PASS**,638 tests:82,944 rankings x2 fresh continuations=165,888 branch episodes. Normal ANSWERED82,944 / missing UNRESOLVED-MISSING_DELIVERY82,944;331,776 decisions,165,888 acquisitions,82,944 publications,248,832 calls/15,925,248 vectors. Missing branch never publishes/rereads;768 guards/545 input checks pass.
- **C165 PASS**,665 tests:165,888 allowed/permission-denied branch episodes,zero failures.331,776 decisions,82,944 acquisitions/restorations,165,888 adapter calls/10,616,832 vectors. Denied UNRESOLVED/PERMISSION_DENIED82,944,zero acquisition/read/debit/publication;budget1->1. Raw RETRIEVE not overridden.768 guards/596 inputs and historical code/tree/HEAD preserved.
- **C166 ACCEPTED PASS**,**695/695 tests**,execution `dc1f315cac66d1963f8e0d08bb897457affbe94a`:82,944 fresh rankings x initial acquisition allowance1/0=165,888 independent-continuation branch episodes,zero failures.331,776 decisions,82,944 acquisitions/restorations,165,888 reads/10,616,832 vectors. Normal ANSWERED82,944; exhausted UNRESOLVED/BUDGET_EXHAUSTED82,944. All exhausted initial/final allowances0, authorities BUDGET_EXHAUSTED, no overbudget fetch/debit/publication/readback. PermissionTrue in both.768 guards/647 input checks/historical code/tree/HEAD preserved;zero mutations/serialization failures. Margins normal6.142457485198975/exhausted5.3444743156433105.

## Interpretation boundary

Raw-query-originating normal recovery, post-fetch missing delivery, permission denial and initial acquisition-budget exhaustion have measured typed terminal evidence. These are distinct runtime claims, not broad model intelligence.
Normal branches retain20,736 bound outputs per arm/layout, semantic_correct WITHIN_FACTOR20,727 / GLOBAL_CONCEPT20,736; zero34,992/one47,952. Nine known errors x2 layouts remain18 repeated instances, not18 new error types. Unresolved semantic_correct=null; unresolved is not bit0 or nonexistence.

Runtime enforces permission/budget after the model proposal. C166 does not establish learned numerical budget comprehension or avoidance of unaffordable proposals. Zero denied/exhausted adapter calls does not remove shared ranking, prerequisite IO or internal decisions; no OS isolation/confidential-catalog guarantee is measured.

C160 stays accepted negative. EvidenceState stays tuple-backed; C163 bridge/C159 emitter unchanged. No checkpoint/threshold/target repair. No accepted raw-query **warm already-bound** path, initially empty world, dynamic epochs, relevance abstention, generated answers, durability or production rollout yet. Repeated fixed-fixture episodes are not independent task generalization; diagnostic timing/allocator data is not full-model production performance. **Gate E NOT PASSED**.

## Accepted artifact chain

**C166:** `runs/c166-v5e-live-budget-exhausted-94d4977de28e464aa298c02f1f63bf06/summary.json`.
SHA256 `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.
Plan `0946b2ef10a92346449d484590b0a753e91561906b14af710dbdebe4b1041eaf`.
Controls `0cd6072abd850d5a7976bd8bf4c029b50e0a6dd670e2fa2a2c792fc6c7254d81`.
Uploaded-log SHA256 `a607be254bdbd681ffa75538b549bb6ecbfe73c60200c9c88c19f1e755ee5d49`.

**C165:** `runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`, SHA256 `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
**C164:** `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`, SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`, SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
C151-C162 paths/hashes, earlier evidence and source splits remain in chained addenda and the prior authoritative handoff at `dc1f315cac66d1963f8e0d08bb897457affbe94a`.
C151 SHA `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`; manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`; split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c166-c167.md`**.
Last executed preregistration: **`docs/experiment-ledger-addendum-c166-preregistration.md`**.
Reviewer checked uploaded console/source/preregistration consistency and uploaded-byte hash. Omitted records mean no independent full-report hash reconstruction or user-side raw-trace/model replay is claimed.

## Next experiment boundary

**C166 judged and recorded. No C167 registered yet.**
Next design must isolate one remaining limitation and preregister before execution. Historical source/run artifacts remain protected; do not rerun C166 for a more favorable metric.

## Independent research tracks

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. Shared-Basis partition, Multi-Axis, local credit, KV/context, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not production clocks. Cross-source namespaces, revisions/retractions and durable publication/recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
