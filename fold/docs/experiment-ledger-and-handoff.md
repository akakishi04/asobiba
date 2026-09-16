# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md` and this handoff. One question per C number; invalid executions retry the same number and accepted negatives remain recorded.
- Latest accepted execution HEAD: C162 `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`. C163 is registered by the subsequent commit adding its module, tests, runner and addendum. Use that registration HEAD as explicit ExpectedHead, not C162's execution HEAD.

## Gate status and architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier cover binding/scope/authority, replay, atomic claim and recovery/fencing. C133-C135 introduce persisted retrieval; C136 fixed-address query formation; C137 dynamic content addressing. Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`. `docs/evidence-recovery-mode-v0.1.md` is separate, not implemented by these diagnostics.

## Accepted through C162

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity; dimension/encoding/seed changes prevent isolated hash-removal causality claims.
- C141 PASS oracle substitution only; C142 PASS small-task supervised color alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive factor accounting.
- C145 VALID NEGATIVE material alignment (1464->346 errors); C146 VALID NEGATIVE all-factor reference (476->11). Named-loss ladder closed.
- C147 VALID NEGATIVE frozen composition (11->4, 3 new errors); C148 VALID NEGATIVE train consistency (11->12, no rescue). C149 PASS arithmetic attribution, not unique causality or permission to remove cross terms.
- C150 PASS on original synthetic split. C151 PASS, 298 tests: four replacement splits, three paired initializations each. WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736. Nine control errors in S2/20261726; other three splits have no accuracy contrast. Minimum margins -0.0321333110/+0.1315777004. No independent language/task generalization. Synthetic ranker tuning closed.
- C152 PASS, 322 tests: 24 frozen heads/two layouts, full replay; 82944 real exact64 reads with correct selected identity/provenance/payload/cost. Source semantics 20727/layout versus 20736/layout.
- C153 PASS, 346 tests: 82944 retrievals, 580608 deliveries; 414720 malformed/stale rejections, 82944 valid request admissions and duplicate rejections each. Immutable diagnostic inbox, not durable publication.
- C154 PASS, 363 tests: 82944 entries -> 3072 ADDED, 79872 ALREADY_PRESENT; 3072 provenance conflicts rejected. 48 actual EvidenceStates x 64 refs, no payload. Classification caveat remains in the PC-ALM review addendum.
- C155 PASS, 388 tests: 12288 resolver cases, 3072 each RESOLVED/SOURCE_UNBOUND/SNAPSHOT_MISMATCH/RECORD_UNBOUND; 3072 reads/196608 vectors. Zero/one 1296/1776, no mutations/failures.
- C156 PASS, 412 tests: 82944 requests x four conditions = 331776 views. Real WorkingState/signed channels, no stale value or external clock change; 82944 reads/5308416 vectors, 331776 internal debits.
- C157 PASS, 440 tests: three C113-recipe routers, seeds 20261741..20261743, 900 CPU updates each; 1990656 recorded-input decisions over six patterns. All actions/margins/input/weight checks pass; minimum logit margin 5.344475269317627.
- C158 PASS, 475 tests: all 1990656 prior decisions replayed; 1920 live episodes/3456 decisions, 768 acquisitions, 384 restored refs, 1536 exact64 calls/98304 vectors. ANSWER_ACTION 768 / STOP 1152, values zero 324/one 444. All three frozen routers and five registered conditions pass. Denied/exhausted branches dispatch nothing. No generated answer or dynamic-world epoch.
- C159 ACCEPTED PASS, 508/508 tests; execution commit `741ca66e93e389ffc7e90688dc924e04695da778`. 1920 stored terminals -> 6528 emissions: ANSWERED 768, UNRESOLVED 1152. All 4608 registered controls rejected; no failures/mutations/serialization failures.
- **C160 ACCEPTED VALID NEGATIVE**, 546/546 tests; execution commit `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`. Full 82944 live query episodes, 5308416 candidate scores, 165888 Controller decisions, 82944 acquisitions/publications, 165888 exact64 calls / 10616832 vectors. Minimum margin 6.142457485198975; 27648 episodes/router. Nevertheless ANSWERED=0 and failed_episodes=82944. Execution and source protections passed.
- **C161 ACCEPTED PASS**, 558/558 tests; execution commit `97e26b5dfa71ac7998138050942bbfd107f3c46e`. Read-only analysis of 48 C160 traces: all 82944 stored cycle assessments passed; all outputs REJECTED/MALFORMED_EVIDENCE; no false cycle checks, all unbound but serialization-valid. Not an independent live rerun or revalidation of every stored evaluator assertion.
- **C162 ACCEPTED PASS**, 588/588 tests; execution commit `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`. Offline 82944 tuple/list differential pairs, all reconstructed-state digests/counts match. 82944 native rejections reproduced; list-only copies yield 82944 bound/source-payload-correct outputs, zero failed pairs/mutations/content changes. All 768 guard cases passed across 128 snapshot/record bindings. Values zero/one=34992/47952; semantic counts exact at 20727 WITHIN_FACTOR / 20736 GLOBAL_CONCEPT per layout. All 104 consumed inputs, protected C37/fixture, tree/HEAD and historical source blobs preserved.

