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

## Accepted through C157

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity; C138/C139 do not isolate hash-removal causality across their dimension/encoding/seed changes.
- C141 PASS oracle substitution only. C142 PASS supervised color alignment on the original small task. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive factor accounting.
- C145 VALID NEGATIVE material alignment (1464->346 errors); C146 VALID NEGATIVE all-factor reference (476->11). Named-loss ladder closed.
- C147 VALID NEGATIVE frozen composition (11->4, 3 new errors); C148 VALID NEGATIVE train consistency (11->12, no rescue). C149 PASS arithmetic accounting, not unique causality or authorization to remove cross terms.
- C150 PASS original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736. C151 PASS, 298 tests: four replacement splits/three paired initializations each; WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736. Nine control errors are in S2/20261726; other three splits have no accuracy contrast. Minimum margins -0.0321333110/+0.1315777004. Not independent language/task generalization. Synthetic ranker tuning closed.
- C152 PASS, 322 tests: 24 frozen heads, two layouts, full replay; 82944 exact64 adapter reads with preserved selected identity/provenance/payload/cost. Source semantic correctness: WITHIN_FACTOR 20727/layout; GLOBAL_CONCEPT 20736/layout.
- C153 PASS, 346 tests: 82944 retrievals, 580608 deliveries; 414720 malformed/stale rejections, 82944 valid request admissions, 82944 duplicate rejections. Immutable diagnostic inbox, not durable publication.
- C154 PASS, 363 tests: 82944 entries -> 3072 ADDED, 79872 ALREADY_PRESENT; 3072 provenance conflicts rejected. Each of 48 actual EvidenceStates has 64 OBSERVED refs, no payload. C154's classification caveat remains in the PC-ALM review addendum.
- C155 PASS, 388 tests: 12288 resolver cases, 3072 each RESOLVED/SOURCE_UNBOUND/SNAPSHOT_MISMATCH/RECORD_UNBOUND. 3072 reads/196608 vectors; zero 1296 times, one 1776 times; failures/mutations zero.
- C156 PASS, 412 tests: 82944 original requests x four branches = 331776 views. Each status has 82944 occurrences; resolved zero 34992/one 47952. Actual WorkingState and signed control channels; no stale-payload leakage, state mutation, clock advancement or acquisition debit. 82944 exact64 reads, 5308416 vectors, 331776 internal-step debits.
- **C157 ACCEPTED PASS**, 440/440 tests; execution commit `40f63b46c67d5c71a8e8bc75ac6ba07ddd3ef05a`. Three new C113-recipe reference routers, seeds 20261741..20261743, 900 CPU updates each. 1990656 recorded-view decisions, 576 evaluation batches; errors/nonpositive margins/input mutations/weight mutations all zero. Minimum logit margin 5.344475269317627; 3/3 routers pass. ANSWER 497664, RETRIEVE 746496, STOP 746496; correct ANSWER with zero 209952/one 287712. All reported protected/tree/HEAD checks pass.

C157 establishes recorded working/context input -> learned action selection, not live action execution or generated answers. Only **six distinct model input patterns** occur; the large count is artifact/interface coverage, not independent reasoning questions. Present irrelevant evidence can still induce ANSWER. Source semantics are bookkeeping, not newly measured accuracy. Exact64 costs and total diagnostic timings are not production performance claims.

## Accepted artifact chain

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

Current verdict/preregistration: **`docs/experiment-ledger-addendum-c157-c158.md`**.
Earlier plans/verdicts remain in chained addenda, including `experiment-ledger-addendum-c156-c157.md`, `experiment-ledger-addendum-c155-c156.md` and `experiment-ledger-addendum-c154-pcalm-review.md`. Formal verdicts use user logs and inspected source, not independently rerun full artifacts. Subsequent local runs verify the runner-printed report hashes against the actual files.

## Active C158 — Bounded Controller-driven reference recovery

