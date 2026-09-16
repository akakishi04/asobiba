# FOLD Experiment Ledger and Handoff

> Current authoritative state. Detailed verdicts and preregistrations remain in chained addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this handoff and the current addendum before work. Judge -> record ledger/handoff -> next C. One question per C; invalid execution retries the same number; accepted valid negatives remain recorded.
- Latest accepted execution: **C164** at `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`. Verdict is `docs/experiment-ledger-addendum-c164-c165.md`.

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

## Accepted evidence through C164

- C137 PASS lexical addressing/growth. C138-C140 VALID NEGATIVE composition/seed sensitivity. C141 PASS oracle localization; C142 PASS small supervised alignment. C143 VALID NEGATIVE expanded ranking; C144 PASS descriptive attribution. C145-C148 include accepted negative interventions; C149 PASS arithmetic attribution. C150 PASS original synthetic split.
- **C151 PASS**, 298 tests: four replacement splits x three paired initializations. WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736. Nine WITHIN_FACTOR control errors occur in S2/20261726; synthetic ranker tuning is closed and does not establish independent language/task generalization.
- **C152 PASS**, 322 tests: 24 frozen heads x two layouts, 82,944 real exact64 reads with selected identity/provenance/payload/cost preserved.
- **C153 PASS**, 346 tests: 82,944 reads, 580,608 deliveries, 414,720 malformed/stale rejections, 82,944 valid admissions and duplicate rejections each; diagnostic immutable inbox, not durable publication.
- **C154 PASS**, 363 tests: 82,944 entries -> 3,072 ADDED, 79,872 ALREADY_PRESENT, 3,072 conflicts rejected; 48 EvidenceStates x 64 references.
- **C155 PASS**, 388 tests: 12,288 resolver cases across four status classes; 3,072 reads/196,608 vectors; zero/one 1,296/1,776.
- **C156 PASS**, 412 tests: 82,944 requests x four conditions = 331,776 views; signed presence/payload channels distinguish zero from unresolved; no stale payload or external-clock advance.
- **C157 PASS**, 440 tests: three learned Controllers, seeds 20261741..20261743, 900 CPU updates each; 1,990,656 recorded-input decisions; minimum margin 5.344475269317627.
- **C158 PASS**, 475 tests: selected-record live bounded cycle across warm/recover/missing-delivery/permission-denied/budget-exhausted conditions. 1,920 episodes/3,456 decisions, 768 acquisitions, 384 restorations, 1,536 exact64 calls/98,304 vectors. ANSWER 768 / STOP 1,152. This did not start from raw query selection.
- **C159 PASS**, 508 tests: stored-terminal emitter only, 1,920 terminals -> 6,528 emissions; ANSWERED 768 / UNRESOLVED 1,152; all 4,608 registered controls rejected.
- **C160 ACCEPTED VALID NEGATIVE**, 546 tests, execution `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`: 82,944 complete live query episodes with correct retrieval/controller accounting, but ANSWERED=0 / failed=82,944 because the native tuple-backed EvidenceState was rejected by the historical emitter. Never retroactively relabel this run.
- **C161 ACCEPTED PASS**, 558 tests, execution `97e26b5dfa71ac7998138050942bbfd107f3c46e`: all 82,944 C160 stored cycle assessments pass; all outputs reject at one post-cycle reason `MALFORMED_EVIDENCE`.
- **C162 ACCEPTED PASS**, 588 tests, execution `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`: 82,944 offline tuple/list differential pairs; unchanged emitter rejects tuple and accepts list-only copy; all 768 guards pass; known semantic boundary preserved.
- **C163 ACCEPTED PASS**, 614 tests, execution `d3cecf1c1221d2119a2e6ab172c69770bde46788`: 82,944 fresh raw-query live cycles all produce bound typed ANSWERED after observations-only normalization. On the same cycles all native controls still reject `MALFORMED_EVIDENCE`. 5,308,416 candidate scores, 165,888 Controller decisions, 82,944 acquisitions/restorations, 165,888 exact64 calls/10,616,832 vectors, zero failures/mutations; all 768 guards pass. Values 34,992 zero / 47,952 one. Per layout semantic correctness remains WITHIN_FACTOR 20,727 and GLOBAL_CONCEPT 20,736.
- **C164 ACCEPTED PASS**, 638 tests, execution `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`: 82,944 fresh ranking prefixes, each forked into two independent fresh cold continuations = 165,888 branch episodes with zero failures. Normal delivery produces 82,944 ANSWERED; post-fetch evidence removal produces 82,944 `UNRESOLVED / MISSING_DELIVERY` with no payload. Totals: 331,776 Controller decisions, 165,888 real acquisitions, 82,944 publications, 248,832 exact64 adapter calls / 15,925,248 vectors. Missing-delivery branch has zero publications/readbacks and minimum margin 5.3444743156433105; normal branch retains the C163 semantic boundary and value counts. All 768 guards, 545 consumed-input checks, historical source blobs, tracked tree and execution HEAD pass.

