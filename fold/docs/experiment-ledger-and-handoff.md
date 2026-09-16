# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and the current addendum before work. Judge -> record ledger/handoff -> next C. One question per C; invalid execution retries the same number; accepted valid negatives remain recorded.
- Latest accepted execution: **C165** at `4dfc1634ea4a18f70390807011a83f60654e1b00`. Verdict: `docs/experiment-ledger-addendum-c165-c166.md`, first recorded in `0a4b0d472501286f4e20a0c831e9e71712355750` before next-C design. Do not confuse execution HEAD with later documentation/registration HEAD.

## Gate status / architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.

```text
learned Control Lane -> authoritative permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

Production retrieval head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Persisted adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` is a separate design, not implemented by these diagnostics.

## Accepted evidence through C165

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity. C141 PASS oracle localization; C142 PASS small supervised alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive attribution. C145-C148 include accepted negative interventions; C149 PASS arithmetic attribution. C150 PASS original synthetic split. Earlier details remain in chained addenda.
- **C151 PASS**, 298 tests: four replacement splits x three paired initializations. WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736. Nine control errors occur in S2/20261726; synthetic ranker tuning is closed, without independent task/language generalization.
- **C152 PASS**, 322 tests: 24 frozen heads x two layouts, 82,944 exact64 reads preserving selected identity/provenance/payload/cost.
- **C153 PASS**, 346 tests: 82,944 reads, 580,608 deliveries, 414,720 invalid rejections, 82,944 valid admissions and duplicate rejections each; immutable diagnostic inbox, not durable publication.
- **C154 PASS**, 363 tests: 82,944 entries -> 3,072 ADDED / 79,872 ALREADY_PRESENT, 3,072 conflicts rejected; 48 states x 64 references. Classification caveat remains in `experiment-ledger-addendum-c154-pcalm-review.md`.
- **C155 PASS**, 388 tests: 12,288 resolver cases, four status classes; 3,072 reads/196,608 vectors; zero/one 1,296/1,776.
- **C156 PASS**, 412 tests: 82,944 requests x four conditions = 331,776 views; zero/unresolved separation, no stale payload or external-clock advance.
- **C157 PASS**, 440 tests: three learned Controllers, seeds 20261741..20261743, 900 CPU updates each; 1,990,656 recorded-input decisions; minimum margin 5.344475269317627.
- **C158 PASS**, 475 tests: preselected-record live warm/recover/missing-delivery/permission-denied/budget-exhausted cases. 1,920 episodes/3,456 decisions; 768 acquisitions, 384 restorations, 1,536 exact64 calls/98,304 vectors. ANSWER 768 / STOP 1,152; not raw-query selection.
- **C159 PASS**, 508 tests: stored-terminal emitter, 1,920 terminals -> 6,528 emissions; ANSWERED 768 / UNRESOLVED 1,152; 4,608 controls rejected.
- **C160 ACCEPTED VALID NEGATIVE**, 546 tests, execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`: 82,944 complete live query cycles with expected retrieval/accounting but ANSWERED=0 / failed=82,944. Never retroactively relabel this run.
- **C161 ACCEPTED PASS**, 558 tests, execution `97e26b5dfa71ac7998138050942bbfd107f3c46e`: all 82,944 stored cycle assessments pass; single post-cycle rejection MALFORMED_EVIDENCE.
- **C162 ACCEPTED PASS**, 588 tests, execution `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`: 82,944 digest-verified reconstructed tuple/list pairs; native rejection versus bound list output; 768 guards pass. Offline reconstruction, not original heap capture.
- **C163 ACCEPTED PASS**, 614 tests, execution `d3cecf1c1221d2119a2e6ab172c69770bde46788`: 82,944 new live raw-query cycles yield bound ANSWERED after observations-only normalization; same-cycle native controls all reject MALFORMED_EVIDENCE. 5,308,416 candidate scores, 165,888 decisions, 82,944 acquisitions/restorations, 165,888 calls/10,616,832 vectors. All 768 guards and 494 input checks pass; zero mutations/failures.
- **C164 ACCEPTED PASS**, 638 tests, execution `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`: 82,944 new ranking prefixes x normal/missing-delivery fresh continuations = 165,888 branch episodes. ANSWERED 82,944 / UNRESOLVED-MISSING_DELIVERY 82,944. 331,776 decisions, 165,888 real acquisitions, 82,944 publications, 248,832 calls/15,925,248 vectors. Missing branch never publishes/rereads. All 768 guards and 545 input checks pass; zero failures.
- **C165 ACCEPTED PASS**, **665/665 tests**, execution `4dfc1634ea4a18f70390807011a83f60654e1b00`: 82,944 new rankings x allowed/permission-denied fresh continuations = 165,888 branch episodes with zero failures. 331,776 raw decisions; 82,944 acquisitions/restorations; 165,888 adapter calls/10,616,832 vectors. Allowed ANSWERED=82,944; denied UNRESOLVED/PERMISSION_DENIED=82,944, with zero actual adapter calls/acquisitions/publications/readbacks and acquisition budget held at 1. All denied first authorities are PERMISSION_DENIED; raw RETRIEVE proposals are not overridden. All 768 guards, 596 consumed inputs, historical blobs, tracked tree and execution HEAD pass. No weight/output mutations or serialization failures.

## Current scientific boundary

C165 establishes runtime permission enforcement in the fixed synthetic raw-query -> selection -> bounded cycle -> typed result path. C164 separately established post-fetch transport loss handling. Normal branches retain 20,736 bound outputs per arm/layout with semantic_correct WITHIN_FACTOR=20,727 / GLOBAL_CONCEPT=20,736; zero/one totals 34,992/47,952. The known nine errors x two layouts remain 18 repeated instances, not new error types. Denied/missing semantic_correct is null; unresolved is neither zero nor evidence of nonexistence.

C165 first proposals are RETRIEVE even when permission is false. Runtime blocks dispatch; reobservation/unavailability leads the learned Controller to STOP. This is not a learned general policy-understanding claim. Zero denied adapter calls does not mean zero catalog ranking or zero prerequisite file access: shared rankings and artifact validation still execute. No OS/security isolation or confidential-catalog-access guarantee is measured.

C160 remains an accepted valid negative. Authoritative EvidenceState remains tuple-backed; the C163 observations-only output bridge and C159 emitter are unchanged. No checkpoint/threshold/case changes repair known semantic errors. Repeated episodes measure fixed-fixture coverage, not independent task generalization. No raw-query budget-exhausted/warm integration, initially empty world, changing external epochs, relevance abstention, generated answers, durable publication or production rollout is established by C165. Diagnostic timing/allocator data is not final FOLD performance. **Gate E remains NOT PASSED.**

## Accepted artifact chain

**C165:** `runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`.
SHA256 `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
Plan `5d84b8a80dad07487c936393625f72267a0ffb8266e29ee69b2edba6eda3ebea`.
Controls `8c6ada9f2e8f694736e4ca381509d487d566883cd1097514b6973998a08a3f3b`.
Uploaded-log SHA256 `01a3c05d7c08b59be6682ff2593fe524522cfc50c892f1efc90309bbcf9fcc1b`.