`C158-v5e-bounded-controller-reference-recovery`; stage `V5-E-BOUNDED-CONTROLLER-REFERENCE-RECOVERY`.
**ACTIVE, awaiting user CPU execution. No C158 result claimed.**

Question: can a frozen Controller proposal execute one authorized retrieval, admit/project its result and reobserve the resulting live state, reaching the correct terminal action without stale values or unbounded retries?

```text
live C156 reobservation -> frozen C157 Controller
-> runtime permission/acquisition-budget gate
-> real C153 fetch/admission -> C154 EvidenceRef projection
-> live C156 reobservation -> same Controller -> ANSWER action / STOP
```

Reuse all three C157 routers/checkpoints without training. Replay all 1990656 C157 decisions first (full source order, exact actions/labels, logits/margins atol 1e-5). Hash every pinned input and reaggregate C154/C153 state lineage via C155. No recreating or relocating missing inputs.

New coverage: **128 snapshot/key bindings**, 64 keys in each original layout. Reaggregate all source streams, then choose one identity-only representative request per binding, not by correctness/value. Save plan before evaluation. This is record-level integration, not all 82944 original language requests or a new relevance score.

Five scenarios per binding/router: WARM_PRESENT, COLD_RECOVER, COLD_MISSING_DELIVERY, COLD_PERMISSION_DENIED, COLD_BUDGET_EXHAUSTED. Cold removes only the selected ref in a diagnostic branch; other 63 refs remain. All start with stale working presence; the actual readback refreshes it. Model-visible RETRIEVE starts true, deliberately stale for denial/budget exhaustion. Runtime authority blocks execution, then updates visible eligibility. After the first RETRIEVE proposal the attempt is spent; maximum one acquisition and three decisions. Model actions are never overridden. A pathological repeated RETRIEVE is bounded but still FAIL, not successful learned termination.

Missing delivery withholds a real successful fetch before admission; it must publish nothing and end with no usable value. Valid admission and matching projection are adopted together as immutable in-process state. New reference restoration stays within the already pinned evidence epoch/revision 1, not a new external-world observation. No generated answer, changing snapshots, durable publication, crash recovery, concurrent transactions or production deployment.

Expected: **1920 live episodes; 3456 live decisions/internal debits; 768 acquisitions; 384 restored refs; 1536 exact64 calls/98304 vectors**. Terminal ANSWER 768/STOP 1152; resolved zero 324/one 444. Exact readback costs include the second read after successful recovery. Model input patterns are still the existing six; the advance is sequential integration, not new learned reasoning.

PASS requires every episode's action/margin/status/value/ref/clock/budget/authority/cost invariants and preservation checks. Finite behavioral violations are valid FAILs, not retries. Bad sources/checkpoints/replay/numerics/execution are INVALID. Gate E remains NOT PASSED. Judge C158 before C159; no C159 registered.

Files: `gate_e_c158_live_recovery.py`, `gate_e_c158_cli.py`, `tests_lm/test_v05_c158_live_recovery.py`, `tools/run_c158.ps1`.
Reviewer **35/35 new CPU helper tests and compilation passed** using exact production state/controller copies. Controlled callbacks isolate the new orchestration; no real C157 checkpoint or full prior artifact integration was available. Full **475 tests**, formal replay/live integration and PowerShell remain unexecuted by the reviewer.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented research candidates. PC-ALM report on main: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` at `903e31f1e509c92877206741672918e7bacc701b`. Review conditions (finite-iteration timing, same-state gradients, immutable evidence, full cost accounting and quantified gates) remain in `experiment-ledger-addendum-c154-pcalm-review.md`. No report is merged or rewritten here.

Shared-Basis partition, Multi-Axis, local credit, KV/context work, ranking, retrieval, request admission, EvidenceState, payload readback, working reobservation, Controller and ANSWER are separate claims. Diagnostic epoch/generation-to-time/revision mapping is not the final production clock design. Cross-source namespaces, revisions/retractions, durable publication and fault recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
