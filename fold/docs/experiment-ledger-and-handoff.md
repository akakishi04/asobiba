# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER. User execution uses `.venv-py31315\Scripts\python.exe`.
- Protected C37: `runs/chatgpt-last-result.json`; SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture: `runs/fixtures/v05-c-composition-20260921.pt`; SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number. Valid negatives close their C number and may advance after interpretation.
- Conversation/execution/handoff responses follow `docs/experiment-conversation-handoff-protocol.md`.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E current architecture

```text
learned Control Lane
-> runtime-authoritative availability / permission
-> learned acquisition request
-> real acquisition component
-> provenance / outcome validation
-> evidence commit only on validated evidence
-> reobserve
-> answer / further acquisition / unresolved
```

Runtime fault-tolerance hardening through C132 covers receipt binding/authority/scope, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent recovery ownership, lease fencing/renewal, SQLite storage fencing, and independent-OS-process fencing. C133-C135 moved RETRIEVE onto a real persisted corpus/StructuralIndex. C136 learned fixed-address query formation; C137 replaced fixed output classes with shared content addressing and dynamic candidate-set growth.

Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Accepted chain through C143

- C137: ACCEPTED PASS, lexical content-addressing / 8→12 corpus-growth scope.
- C138: ACCEPTED VALID NEGATIVE, compositional alias fixture with hashed front-end.
- C139: ACCEPTED VALID NEGATIVE, collision-free diagnostic; solution possible but not all-seed robust.
- C140: ACCEPTED VALID NEGATIVE, 12-seed replication; 8/12 fully correct.
- C141: ACCEPTED PASS, oracle evaluation-only color substitution scope; all four C140 errors rescued, no new errors.
- C142: ACCEPTED PASS, training-only supervised color alignment on the registered 12-candidate fixture; 12/12 COLOR_AUX heads passed original queries, BASELINE 5/12; no inference oracle or production change.
- C143: **ACCEPTED VALID NEGATIVE**, exhaustive frozen ranking scope. Focused regression 152/152; 24 C142 checkpoints reconstructed; original-12 replay match 1.0; no retraining; protected/input/checkpoint controls valid. Expanded catalog: 64 descriptors, 1,728 alias queries/model, 41,472 total rankings. Runtime path not exercised.

C143 aggregate results:

```text
BASELINE ALL: 17178 / 20736 = 0.8284143519
COLOR_AUX ALL: 19211 / 20736 = 0.9264564043

COLOR_AUX TRAIN_COMBINATION:          2592 / 2592  = 1.0
COLOR_AUX PRIOR_HELDOUT_COMBINATION:  945 / 1296   = 0.7291666667
COLOR_AUX NEW_COMBINATION:            15674 / 16848 = 0.9303181387
COLOR_AUX ORIGINAL_VALIDATION_IN_64:  128 / 144    = 0.8888888889

COLOR_AUX residual errors = 1525
BASELINE errors = 3558
paired rescued = 2141
paired regressions = 108
both wrong = 1417
full_model_pass_count = 0 for both arms
```

C143 therefore shows that C142's supervised alignment materially improves broader in-vocabulary factor/alias ranking but is not sufficient for exhaustive 64-candidate generalization. The scoped C142 PASS remains valid. C143 does not establish an end-to-end runtime failure because persisted retrieval/evidence/ANSWER was not run for the generated 64-candidate catalog.

Detailed C143 verdict and C144 registration: `docs/experiment-ledger-addendum-c143-c144.md`.

## Active experiment — C144

Experiment: `C144-v5e-factor-mismatch-attribution`.
Stage: `V5-E-FACTOR-MISMATCH-ATTRIBUTION`.
Status: ACTIVE, awaiting user local analysis.

Question: which canonical factor-difference patterns dominate C143 residual errors and the BASELINE→COLOR_AUX rescued/regressed decisions?

C144 performs **analysis only** over the accepted C143 `summary.json` + `evaluation-manifest.json`:

```text
model loading = False
additional scoring = False
additional training steps = 0
runtime path = False
```

It first recomputes the accepted C143 aggregate counts from full records. Every wrong selection is then classified as COLOR / SHAPE / MATERIAL / pairwise mismatch / all-three mismatch. It also reports factor-space distance, bucket-specific mask counts, expected-value and alias-token error rates, and separate mismatch distributions for 2141 rescues and 108 regressions.

C144 PASS means the descriptive attribution completed with exact prerequisite/accounting consistency; it is not a model-capability pass. The output distribution determines C145. Do not add new factor losses or tune C142 until C144 is judged.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C144 vocabulary/factor fixtures are diagnostics and synthetic development tasks, not scalable production tokenizer or open-domain semantic evidence.
- C141 oracle substitution, C142 explicit training supervision, and automatically discovered semantic factors are different claims.
- Gate E remains NOT PASSED.
