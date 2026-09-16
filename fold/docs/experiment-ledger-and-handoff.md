# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and current verdict/design. Judge -> ledger/handoff -> next C. One scientific question per C; invalid executions retry the same number; valid negatives stay accepted evidence.
- Latest accepted execution: **C167**, HEAD `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`. Subsequent documentation commits are not scientific execution HEADs.

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

## Accepted evidence through C167

Earlier detailed summaries and artifact identities remain in the prior handoff at `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1` and its chained addenda. They are not superseded by this compression of the current handoff.

C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity. C141 PASS oracle localization; C142 PASS small supervised alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive attribution. C145-C148 include accepted negative interventions; C149 PASS arithmetic attribution; C150 PASS original synthetic split.

- **C151 PASS**,298 tests: four splits x three paired initializations; WITHIN_FACTOR20,727/20,736 and GLOBAL_CONCEPT20,736/20,736. Nine control errors in S2/20261726; synthetic ranker tuning closed; no independent task/language generalization.
- **C152 PASS**,322 tests:24 frozen heads/two layouts;82,944 exact64 reads, selected identity/provenance/payload/cost preserved.
- **C153 PASS**,346 tests:82,944 reads,580,608 deliveries,414,720 invalid rejections,82,944 admissions and duplicate rejections each; immutable diagnostic inbox, not durability.
- **C154 PASS**,363 tests:3,072 ADDED/79,872 ALREADY_PRESENT,3,072 conflicts rejected;48 states x64 refs. Classification caveat: `experiment-ledger-addendum-c154-pcalm-review.md`.
- **C155 PASS**,388 tests:12,288 resolver cases/four statuses;3,072 reads/196,608 vectors;zero/one1,296/1,776.
- **C156 PASS**,412 tests:82,944 requests x4 conditions=331,776 views;zero/unresolved separated,no stale payload/external-clock advance.
- **C157 PASS**,440 tests:three Controllers20261741..20261743,900 updates each;1,990,656 recorded-input decisions;minimum margin5.344475269317627.
- **C158 PASS**,475 tests:preselected warm/recover/missing/denied/exhausted;1,920 episodes/3,456 decisions,768 acquisitions,384 restorations,1,536 calls/98,304 vectors. Not raw-query selection.
- **C159 PASS**,508 tests:stored-terminal emitter;1,920 terminals ->6,528 emissions,ANSWERED768/UNRESOLVED1,152,4,608 controls rejected.
- **C160 ACCEPTED VALID NEGATIVE**,546 tests,execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`:82,944 complete live cycles,ANSWERED0/failed82,944. Never retroactively relabel.
- **C161 PASS**,558 tests:all82,944 stored cycle assessments pass;single terminal rejection MALFORMED_EVIDENCE.
- **C162 PASS**,588 tests:82,944 digest-verified offline tuple/list pairs;native rejection/list-bound output;768 guards. Reconstruction,not original heap capture.
- **C163 PASS**,614 tests:82,944 raw-query live bound ANSWERED after observations-only normalization;native controls reject.165,888 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors;768 guards/494 input checks.
- **C164 PASS**,638 tests:82,944 rankings x2 continuations=165,888 branch episodes;normal ANSWERED82,944/missing UNRESOLVED-MISSING_DELIVERY82,944.331,776 decisions,165,888 acquisitions,82,944 publications,248,832 calls/15,925,248 vectors;missing never publishes/rereads;768 guards/545 input checks.
- **C165 PASS**,665 tests:165,888 allowed/permission-denied episodes,zero failures;331,776 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors. Denied UNRESOLVED/PERMISSION_DENIED82,944;zero acquisition/read/debit/publication;budget1->1.768 guards/596 input checks.
- **C166 PASS**,695 tests:165,888 initial acquisition-allowance1/0 episodes,zero failures;331,776 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors. Exhausted UNRESOLVED/BUDGET_EXHAUSTED82,944;no fetch/debit/publication/readback;permissionTrue both.768 guards/647 input checks.
- **C167 ACCEPTED PASS**,**725/725 tests**:82,944 fresh ranking prefixes x cold/warm=165,888 episodes;failed0,matched observed-output pairs82,944,ANSWERED165,888.248,832 decisions,82,944 acquisitions/restorations,248,832 exact64 reads/15,925,248 vectors. Warm82,944 episodes each:one paid read,one ANSWER,no acquisition/admission/publication,unchanged evidence,acquisition allowance1->1,final budget(2,1). Cold retains recovery behavior/final budget(1,0). Margins cold6.142457485198975/warm9.29835307598114.768 guards/698 declared input-path checks and new output-artifact/historical-code/tree/HEAD checks pass;zero mutations/serialization failures.

## Interpretation boundary

Raw-query normal recovery, missing delivery, permission denial, acquisition-budget exhaustion and warm already-bound references have measured typed terminal evidence. These are distinct runtime claims, not broad model intelligence.
For every answered condition/layout, each arm has20,736 bound outputs;semantic_correct WITHIN_FACTOR20,727/GLOBAL_CONCEPT20,736. In C167,known errors repeat36 times=9 x2 layouts x2 answered conditions,not36 error types. Each condition values0=34,992/1=47,952. Unresolved remains neither bit0 nor nonexistence;unresolved semantic_correct=null.

Runtime enforces permission/budget after model proposal. Zero denied/exhausted adapter calls excludes shared ranking,prerequisite IO and internal decisions. Warm still pays an exact64 read. No learned numerical budget comprehension,OS isolation,zero-IO answer-cache or warm language-session prefix reuse is established.

C160 stays accepted negative;EvidenceState tuple backing and historical C163 bridge/C159 emitter unchanged. No checkpoint/threshold/target repair. No accepted general semantic relevance/necessity judgment,initially empty world,dynamic epochs,generated answers,durability or production rollout from these diagnostics. Repeated fixed-fixture episodes are not independent task generalization;diagnostic timing/allocator data is not full-model production performance.

The roadmap's comparative hallucination/quality/unnecessary-question/coverage criteria are not satisfied merely by accumulating local PASS results. A final evaluation's scope,baselines,denominators and numerical decision rules must be fixed before its deciding comparison. **Gate E NOT PASSED**;remaining number of experiments is not yet established.

## Accepted artifact chain

**C167:** `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`.
SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.
Plan `24afcd65e73a7ff2c2d81accb9987e75a7dba40e5d85d8dc662a1a784ac6c70e`.
Controls `fd8ee32e98443b7ab3ec0bdf9bfd4c4672cb4ae7710bc2318938150e8be534a4`.
Uploaded-log SHA256 `ce0a633df8dfa338046484766b38afa18f985b1e94789710857f97287c45922a`.

**C166:** `runs/c166-v5e-live-budget-exhausted-94d4977de28e464aa298c02f1f63bf06/summary.json`,SHA256 `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.
**C165:** `runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`,SHA256 `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
**C164:** `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`,SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`,SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
C151-C162 paths/hashes and earlier source splits remain in chained addenda and the handoff at `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`.
C151 SHA `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`;manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`;split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c167-c168.md`**.
C167 preregistration remains historical: `docs/experiment-ledger-addendum-c167-preregistration.md`.
Reviewer checked uploaded-byte hash and console/source/preregistration consistency. Omitted records mean no independent full-report hash reconstruction or raw-trace/model replay is claimed.

## Next action — design boundary, no active experiment

**C167 ACCEPTED PASS. C168 NOT REGISTERED. No next experiment is currently ACTIVE.**
The user's Gate E exit-condition question identifies a planning need: map the five roadmap properties to actual evidence and define a finite acceptance-evaluation contract before continuing long local contrasts. This is not a new scientific result and does not change C167's criteria.
Do not run C167 again just because documentation HEAD advanced. Preserve its report and48 traces. Do not invent a C168 execution command or expected test count. Register the next C only with a concrete one-question design and reproducible implementation/decision rules.

## Independent research tracks

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate,unimplemented candidates. Shared-Basis partition,Multi-Axis,local credit,KV/context,ranking,retrieval,admission,EvidenceState,readback,reobservation,Controller,typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not production clocks. Cross-source namespaces,revisions/retractions and durable publication/recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference,not the V5-E store.
