# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and the current addendum before work. Judge -> ledger/handoff -> next C. One question per C; invalid executions retry the same number; valid negatives remain accepted evidence.
- Latest accepted execution: **C165** at `4dfc1634ea4a18f70390807011a83f60654e1b00`. Verdict first recorded in `0a4b0d472501286f4e20a0c831e9e71712355750`; acceptance-only handoff commit `76b91ebe07a7e710f0be239e54b9105161c3e84e` precedes C166 registration. The runner must use the final C166 registration HEAD, not the C165 execution HEAD.

## Gate status / architecture boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.

```text
learned Control Lane -> authoritative permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

Production retrieval head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Persisted adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains a separate design, not implemented by these diagnostics.

## Accepted evidence through C165

C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity. C141 PASS oracle localization; C142 PASS small supervised alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive attribution. C145-C148 include accepted negative interventions; C149 PASS arithmetic attribution. C150 PASS original synthetic split. Earlier detailed claims remain in the chained addenda.

- **C151 PASS**,298 tests: four replacement splits x three paired initializations; WITHIN_FACTOR20,727/20,736 and GLOBAL_CONCEPT20,736/20,736. Nine control errors in S2/20261726; synthetic ranker tuning closed, no independent task/language generalization.
- **C152 PASS**,322 tests:24 frozen heads/two layouts;82,944 exact64 reads with selected identity/provenance/payload/cost preserved.
- **C153 PASS**,346 tests:82,944 reads,580,608 deliveries,414,720 invalid rejections,82,944 valid admissions and duplicate rejections each; immutable diagnostic inbox, not durability.
- **C154 PASS**,363 tests:3,072 ADDED/79,872 ALREADY_PRESENT from82,944 entries,3,072 conflicts rejected;48 states x64 refs. Classification caveat: `experiment-ledger-addendum-c154-pcalm-review.md`.
- **C155 PASS**,388 tests:12,288 resolver cases/four statuses;3,072 reads/196,608 vectors;zero/one1,296/1,776.
- **C156 PASS**,412 tests:82,944 requests x4 conditions=331,776 views; zero/unresolved separated, no stale payload or external-clock advance.
- **C157 PASS**,440 tests:three Controllers, seeds20261741..20261743,900 updates each;1,990,656 recorded-input decisions. Minimum margin5.344475269317627.
- **C158 PASS**,475 tests:preselected-record warm/recover/missing/denied/exhausted live cases;1,920 episodes/3,456 decisions,768 acquisitions,384 restorations,1,536 calls/98,304 vectors;ANSWER768/STOP1,152. Not raw-query selection.
- **C159 PASS**,508 tests:stored-terminal emitter;1,920 terminals ->6,528 emissions,ANSWERED768/UNRESOLVED1,152,4,608 controls rejected.
- **C160 ACCEPTED VALID NEGATIVE**,546 tests,execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`:82,944 complete live query cycles with expected retrieval/accounting but ANSWERED0/failed82,944. Never retroactively relabel.
- **C161 ACCEPTED PASS**,558 tests,execution `97e26b5dfa71ac7998138050942bbfd107f3c46e`:all82,944 stored cycle assessments pass; single post-cycle rejection MALFORMED_EVIDENCE.
- **C162 ACCEPTED PASS**,588 tests,execution `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`:82,944 digest-verified offline tuple/list pairs; native rejection/list-bound output,768 guards pass. Reconstruction, not original heap capture.
- **C163 ACCEPTED PASS**,614 tests,execution `d3cecf1c1221d2119a2e6ab172c69770bde46788`:82,944 live raw-query cycles yield bound ANSWERED after observations-only normalization; native controls reject.165,888 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors;768 guards/494 input checks pass.
- **C164 ACCEPTED PASS**,638 tests,execution `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`:82,944 rankings x2 fresh continuations=165,888 branch episodes. Normal ANSWERED82,944 / missing UNRESOLVED-MISSING_DELIVERY82,944;331,776 decisions,165,888 actual acquisitions,82,944 publications,248,832 calls/15,925,248 vectors. Missing branch never publishes/rereads;768 guards/545 input checks pass.
- **C165 ACCEPTED PASS**,**665/665 tests**,execution `4dfc1634ea4a18f70390807011a83f60654e1b00`:82,944 rankings x allowed/denied fresh continuations=165,888 branch episodes,zero failures.331,776 decisions,82,944 acquisitions/restorations,165,888 adapter calls/10,616,832 vectors. Allowed ANSWERED82,944; denied UNRESOLVED/PERMISSION_DENIED82,944 with zero acquisition/adapter call/publication/readback and acquisition allowance preserved at1. Raw RETRIEVE proposals not overridden; all denied first authorities PERMISSION_DENIED.768 guards,596 inputs,historical blobs,tracked tree/HEAD preserved;zero weight/output mutation or serialization failure.

## Interpretation boundary