**C164:** `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`, SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`, SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
**C162:** `runs/c162-v5e-evidence-container-a9f04a81882346c99d11c1cafa6f771c/summary.json`, SHA256 `0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac`.
**C161:** `runs/c161-v5e-c160-failure-localization-794f97af76da46c3b7b919f0f278f214/summary.json`, SHA256 `2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38`.
**C160:** `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`, SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
**C159:** `runs/c159-v5e-terminal-result-9e2b2e3e1f9c42bda1f33d7d49fa3cd7/summary.json`, SHA256 `522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6`.
**C158:** `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`, SHA256 `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
**C157:** `runs/c157-v5e-controller-bridge-e68cc92a350145b983d123acad386982/summary.json`, SHA256 `b521eafc61fedaf3b9d2f78fb9c591de654b95cfa6689938c8c042fbc200b934`.
C151-C156 identities/paths and earlier history remain in `experiment-ledger-addendum-c164-c165.md`, the chained addenda and pinned input manifests. C151 SHA `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`; manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`; split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c165-c166.md`**.
Completed preregistration: `docs/experiment-ledger-addendum-c165-preregistration.md`.
Reviewer scope: complete uploaded console JSON/aggregate/progress/postcheck consistency plus source/preregistration review. Console omits records; no independent full report hash reconstruction or user-side raw trace/model rerun is claimed.

## Next-C boundary

**Accepted through C165. No active new C; C166 is not yet registered.**
The acceptance/handoff update precedes next-C design. Keep prior code, artifacts, failure classifications and scientific gates unchanged. A subsequent one-question preregistration must state its own counts, controlled variables, interpretation limits, runner/regression/protection requirements and stop condition before execution.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. PC-ALM report on main remains independent. Shared-Basis partition, Multi-Axis, local credit, KV/context, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not final production clocks. Cross-source namespaces, revisions/retractions, durable publication and recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
