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

## Accepted through C158

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity; C138/C139 do not isolate hash-removal causality across their dimension/encoding/seed changes.
- C141 PASS oracle substitution only. C142 PASS supervised color alignment on the original small task. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive factor accounting.
- C145 VALID NEGATIVE material alignment (1464->346 errors); C146 VALID NEGATIVE all-factor reference (476->11). Named-loss ladder closed.
- C147 VALID NEGATIVE frozen composition (11->4, 3 new errors); C148 VALID NEGATIVE train consistency (11->12, no rescue). C149 PASS arithmetic accounting, not unique causality or authorization to remove cross terms.
- C150 PASS original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736. C151 PASS, 298 tests: four replacement splits/three paired initializations each; WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736. Nine control errors are in S2/20261726; other three splits have no accuracy contrast. Minimum margins -0.0321333110/+0.1315777004. Not independent language/task generalization. Synthetic ranker tuning closed.
- C152 PASS, 322 tests: 24 frozen heads, two layouts, full replay; 82944 exact64 adapter reads with preserved selected identity/provenance/payload/cost. Source semantic correctness: WITHIN_FACTOR 20727/layout; GLOBAL_CONCEPT 20736/layout.
- C153 PASS, 346 tests: 82944 retrievals, 580608 deliveries; 414720 malformed/stale rejections, 82944 valid request admissions, 82944 duplicate rejections. Immutable diagnostic inbox, not durable publication.
- C154 PASS, 363 tests: 82944 entries -> 3072 ADDED, 79872 ALREADY_PRESENT; 3072 provenance conflicts rejected. Each of 48 actual EvidenceStates has 64 OBSERVED refs, no payload. C154's classification caveat remains in the PC-ALM review addendum.
- C155 PASS, 388 tests: 12288 resolver cases, 3072 each RESOLVED/SOURCE_UNBOUND/SNAPSHOT_MISMATCH/RECORD_UNBOUND. 3072 reads/196608 vectors; zero 1296 times, one 1776 times; failures/mutations zero.
- C156 PASS, 412 tests: 82944 original requests x four branches = 331776 views. Actual WorkingState and signed control channels; no stale-payload leakage, state mutation, clock advancement or acquisition debit. 82944 exact64 reads/5308416 vectors; 331776 internal-step debits.
- C157 PASS, 440 tests: three newly trained C113-recipe reference routers, seeds 20261741..20261743, 900 CPU updates each. 1990656 recorded-view decisions over six distinct input patterns; zero action/margin/input/weight failures. Minimum expected-action margin 5.344475269317627; all three pass. Not generated answers or independent reasoning tasks.
- **C158 ACCEPTED PASS**, 475/475 tests; execution commit `1b407ef26d6c1f5575482e07f6c8d046a3bff438`. Full 1990656 C157 decisions replayed. All 1920 live episodes pass: 3456 Controller decisions/internal debits, 768 authorized acquisitions, 384 restored refs, 1536 actual exact64 calls/98304 vectors. Terminal ANSWER_ACTION 768/STOP_UNRESOLVED 1152; observed zero 324/one 444. Permission-denied and exhausted-budget branches have zero fetches. All three frozen routers pass, no weight mutation; protected/tree/HEAD checks pass.

C158 connects learned action -> authorized acquisition -> sequential in-process admission/projection -> live reobservation -> terminal action. It restores only an already selected reference within a pinned observation epoch, not a new query choice or changing-world observation. ANSWER is still an action with readback metadata, not generated/computed answer content. Runtime permission/budget/attempt caps are explicit. No durability, crash recovery or concurrency claim follows. Source semantic counts are bookkeeping; authentic irrelevant evidence is not repaired. Exact64 costs and total diagnostic timings are not production performance.

## Accepted artifact chain

**C158:** `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`.
SHA256 `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
Episode plan SHA256 `0f9d0703a28efc5d9e52a11e261fe58c83411fd75994d81428c4f217b3017f8c`.
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
Manifest SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan SHA256 `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict/preregistration: **`docs/experiment-ledger-addendum-c158-c159.md`**.
C158 original plan: `docs/experiment-ledger-addendum-c157-c158.md`. Earlier plans/verdicts remain in chained addenda, including `experiment-ledger-addendum-c156-c157.md`, `experiment-ledger-addendum-c155-c156.md` and `experiment-ledger-addendum-c154-pcalm-review.md`. Formal verdicts use user logs and inspected source, not independently rerun full artifacts. Subsequent local runs verify runner-printed report hashes against actual files.

## Active C159 — Evidence-bound terminal result

`C159-v5e-evidence-bound-terminal-result`; stage `V5-E-EVIDENCE-BOUND-TERMINAL-RESULT`.
**ACTIVE, awaiting user CPU execution. No C159 result claimed.**

Question: can the accepted recorded terminal state become a request/snapshot-bound typed return without zero/None confusion, wrong-request evidence or raw fetched-but-unadmitted leakage?

```text
C158 plan + terminal JSONL (hash pinned and fully reaggregated)
-> immutable request binding
-> deterministic emit_terminal, no expected value/scenario/corpus input
-> ANSWERED observed bit with source binding / UNRESOLVED / REJECTED
-> JSON roundtrip
```

No model load, neural scoring, training, fresh seeds, retrieval, live-cycle rerun, state commit or generated answer content. This is a recorded-output contract bridge. ANSWERED copies validated final working payload; it is not a learned semantic answer. Unresolved/rejected results retain request/scope but expose no value or supporting evidence. Reasons come from recorded runtime state, not scenario labels. A guard rejection is not a learned successful STOP and does not overwrite the original action.

Require C158 full summary/plan/three 640-row JSONL and all upstream input hashes. Reaggregate actions and margins, state identity/clocks, values, budgets, acquisitions/publications, costs and scenario counts before the new boundary. Missing/modified inputs are INVALID, not reconstructed. Source records remain untouched.

Base **1920 outputs: 768 ANSWERED (324 zero / 444 one), 1152 UNRESOLVED**. Four independent output-fault controls: WRONG_REQUEST 1920; WRONG_PROVENANCE 768; PAYLOAD_DISAGREEMENT 768; FORCED_UNGROUNDED_ANSWER 1152. Total **4608 controls / 6528 emitter calls**. Output faults are deliberate copies, not new learned failures or independent tasks. Save all results/checks in source-bound per-router JSONL. Diagnostic schema `c159-terminal-result-v1`, not production API/durability.

PASS: exact base status/value and control rejection counts/reasons, no usable payload on failures, zero mutations/serialization failures and all protections. Valid bad output is FAIL and saved; bad source/hash/reaggregation/setup is INVALID and retries C159. Gate E remains NOT PASSED. C160 is not registered; judge C159 first.

Files: `gate_e_c159_terminal_result.py`, `gate_e_c159_cli.py`, `tests_lm/test_v05_c159_terminal_result.py`, `tools/run_c159.ps1`.
Reviewer **33/33 new standard-library CPU tests and compilation passed**. Fabricated full-size source integration passed; an injected emitter defect produced a valid FAIL, input tampering produced INVALID. No actual user episode files were available. Full **508 tests**, real artifact-chain integration and PowerShell remain unexecuted by reviewer.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented research candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full cost accounting and quantified gates) remain in `experiment-ledger-addendum-c154-pcalm-review.md`. No report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context work, ranking, retrieval, request admission, EvidenceState, payload readback, working reobservation, Controller, typed return and learned ANSWER are separate claims. Diagnostic epoch/generation-to-time/revision mapping is not the final production clock design. Cross-source namespaces, revisions/retractions, durable publication and fault recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