C165 supports runtime permission enforcement in the fixed synthetic raw-query -> selection -> bounded cycle -> typed result path. C164 separately supports post-fetch transport loss handling. Normal branches retain20,736 bound outputs per arm/layout, semantic_correct WITHIN_FACTOR20,727 / GLOBAL_CONCEPT20,736, values zero34,992/one47,952. Known nine errors x2 layouts remain18 instances, not18 new error types. Denied/missing semantic_correct is null; unresolved is not bit0 or proof of nonexistence.

Runtime enforces permission after the model proposal; unavailability/reobservation then causes learned STOP. This is not general policy understanding. Zero denied adapter calls does not mean zero ranking or zero prerequisite file reads. No OS/security isolation/confidential-catalog guarantee is measured.

C160 stays accepted negative. EvidenceState remains tuple-backed; C163's output bridge/C159 emitter remain unchanged. No target/checkpoint/threshold changes repair known semantic errors. No accepted raw-query budget-exhausted/warm path, initially empty world, dynamic epochs, relevance abstention, generated answers, durability or production rollout is established yet. Repeated fixed-fixture episodes are not independent task generalization; diagnostic timing/allocator data is not final FOLD performance. **Gate E stays NOT PASSED.**

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
C151-C156 paths/identities and earlier evidence are retained in chained addenda, pinned manifests and the C164/C165 acceptance-only handoff history. C151 SHA `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`; manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`; split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c165-c166.md`**.
Current preregistration: **`docs/experiment-ledger-addendum-c166-preregistration.md`**.
C165 reviewer checked uploaded console/source/preregistration consistency; records omitted means no independent full report hash reconstruction or user-side raw-trace/model replay is claimed.

## Active C166 — Live query acquisition-budget exhaustion

`C166-v5e-live-query-budget-exhausted`; `V5-E-LIVE-QUERY-BUDGET-EXHAUSTED`.
**ACTIVE / NOT YET JUDGED. No C167 registered.**

One question: with permission=True and identity delivery, does initial acquisition allowance0 block actual acquisition after learned RETRIEVE and lead to typed payload-free UNRESOLVED/BUDGET_EXHAUSTED, while allowance1 retains normal ANSWERED?

Change only initial `BudgetState.acquisitions_remaining`1->0. Local diagnostic BudgetState factory verifies C160's original(3,1) constructor request, returns an actual core budget(3,1)/(3,0), and leaves all other API objects/cycle arguments unchanged. The actual effective initial budget is returned and evaluated, avoiding an allowance-one evaluation proxy. Internal budget3, permissionTrue, source clocks/state, normal delivery,24 rankers,3 Controllers,query/layout/router schedules and C163/C159 output path remain fixed. No training/fresh seed, no historical or production changes.

82,944 fresh rankings/5,308,416 candidate scores, each with two independent cold continuations (allowance1 first). Expected165,888 branch episodes,331,776 decisions/internal debits,82,944 actual acquisitions/restorations,165,888 adapter calls/10,616,832 vectors. Each Controller27,648 episodes per condition. Actions RETRIEVE165,888/ANSWER82,944/STOP82,944. Allowance1:82,944 bound ANSWERED,unchanged per-layout semantic/value totals. Allowance0:82,944 UNRESOLVED/BUDGET_EXHAUSTED,zero fetch/adapter/debit/admission/publication/readback,initial/final acquisition0,final internal1/internal step9,stale payload cleared. Semantic score null. No invented zero or nonexistence.

Use unchanged C163 emitter:165,888 native controls+165,888 adapted candidates+768 guards; native MALFORMED_EVIDENCE retained. C1596,528 and C15141,472+288 replays separate. Pin full C165 parent and all traces/plan/controls/inputs; historical core/C158-C165 blobs fixed. Save48 gzip traces x3456rows plus actual initial budgets, compact state digests, all action/authority/output/budget assessments and guards. New UUID run; rehash code/inputs/tree/HEAD in Python and runner.

PASS requires complete coverage, original normal-success gate, exact exhausted behavior/output/budget,positive finite margins,independent cost meters,native controls,all guards/protections and zero measured defects. Valid finite defects are FAIL/ACCEPTED VALID NEGATIVE; no threshold/checkpoint/case tuning for PASS. Invalid setup/hash/schema/replay/numeric/incomplete execution or outer protection failure retries C166 unchanged. Zero adapter cost does not remove shared rankings,source IO or internal decisions. Gate E remains NOT PASSED.

Files: `fold_lm/v05_benchmarks/gate_e_c166_live_budget_exhausted.py`, `tests_lm/test_v05_c166_live_budget_exhausted.py`, `tools/run_c166.ps1`.
Focused regression **695 expected=665+30**. Reviewer compiled both Python files and passed23 dependency-light tests via inspected excerpts/test doubles; seven actual-cycle/emitter integration methods,complete695/realCUDA-CPU/WindowsPowerShell were not executed here. No formal C166 result yet. Stop after execution for judgment/ledger update before C167.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate,unimplemented candidates. Shared-Basis partition,Multi-Axis,local credit,KV/context,ranking,retrieval,admission,EvidenceState,readback,reobservation,Controller,typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not production clocks. Cross-source namespaces,revisions/retractions,durable publication/recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference,not the V5-E store.
