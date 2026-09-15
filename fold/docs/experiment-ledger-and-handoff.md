# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read AGENTS.md, `docs/experiment-conversation-handoff-protocol.md` and this handoff. One question per C number. Invalid execution retries the same number; accepted negatives remain recorded.

## Gate status and architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier cover binding/scope/authority, replay, atomic claim, recovery/fencing. C133-C135 introduce persisted retrieval, C136 fixed-address query formation, C137 shared content addressing/dynamic candidates. Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` is separate and not implemented by these diagnostics.

## Accepted through C156

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity; hash-removal causality is not isolated across C138/C139's dimensional/encoding/seed changes.
- C141 PASS oracle substitution only. C142 PASS supervised color alignment on original small task. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive factor-mismatch accounting.
- C145 VALID NEGATIVE material alignment (1464->346 errors); C146 VALID NEGATIVE all-factor reference (476->11). Named-loss ladder closed.
- C147 VALID NEGATIVE frozen composition (11->4, 3 new errors); C148 VALID NEGATIVE train consistency (11->12, no rescue). C149 PASS arithmetic accounting, not unique causality or authorization to remove cross terms.
- C150 PASS original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736, minimum margins -0.0000681/+0.1425753. C151 PASS same-task cross-split replication, 298 tests: four replacement splits/three paired initializations each; WITHIN_FACTOR 20727/20736 and GLOBAL_CONCEPT 20736/20736. Nine control errors are in S2/20261726; other three splits have no accuracy contrast. Minimum margins -0.0321333110/+0.1315777004. Not independent language/task generalization.
- C152 PASS, 322 tests: 24 frozen heads, two layouts; full replay; 82944 exact64 adapter reads with correct selected identity/provenance/payload/cost. Source semantic correctness: WITHIN_FACTOR 20727/layout, GLOBAL_CONCEPT 20736/layout. No new learning.
- C153 PASS, 346 tests; commit `dc5f5d8bf72bc04692411c05213c824eb8c8c918`: 82944 retrievals, 580608 deliveries; 414720 registered malformed/stale rejections, 82944 valid request admissions, 82944 duplicate rejections. Immutable diagnostic inbox, not durable/production commit or Controller/ANSWER.
- C154 PASS, 363 tests; commit `8768303869d6ee24d72cc98a9690219a4205a495`: 82944 request entries -> 3072 ADDED, 79872 ALREADY_PRESENT; 3072 provenance conflicts rejected. Each of 48 actual EvidenceStates has 64 OBSERVED refs, no payload. Not 3072 distinct records or a measured compression ratio.
- C155 PASS, 388 tests; commit `ab8e29bc1d7fa3a9fa4cb786874aef4f5b881fe4`: 12288 resolver cases, 3072 each RESOLVED/SOURCE_UNBOUND/SNAPSHOT_MISMATCH/RECORD_UNBOUND. 3072 exact64 reads/196608 vectors; zero 1296 times, one 1776 times; failures/mutations zero. No Controller, training or new observation commit.
- **C156 ACCEPTED PASS**, 412/412 tests; execution commit `fe2b277341b62abf04bb51d284ce7fd288f15581`. 82944 original requests x 4 branches = 331776 views. RESOLVED/REFERENCE_UNBOUND/SOURCE_UNBOUND/SNAPSHOT_MISMATCH each 82944; resolved zero 34992/one 47952. 82944 actual exact64 reads/5308416 vectors. Behavioral, control-tensor, evidence-state and old-working-state failures all zero. 331776 internal debits; zero acquisition debits. All reported input/protected/tree/HEAD postchecks pass, `run_execution_valid=True`.

C156 maps the selected request-bound reference into actual WorkingState and canonical signed working channels. Valid zero retains presence; unresolved reads clear stale presence/value; other records are not substituted. Evidence clocks and state stay fixed. No learned Controller, action selection, ANSWER, live policy loop, durable commit or crash recovery has yet been established on this path.

Source semantics remain bookkeeping (20727/layout versus 20736/layout). Authentic irrelevant evidence is not repaired. These controlled repeated artifacts are not independent natural-language tasks. Diagnostic exact64 costs and wall times are not production throughput/VRAM evidence. Synthetic ranker tuning remains closed.