C164 establishes a narrow live transport-failure claim: after a real fetch, removing only the delivered evidence object prevents admission/publication/readback and causes the learned Controller to STOP, returning typed payload-free UNRESOLVED rather than the stale working bit or debug-visible fetched payload. It does **not** establish target absence, semantic relevance abstention, permission/budget-denied raw-query behavior, dynamic epochs, durable commit, learned answer generation, general language/task capability or production performance.

The original C160 valid negative remains accepted. Authoritative EvidenceState remains tuple-backed; C163/C164 use the explicit diagnostic output normalization rather than silently changing the historical emitter. No threshold/checkpoint/case changes repair the known nine WITHIN_FACTOR errors per layout.

## Accepted artifact chain

**C164:** `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`.
SHA256 `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
Plan `09c1cedcf371e320cae3cb1451319ff837a9abe33d1fb78ee7b3acaa74a8f04e`.
Controls `800c27c47f2fad4db97188a96e95f894de22f0e7dcc9de40650fe88841c66bb9`.
Uploaded-log SHA256 `8b1a735e212cb10f2c72bcc3e58a69045f0cdba6a3c1badccc7730aca536b54c`.

**C163:** `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`, SHA256 `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
**C162:** `runs/c162-v5e-evidence-container-a9f04a81882346c99d11c1cafa6f771c/summary.json`, SHA256 `0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac`.
**C161:** `runs/c161-v5e-c160-failure-localization-794f97af76da46c3b7b919f0f278f214/summary.json`, SHA256 `2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38`.
**C160:** `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`, SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
**C159:** `runs/c159-v5e-terminal-result-9e2b2e3e1f9c42bda1f33d7d49fa3cd7/summary.json`, SHA256 `522a6ce4d8792e4e659fc7262928f9d610d814c2ffccff47cc658f6b49e069e6`.
**C158:** `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`, SHA256 `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
**C157:** `runs/c157-v5e-controller-bridge-e68cc92a350145b983d123acad386982/summary.json`, SHA256 `b521eafc61fedaf3b9d2f78fb9c591de654b95cfa6689938c8c042fbc200b934`.
**C156:** SHA256 `b2c43401a6731400de8e18697f82f5e220aeb3f2368737d9dee5847f7ca1f84f`.
**C155:** SHA256 `1ac82ec4c4e60e6c7586058d497096d602a861e191909ca2adfd685f1f2fb4aa`.
**C154:** SHA256 `4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284`.
**C153:** SHA256 `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
**C152:** SHA256 `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
**C151:** SHA256 `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`; manifest `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`; split plan `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Current verdict: **`docs/experiment-ledger-addendum-c164-c165.md`**.
Earlier registrations/verdicts remain in the chained C159-C164 addenda.

## Next experiment

C164 is formally judged and recorded. **C165 is not yet registered in this verdict state.** The next C must remove one remaining V5-E integration constraint without changing accepted historical runs.

## Independent reports / non-claims

Multi-Axis/MA-1 and PC-ALM/FHLC/PA-0..PA-6 remain separate, unimplemented candidates. PC-ALM report on main remains independent. Shared-Basis partition, Multi-Axis, local credit, KV/context, ranking, retrieval, admission, EvidenceState, readback, reobservation, Controller, typed return and learned ANSWER are distinct claims. Diagnostic epoch/generation mappings are not final production clocks. Cross-source namespaces, revisions/retractions, durable publication and recovery remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store.
