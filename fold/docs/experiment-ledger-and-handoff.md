# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and the current addendum before work. Judge -> record ledger/handoff -> next C. One question per C; invalid execution retries the same number; valid negatives remain recorded.
- Latest accepted execution: C163 at `d3cecf1c1221d2119a2e6ab172c69770bde46788`. Verdict recorded in `5b462d453ed1c6f826787c08be1cb1cebe15f847` before C164 registration. C164's runner requires its current registration HEAD, not the old execution HEAD.

## Gate status / architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier cover binding/scope/authority, replay, atomic claim and recovery/fencing. C133-C135 introduce persisted retrieval; C136 fixed-address query formation; C137 dynamic content addressing. Production head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`. `docs/evidence-recovery-mode-v0.1.md` is a separate design, not implemented by these diagnostics.

## Accepted evidence through C163

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity; dimension/encoding/seed changes prevent isolated hash-removal causality claims.
- C141 PASS oracle substitution only; C142 PASS small-task supervised color alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive factor accounting.
- C145 VALID NEGATIVE material alignment (1464->346 errors); C146 VALID NEGATIVE all-factor reference (476->11). Named-loss ladder closed.
- C147 VALID NEGATIVE frozen composition (11->4, three new errors); C148 VALID NEGATIVE train consistency (11->12, no rescue). C149 PASS arithmetic attribution, not unique causality or permission to remove cross terms.
- C150 PASS original synthetic split. C151 PASS, 298 tests: four replacement splits x three paired initializations. WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736; nine control errors in S2/20261726, no accuracy contrast on other splits. Minimum margins -0.0321333110/+0.1315777004. Synthetic ranker tuning closed; no independent task/language generalization.
- C152 PASS, 322 tests: 24 frozen heads/two layouts, full replay, 82944 real exact64 reads, selected identity/provenance/payload/cost preserved. C153 PASS, 346 tests: 82944 reads, 580608 deliveries, 414720 invalid rejections, 82944 valid admissions and duplicate rejections each; immutable diagnostic inbox, not durable publication.
- C154 PASS, 363 tests: 82944 entries -> 3072 ADDED, 79872 ALREADY_PRESENT, 3072 conflicts rejected; 48 EvidenceStates x 64 references without payload. Classification caveat remains in `experiment-ledger-addendum-c154-pcalm-review.md`.
- C155 PASS, 388 tests: 12288 resolver cases, four status classes of 3072 each; 3072 reads/196608 vectors; zero/one 1296/1776. C156 PASS, 412 tests: 82944 requests x four conditions = 331776 views, real WorkingState/signed channels, no stale payload/clock advance; 82944 reads/5308416 vectors, 331776 internal debits.
- C157 PASS, 440 tests: three C113-recipe Controllers, seeds 20261741..20261743, 900 CPU updates each; 1990656 recorded-input decisions; minimum margin 5.344475269317627.
- C158 PASS, 475 tests: full 1990656-decision replay; 1920 live selected-record episodes/3456 decisions, 768 acquisitions, 384 restorations, 1536 exact64 calls/98304 vectors. ANSWER_ACTION 768/STOP 1152, values zero 324/one 444. Five conditions and all three routers passed; denied/exhausted dispatch nothing.
- C159 PASS, 508 tests: recorded-trace emitter only, 1920 terminals -> 6528 emissions, ANSWERED 768, UNRESOLVED 1152; all 4608 fault controls rejected. No new live cycle.
- **C160 ACCEPTED VALID NEGATIVE**, 546 tests, execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`: complete 82944 live query episodes, 165888 decisions, 82944 acquisitions/restorations, 165888 reads/10616832 vectors; nevertheless ANSWERED=0 and failed=82944. Valid execution; never retroactively relabel or rerun merely for PASS.
- **C161 ACCEPTED PASS**, 558 tests, execution `97e26b5dfa71ac7998138050942bbfd107f3c46e`: all 82944 stored cycle assessments pass; all outputs REJECTED/MALFORMED_EVIDENCE. Read-only localization, not independent live revalidation.
- **C162 ACCEPTED PASS**, 588 tests, execution `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`: 82944 digest-verified offline tuple/list pairs; native rejection reproduced, list output bound and observed-value correct, all 768 guards pass. Zero/one 34992/47952; semantic boundary preserved. Reconstructed objects, not original heap capture.
- **C163 ACCEPTED PASS**, 614/614 tests, execution `d3cecf1c1221d2119a2e6ab172c69770bde46788`: all **82944 fresh live query cycles** yield bound typed ANSWERED after observations-only normalization. On those same cycles all 82944 native controls still reject MALFORMED_EVIDENCE. 5308416 candidate scores, 165888 Controller decisions, 82944 acquisitions/restorations, 165888 exact64 calls/10616832 vectors; 27648 episodes/router. Margin 6.142457485198975, zero mutations/serialization failures, all 768 guards pass. Zero/one 34992/47952. All 494 consumed inputs, historical source blobs, tracked tree and execution HEAD preserved.

C163 establishes the diagnostic raw-query -> frozen selection -> live authorized recovery -> adapted typed observed-bit path on the fixed synthetic task. Each arm/layout has 20736 bound outputs; semantic_correct is WITHIN_FACTOR 20727 and GLOBAL_CONCEPT 20736. The known nine errors repeated over two layouts remain 18 instances, not new error types. No truth/target repair, threshold change, new checkpoint or fresh training is allowed.

The original C160 failure remains accepted. Authoritative EvidenceState remains tuple-backed; the diagnostic adapter changes only the outgoing observations container. Historical C158/C159/C160/core and C161/C162 are untouched. C163 does not measure failed-delivery query cycles, permission/budget-denied query cycles, learned/generated answers, relevance abstention, initially empty worlds, changing epochs, durable publication or production rollout. Repeated episodes are not independent task generalization; exact64 costs and diagnostic allocator/timing fields are not production performance. **Gate E remains NOT PASSED.**

## Accepted artifact chain

**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`.
SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
Plan `884e5f63ef4a462bc228fde19a24be5d96e843bcd4ab692ae2cfad693969ffa9`.
Controls `d165b06f2ba1bec5205e336c697b2a5bc5dc2d69e1602d786c416dea03ae9e3d`.
Uploaded-log SHA256 `7dc7cb7d151fd82f3cbd094ca4e3e4c5eeedade25e2a1b857da78ac8d560c15c`.
**C162:** `runs/c162-v5e-evidence-container-a9f04a81882346c99d11c1cafa6f771c/summary.json`.
SHA256 `0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac`.
**C161:** `runs/c161-v5e-c160-failure-localization-794f97af76da46c3b7b919f0f278f214/summary.json`.
SHA256 `2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38`.
**C160:** `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`.
SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
**C159:** `runs/c159-v5e-terminal-result-9e2b2e3e1f9c42bda1f33d7d49fa3cd7/summary.json`.
SHA256 `522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6`.
**C158:** `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`.
SHA256 `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
**C157:** `runs/c157-v5e-controller-bridge-e68cc92a350145b983d123acad386982/summary.json`.
SHA256 `b521eafc61fedaf3b9d2f78fb9c591de654b95cfa6689938c8c042fbc200b934`.
**C156:** `runs/c156-v5e-request-reobservation-0d0d4cb6c1704c4987ebf8651fc683e0/summary.json`.
SHA256 `b2c43401a6731400de8e18697f82f5e220aeb3f2368737d9dee5847f7ca1f84f`.
**C155:** `runs/c155-v5e-payload-dereference-2e18c0303d69421e8f1d21f9d0a3e2a1/summary.json`.
SHA256 `1ac82ec4c4e60e6c7586058d497096d602a861e191909ca2adfd685f1f2fb4aa`.
**C154:** `runs/c154-v5e-evidence-state-projection-ddacda18a60e4b7b91c370155ae5551c/summary.json`.
SHA256 `4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284`.
**C153:** `runs/c153-v5e-evidence-admission-6a96d53560a0454082d0ae22c143fdf0/summary.json`.
SHA256 `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
**C152:** `runs/c152-v5e-persisted-bridge-c14bc4bd93e64087991290cb92e2b42a/summary.json`.
SHA256 `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
**C151:** `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
SHA256 `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`; split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c163-c164.md`**.
Current preregistration: **`docs/experiment-ledger-addendum-c164-preregistration.md`**.
Historical registrations/verdicts stay in `experiment-ledger-addendum-c162-c163.md`, `experiment-ledger-addendum-c161-c162.md`, `experiment-ledger-addendum-c160-c161.md`, `experiment-ledger-addendum-c159-c160.md` and earlier chained addenda. Verdicts use uploaded console logs plus inspected source and preregistered gates. C163 console omits `records`: no reconstructed full report hash or independent reviewer trace replay is claimed.

## Active C164 — Live query missing delivery

`C164-v5e-live-query-missing-delivery`; `V5-E-LIVE-QUERY-MISSING-DELIVERY`.
**ACTIVE / NOT YET JUDGED. No C165 registered.**

Question: does a real acquisition whose evidence is removed during delivery produce payload-free typed UNRESOLVED through the frozen query-originating path, while matched normal delivery still answers?

Only the transport callback changes: normal returns the actual Delivery; missing returns `replace(fetched, evidence=None)` after real fetch, preserving the envelope. It is not a bare None envelope, nonexistent target, retrieval miss, permission denial, budget change or semantic abstention. C163's diagnostic tuple/list adapter, C159 emitter, C158 cycle, all 24 rankers, three Controllers, two layouts, clocks, initial budget(3,1), stale bit and 63 other references stay fixed. Zero training/fresh seeds, no production/historical source changes. Request namespace includes condition for disjoint identity, not as a learned feature.

Run **82944 fresh ranking prefixes / 5308416 candidate scores**. Each live selection feeds normal and missing-delivery cold continuations with fresh independent state/inbox/budget; normal first. This is **165888 branch episodes**, not twice as many independent queries or cached historical predictions. Expected totals: **331776 decisions, 165888 actual acquisitions, 82944 restorations, 248832 exact64 calls / 15925248 vectors**. Each Controller handles 27648 episodes per condition (55296 total). Raw actions: RETRIEVE 165888, ANSWER 82944, STOP 82944.

Normal output: 82944 ANSWERED, zero/one 34992/47952, per-layout WITHIN_FACTOR semantic20727 and GLOBAL_CONCEPT20736 with all20736 bindings intact. Missing output: 82944 UNRESOLVED/MISSING_DELIVERY with value/key/source/time/revision allNone, no publication/readback, stale presence/payload cleared. Missing semantic_correct is null/notapplicable; unresolved is not zero or proof of absence. The known nine errors/layout are not corrected.

Use unchanged C163 AuditedEmitter: 165888 native controls, 165888 candidate calls, 768 guards on first normal source-record identities. New emitter total332544; old C1596528 replay calls separate. Save 48 gzip traces x3456rows plus controls. Pin accepted C163 summary/all source and trace hashes, then existing C15141472+288 ranker replay and C159 recorded-output replay; no new C157 large action replay. Rehash inputs/code at end and independently in the runner.

PASS requires the unchanged original C160 success gate on the matched normal branch, all existing C158 missing-delivery checks and exact typed no-payload contract, positive finite margins, exact coverage/actions/budgets/costs and independent meter agreement, native rejection/type/content/preservation checks and all guards. Valid finite defects are saved FAIL/VALID NEGATIVE; source/schema/hash/code/replay/numeric/execution/postcheck invalidity retries C164 without changing its science. Never rewrite C160/C163 runs. Gate E stays NOT PASSED.

Files: `fold_lm/v05_benchmarks/gate_e_c164_live_missing_delivery.py`, `tests_lm/test_v05_c164_live_missing_delivery.py`, `tools/run_c164.ps1`.
Focused regression **638 = 614 previous + 24 new**. Reviewer compiled both Python files and passed **19 dependency-light tests** using inspected excerpts/test doubles. Five actual C158-cycle/adapter wiring test methods were not reviewer-executed; no complete historical dependency import/full638/realCUDA-CPU/PowerShell run is claimed. Formal C164 has no result yet. Stop after execution for judgment and ledger update before C165.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full accounting and quantified gates) remain in `experiment-ledger-addendum-c154-pcalm-review.md`. No hypothesis report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not final production clocks. Cross-source namespaces, revisions/retractions, durable publication and recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