## Accepted artifact chain

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
Manifest SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan SHA256 `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict/preregistration: **`docs/experiment-ledger-addendum-c156-c157.md`**.
C156 original plan: `docs/experiment-ledger-addendum-c155-c156.md`; C155 plan: `docs/experiment-ledger-addendum-c154-c155.md`; C154 verdict/PC-ALM review: `docs/experiment-ledger-addendum-c154-pcalm-review.md`. Earlier evidence remains in chained addenda. Formal verdicts use user terminal logs and inspected source, not independently rerun full user artifacts. Subsequent formal runs verify printed report hashes against actual files.

## Active C157 — Learned Controller readback bridge

`C157-v5e-learned-controller-readback-bridge`; stage `V5-E-LEARNED-CONTROLLER-READBACK-BRIDGE`.
**ACTIVE, awaiting user CPU execution. No formal result claimed.**

Question: do accepted recorded working inputs plus explicit availability produce the appropriate actual learned action, including ANSWER for resolved zero and no ANSWER when unresolved?

```text
C156 JSONL working slots -> canonicalizer -> Controller working input
+ fixed context RETRIEVE_AVAILABLE (0,1,0,0) or NO_ACQUISITION (0,0,0,0)
+ operation ID 0
-> real ControlLaneActionRouter forward, no action override
```

Prepare **three new** reference routers via unchanged C113 `_train_router`: seeds **20261741, 20261742, 20261743**, 900 updates each, CPU float32/highest, two threads, width/control/hidden/action counts 8/4/8/6, AdamW lr .01. Existing logical training data/canonicalizer/natural sampling, no source cases or evaluation outcomes used for fitting. All three final-schedule routers are saved/reloaded and frozen before bridge evaluation. No checkpoint/seed selection, no ranker retraining. Training is not zero and this is not old-controller-checkpoint replay.

331776 source views x 2 contexts x 3 routers = **1990656 decisions**, 576 evaluation batches. **Only six distinct model input patterns**, not millions of independent reasoning tasks. Every row is evaluated; no prediction cache. Expected aggregate action counts: ANSWER 497664, RETRIEVE 746496, STOP_UNRESOLVED 746496. Matched zero/one both ANSWER; unresolved chooses RETRIEVE only in the explicitly available context, otherwise STOP. Presence is not relevance: the source's authentic wrong selections are not repaired.

Validate the exact C156 report, all 48 JSONL hashes/sizes and reaggregate request/scope/provenance/status/value/channels/clock/costs; hash all input artifacts listed by C156. Keep source trace order; save actual logits/actions/expected labels/margins per router/stream as NPZ plus source binding metadata. This is diagnostic storage only.

PASS requires every registered learned action and strictly positive finite expected-action logit margin, all three routers, exact counts and preserved input/weight state. Valid finite wrong actions/nonpositive margins or measured mutations yield FAIL and remain recorded. Bad source/hash/schema/recipe, nonfinite values or unexpected execution/outer guard errors are INVALID. No changing criteria or filtering seeds.

**ANSWER is an action ID, not generated answer text/value.** No external action executes, no live retrieval/reobservation, runtime authority enforcement, durable publication, learned relevance or end-to-end acquisition loop is tested. Context masks are hand-specified fixtures. Gate E stays NOT PASSED. C158 is not registered; judge C157 first.

Files: `gate_e_c157_controller_bridge.py`, `gate_e_c157_cli.py`, `tests_lm/test_v05_c157_controller_bridge.py`, `tools/run_c157.ps1`.
Reviewer **28/28 new CPU tests and compilation passed** with exact production Controller dependency. Synthetic full-shaped trace decoder, raw learned-forward interface, wrong-output retention, margins/checkpoint helpers verified. Fixed-recipe training wrapper tested with controlled trainer; no formal fresh router trained by reviewer. Full **440 tests**, actual artifact integration, formal training/evaluation and PowerShell not reviewer-executed.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented research candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full cost accounting and quantified gates) remain in `experiment-ledger-addendum-c154-pcalm-review.md`. No report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context work, ranking, retrieval, request admission, EvidenceState, payload readback, working-input reobservation, Controller and ANSWER remain different claims. Diagnostic epoch/generation-to-time/revision mapping is not a final production clock design. Cross-source namespaces, revisions/retractions, durable publication and fault recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
