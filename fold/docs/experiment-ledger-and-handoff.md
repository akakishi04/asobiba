# FOLD Experiment Ledger and Handoff

> Current authoritative state. Read this with the protocol, current verdict and current design review.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this file, `docs/experiment-ledger-addendum-c167-c168.md`, and **`docs/gate-e-acceptance-gap-audit-after-c167.md`**.
- Judge -> ledger/handoff -> next C; one scientific question per C. Preserve valid negatives; invalid executions retry the same registered number. Do not tune checkpoints/thresholds/cases to relabel past results.
- Latest accepted execution **C167** at `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`; acceptance commit **`5b0f37028f82e987e399da60bf40c17e69de5fcf`**. Documentation HEAD changes do not require rerunning C167.

## Formal state / architecture boundary

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**.
**C167 ACCEPTED PASS. C168 NOT REGISTERED. No new experiment is ACTIVE.**
Priority remains operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> runtime permission/budget -> actual acquisition
-> provenance/outcome validation -> evidence commit -> reobserve -> typed answer/unresolved
```

Retrieval head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`;
persisted adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains separate design, not implemented by these diagnostics.

## Accepted evidence

The full through-C166 summary/earlier source identities remain in the handoff at `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`; the acceptance-only handoff at `5b0f37028f82e987e399da60bf40c17e69de5fcf` retains the detailed through-C167 summary. Their chained addenda remain authoritative history, not superseded by this compact current index.

- C137 PASS; C138-C140 VALID NEGATIVE; C141-C142 PASS; C143 VALID NEGATIVE; C144 PASS; C145-C148 include accepted negative interventions; C149-C150 PASS within their registered scopes.
- C151 PASS:24 paired heads/four splits; WITHIN_FACTOR20,727/20,736; GLOBAL_CONCEPT20,736/20,736. Nine control errors in S2/20261726; synthetic ranker tuning closed.
- C152-C157 PASS: persisted retrieval -> admission -> EvidenceState projection -> paid payload read -> request reobservation -> frozen learned Controller; each claim remains separate. C154 classification caveat: `experiment-ledger-addendum-c154-pcalm-review.md`.
- C158 PASS: preselected-record warm/recover/missing/denied/exhausted live cycle; not raw query. C159 PASS: stored-terminal emitter/guards; not live query composition.
- **C160 ACCEPTED VALID NEGATIVE**,546 tests:82,944 completed live cycles,ANSWERED0. Never relabel. C161 PASS localized single terminal rejection. C162 PASS offline tuple/list differential,not original heap capture.
- **C163 PASS**,614 tests:82,944 raw-query bound ANSWERED after observations-only normalization; original native controls reject.165,888 decisions,82,944 acquisitions/restorations,165,888 calls/10,616,832 vectors;768 guards/494 input checks.
- **C164 PASS**,638 tests:82,944 shared rankings/two continuations;normal ANSWERED82,944,missing UNRESOLVED-MISSING_DELIVERY82,944. Missing fetch occurs but no publication/readback;768 guards/545 input checks.
- **C165 PASS**,665 tests:allowed/permission-denied165,888 episodes;denied no acquisition/read/debit/publication,budget1->1,UNRESOLVED/PERMISSION_DENIED82,944;768 guards/596 input checks.
- **C166 PASS**,695 tests:allowance1/0 cold continuations165,888 episodes;exhausted no fetch/debit/publication/readback,permissionTrue both,UNRESOLVED/BUDGET_EXHAUSTED82,944;768 guards/647 input checks.
- **C167 ACCEPTED PASS**,**725/725 tests**:82,944 fresh ranking prefixes x cold/warm=165,888 episodes,failed0,matched output pairs82,944,ANSWERED165,888.248,832 decisions,82,944 acquisitions/restorations,248,832 exact64 reads/15,925,248 vectors. Warm82,944 episodes each:one paid read,one ANSWER,no acquisition/admission/publication,unchanged evidence,acquisition allowance1->1,final budget(2,1). Cold final budget(1,0). Margins cold6.142457485198975/warm9.29835307598114.768 guards/698 declared input-path checks and output-artifact/code/tree/HEAD checks pass;mutations/serialization failures0.