C162 supports the observations-container explanation on reconstructed records through the unchanged emitter. EvidenceState is tuple-backed; C159 expects the JSON-loaded list form. The direct C160 live handoff lacked this conversion. **Live integration with the adapter is not yet measured**. C160 remains a valid negative with zero ANSWERED, not an INVALID retry or retroactive PASS. No checkpoint/threshold/case changes or repair of the known nine errors/layout (18 repeated instances) are allowed. Gate E stays NOT PASSED.

## Accepted artifact chain

**C162:** `runs/c162-v5e-evidence-container-a9f04a81882346c99d11c1cafa6f771c/summary.json`.
SHA256 `0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac`.
Plan `3c3c9049dd7ebd24c9c0a101d1dbe395f41721fc6440bac9f8786a6cdbc03f43`.
Guard controls `9270ebf5c21d2c9ee2e62d8e6fbaac93fcddf1bafe66a644dbe2d52e25b98373`.
Uploaded-log SHA256 `e055d84e43267a526f3db6de8982b4b4375e69e70b561f4e0d9671630c3a265d`.
C162 console omits records: no reviewer reconstruction of the full report hash or independent replay of local differential files is claimed.

**C161:** `runs/c161-v5e-c160-failure-localization-794f97af76da46c3b7b919f0f278f214/summary.json`.
SHA256 `2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38`.
**C160:** `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`.
SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
Query plan `656b53b55db3ed756a6421f767527857f8d71886c8e976735f3734d7160beb13`.
**C159:** `runs/c159-v5e-terminal-result-9e2b2e3e1f9c42bda1f33d7d49fa3cd7/summary.json`.
SHA256 `522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6`.
**C158:** `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`.
SHA256 `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
Episode plan `0f9d0703a28efc5d9e52a11e261fe58c83411fd75994d81428c4f217b3017f8c`.
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
Manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict/preregistration: **`docs/experiment-ledger-addendum-c162-c163.md`**.
Earlier registrations remain unchanged in `experiment-ledger-addendum-c161-c162.md`, `experiment-ledger-addendum-c160-c161.md`, `experiment-ledger-addendum-c159-c160.md` and chained addenda. Verdicts use uploaded console logs plus inspected source/registered gates; local artifacts are verified by subsequent user runs, not claimed independently replayed by the reviewer.

## Active C163 — Live evidence-container bridge

`C163-v5e-live-evidence-container-bridge`; `V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE`.
**ACTIVE / NOT YET JUDGED. No C164 registered.**

One question: does an observations-only tuple -> list adapter at the live terminal boundary make the unchanged frozen C160-style composition return bound typed bits, while native controls on the same fresh cycles reproduce the original rejection?

All 24 frozen C151 rankers, three C157 Controllers, two original C152 layouts, 1728 original queries, modulo-three router assignment, COLD_RECOVER, permission, budget(3,1), source ordering and clocks remain fixed. Zero training/fresh seeds. The new C163 request namespace carries identity only. No saved selected address or output substitutes for live inference. Preserve C158/C159/C160/core and C161/C162 source blobs. New adapter is diagnostic-only; no production rollout.

Pin C162 and C160 summaries above, C162 pair/guard files and all source hashes. This hash check is not a replay of C162's full differential. Reuse C160 prerequisite chain and 6528 old C159 emitter replays, 41472+288 ranker replays, same checkpoint loading. Do not repeat the old 1990656 C157 action replay or regenerate missing sources.

Expected NEW LIVE scope: **82944 episodes; 5308416 candidate scores; 165888 Controller decisions; 82944 acquisitions/restorations; 165888 exact64 calls / 10616832 vectors; 27648 episodes/router**. Every live native result yields one unadapted control and one adapted candidate: **82944+82944 emitter calls**, plus **768 guard calls** on 128 snapshot/record identities. Old 6528 emitter replay calls remain separate.

PASS requires the original C160 gate without threshold changes, all native controls MALFORMED_EVIDENCE, all adapted outputs bound/ANSWERED, content/input preservation, all six guard probes effective, and zero failure/mutation. Values zero/one=34992/47952. Per layout semantic_correct remains **20727 WITHIN_FACTOR / 20736 GLOBAL_CONCEPT** with 20736 bound outputs/arm. Save all new live traces/controls and rehash inputs/code at the end. Diagnostic timing includes controls, not production latency.

Finite behavior/guard/count/output defects with valid sources yield saved FAIL / VALID NEGATIVE. Wrong sources/schema/checkpoints/replays/code, nonfinite arithmetic or execution/postcheck failure yield INVALID / RETRY C163. Never rewrite C160/C161/C162 results. A PASS supports this controlled live adapter path only; Gate E remains NOT PASSED.

Files: `fold_lm/v05_benchmarks/gate_e_c163_live_container_bridge.py`, `tests_lm/test_v05_c163_live_container_bridge.py`, `tools/run_c163.ps1`.
Focused regression **614 = 588 previous + 26 new**. Reviewer passed **26 helper tests and Python compilation** using local excerpts of inspected dependency definitions (not a full checkout); the wiring test uses a controlled cycle callback. Full 614 tests, real artifact-backed CUDA/CPU integration and Windows PowerShell NOT reviewer-executed. No C163 result yet.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full accounting and quantified gates) stay in `experiment-ledger-addendum-c154-pcalm-review.md`. No hypothesis report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context work, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Epoch/generation mappings are diagnostic, not final production clocks. Cross-source namespaces, revisions/retractions, durable publication and recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
