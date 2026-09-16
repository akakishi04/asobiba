# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md` and this handoff. One question per C number; invalid executions retry the same number and accepted negatives remain recorded.

## Gate status and architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier cover binding/scope/authority, replay, atomic claim and recovery/fencing. C133-C135 introduce persisted retrieval; C136 fixed-address query formation; C137 dynamic content addressing. Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`. `docs/evidence-recovery-mode-v0.1.md` is separate, not implemented by these diagnostics.

## Accepted through C160

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
- C159 ACCEPTED PASS, 508/508 tests; execution commit `741ca66e93e389ffc7e90688dc924e04695da778`. 1920 stored terminals -> 6528 emissions: ANSWERED 768, UNRESOLVED 1152. All 4608 registered wrong-request/provenance/payload/ungrounded-answer controls rejected; no failures/mutations/serialization failures.
- **C160 ACCEPTED VALID NEGATIVE**, 546/546 tests; execution commit `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`. Full 82944 live query episodes completed with 5308416 ranker candidate scores, 165888 Controller decisions, 82944 acquisitions, 82944 publications, 165888 exact64 calls / 10616832 vectors and exact 27648 episodes per Controller. Minimum Controller margin 6.142457485198975; mutations/serialization failures zero. Nevertheless `answered=0`, `failed_episodes=82944`, and every arm/layout reports `binding_correct=0`, `semantic_correct=0`. Protected artifacts/tree/HEAD passed and `diagnostic_execution_valid=true`.

C160 therefore does not establish live query-to-result composition. It is a valid negative, not an invalid retry. The C151 ranking replay, C157 Controller margins, acquisition/publication counts, exact read costs and old C159 replay all remain accepted, so the unresolved question is the shared composition boundary between the preserved C158-style cycle result and the C159 typed terminal contract. C160's console aggregate does not reveal whether stored C158 cycle assessments themselves failed or whether one/multiple terminal guards rejected otherwise accepted cycles.

Do not retrain, select new checkpoints, change thresholds, shrink coverage, alter the known 18 WITHIN_FACTOR semantic control errors, or rerun C160 merely to obtain PASS. Gate E remains NOT PASSED.

## Accepted artifact chain

**C160:** `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`.
SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
Query-cycle plan SHA256 `656b53b55db3ed756a6421f767527857f8d71886c8e976735f3734d7160beb13`.
Uploaded console-log SHA256 `98eafa0e628e1d214ba3f9c63cf1eee22c7bd3708092932be51026f2c1d3fc43`.

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

Current verdict/preregistration: **`docs/experiment-ledger-addendum-c160-c161.md`**.
Previous plans/verdicts remain in `experiment-ledger-addendum-c159-c160.md`, `experiment-ledger-addendum-c158-c159.md`, `experiment-ledger-addendum-c157-c158.md` and chained addenda. Formal verdicts use user console logs plus inspected source/registered gates, not independently replayed full local artifacts; subsequent local runs verify report/trace hashes against real files.

## Active C161 — C160 failure-boundary localization

`C161-v5e-c160-failure-boundary-localization`; `V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION`.
**ACTIVE / NOT YET JUDGED.**

Question: **is the universal C160 failure entirely a single post-cycle terminal rejection after an otherwise accepted C158 cycle assessment?**

C161 is read-only. It consumes the accepted C160 summary SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd` and the 48 gzip traces whose hashes/sizes are registered inside that summary. It executes **no model forward, retrieval, acquisition, publication, live cycle or emitter repair**, and performs zero training/fresh seeds.

Coverage is fixed at **48 traces x 1728 rows = 82944 episodes**. It aggregates stored `cycle_assessment.passed/checks/margins`, terminal `output.status/reason`, `output_assessment.bound/serialization_ok`, boundary classes, arm/layout partitions and router coverage. It saves compact examples only; C160 rows are never rewritten.

PASS requires all 82944 stored cycle assessments to pass, no false cycle checks, all outputs to be REJECTED for one and only one common reason, all outputs unbound but serialization-valid, and every row to classify as `POST_CYCLE_TERMINAL_REJECTION`. This PASS localizes a failure reason only; it does not repair C160 or advance Gate E.

A valid complete trace set that contains any cycle-assessment failure, multiple terminal reasons or multiple failure boundaries is **ACCEPTED VALID NEGATIVE / FAIL** for C161's single-boundary hypothesis. Wrong C160 hash/profile, missing/tampered traces, malformed schema, incomplete coverage/router schedule or postcheck failure is **INVALID / RETRY C161**.

Files:
- `fold_lm/v05_benchmarks/gate_e_c161_failure_localization.py`
- `tests_lm/test_v05_c161_failure_localization.py`
- `tools/run_c161.ps1`

Focused regression target: **558 tests = prior 546 + 12 C161 helper tests**. The helper tests are registered; the formal user regression and real 48-trace diagnostic are not yet executed. Do not preregister a repair C162 until C161 is judged.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full accounting and quantified gates) stay in `experiment-ledger-addendum-c154-pcalm-review.md`. No hypothesis report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context work, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Epoch/generation mappings are diagnostic, not final production clocks. Cross-source namespaces, revisions/retractions, durable publication and recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