## Interpretation boundary

All answered conditions/layouts retain20,736 bound outputs per arm;semantic_correct WITHIN_FACTOR20,727/GLOBAL_CONCEPT20,736. C167 known-error instances36=9 x2 layouts x2 answered conditions,not36 failure types. Per condition values0=34,992/1=47,952. Unresolved is not bit0/nonexistence;unresolved semantic_correct=null.

C167 proves no redundant acquisition for an already-bound selected reference on the pinned task. C160 helper fixes dependency channel1=1; C156 reobservation updates presence/value. Thus this path stipulates requiredness rather than inferring missing-information necessity from task content. See the new design review for inspected code and limits; this is not a C167 defect or a universal claim about earlier experiments.

Runtime enforces permission/budget after proposal. Zero denied/exhausted adapter calls excludes shared ranking/prerequisite IO/internal decisions. Warm still pays exact64 dereference. No numerical-budget comprehension,OS isolation,zero-IO answer cache,language-session reuse or learned semantic abstention is established by these contrasts.

C160 stays negative;EvidenceState tuple backing and existing C163 bridge/C159 emitter unchanged. No checkpoint/threshold/target repair. No initially empty-world,dynamic-epoch,generated-answer,durability or production-rollout result. Repeated fixtures do not establish independent task generalization. Diagnostic timing/allocator peaks are not full-model production performance.

**Gate E's remaining experiment count is not fixed.** Comparative hallucination,quality,unnecessary-question and mixed-suite coverage claims need explicit baselines/denominators/numerical rules before deciding evaluation. Do not call Gate E passed merely because local experiments pass; do not add Vision/general language mastery/durable memory as implicit new Gate E requirements.

## Accepted artifact chain

**C167:** `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`.
SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.
Plan `24afcd65e73a7ff2c2d81accb9987e75a7dba40e5d85d8dc662a1a784ac6c70e`.
Controls `fd8ee32e98443b7ab3ec0bdf9bfd4c4672cb4ae7710bc2318938150e8be534a4`.
Uploaded log `ce0a633df8dfa338046484766b38afa18f985b1e94789710857f97287c45922a`,333,106 bytes.

**C166:** `runs/c166-v5e-live-budget-exhausted-94d4977de28e464aa298c02f1f63bf06/summary.json`,SHA256 `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.
**C165:** `runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`,SHA256 `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
**C164:** `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`,SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`,SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
C151-C162 paths/hashes remain in earlier handoff/addenda. C151 SHA `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`;manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`;split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Reviewer checked uploaded-byte hash and console/source/preregistration consistency. Omitted records mean no independent full-report hash reconstruction or raw-trace/model replay is claimed. New changes are documentation-only; no new runtime tests are claimed.

## Next work — finite acceptance contract and C168 draft

Read **`docs/gate-e-acceptance-gap-audit-after-c167.md`**. It maps all five roadmap criteria to evidence/gaps and proposes a finite final-evaluation contract without inventing numerical thresholds or revising accepted trials.

Proposed C168 question: can current model-visible inputs distinguish answer-critical from irrelevant missing information without an evaluator-supplied dependency label? This is an input-observability preflight,not yet a learned-necessity or full terminal-output trial. The draft describes paired logical examples,input-equivalence conflicts,task-validity controls and PASS/negative/invalid meanings.

**C168 NOT REGISTERED / NO RUNNER.** Exact fixture/schema,counts,code/source pins and tests must be finalized before registration. No new GPU run or C167 rerun is requested now. This design boundary adds no permanent approval requirement; complete the concrete next design under the existing protocol,then preregister before executing. Preserve C167 report and48 traces.

## Independent research tracks

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate unimplemented candidates. Shared-Basis,local credit,KV/context,ranking,retrieval,admission,EvidenceState,readback,reobservation,Controller,typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not production clocks. Cross-source namespaces,revisions/retractions,durable publication/recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference,not the V5-E store.
