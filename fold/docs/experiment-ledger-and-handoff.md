# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; user runs `.venv-py31315\Scripts\python.exe`.
- Protected C37: `runs/chatgpt-last-result.json`; SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture: `runs/fixtures/v05-c-composition-20260921.pt`; SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry same C number; valid negatives close their number after interpretation.
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

Runtime hardening through C132 covers receipt binding/scope/authority, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent ownership and fencing. C133-C135 moved RETRIEVE onto persisted corpus/StructuralIndex. C136 learned fixed-address query formation; C137 moved to shared content addressing and dynamic candidate growth.

Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Accepted chain through C144

- C137: ACCEPTED PASS, lexical content-addressing / 8→12 corpus-growth scope.
- C138: ACCEPTED VALID NEGATIVE, compositional alias fixture with hashed front end.
- C139: ACCEPTED VALID NEGATIVE, collision-free diagnostic; finite solution possible but not all-seed robust.
- C140: ACCEPTED VALID NEGATIVE, 12-seed robustness replication; 8/12 fully correct.
- C141: ACCEPTED PASS, oracle evaluation-only color substitution; all C140 errors rescued, no new errors.
- C142: ACCEPTED PASS, training-only supervised color alignment on original 12-candidate fixture; 12/12 COLOR_AUX heads pass, BASELINE 5/12.
- C143: ACCEPTED VALID NEGATIVE, frozen exhaustive 64-candidate ranking; COLOR_AUX 19211/20736 = 0.926456, 1,525 residual errors; runtime path not exercised.
- C144: **ACCEPTED PASS, descriptive attribution scope only**. Focused regression 162/162; analysis-only; C143 summary/manifest preserved; attribution complete.

C144 COLOR_AUX residual masks:

```text
MATERIAL                  679
SHAPE                     305
COLOR                     152
SHAPE+MATERIAL            168
COLOR+MATERIAL            147
COLOR+SHAPE                36
COLOR+SHAPE+MATERIAL       38
```

Material appears in 1,032 / 1,525 residual errors (67.67%); shape in 547 (35.87%); color in 373 (24.46%). Of 108 BASELINE→COLOR_AUX regressions, material is involved in 77 (71.30%), with MATERIAL-only 65 and SHAPE-only 32. C144 is descriptive, not causal.

Detailed C144 verdict and C145 preregistration: `docs/experiment-ledger-addendum-c144-c145.md`.

## Active experiment — C145

Experiment: `C145-v5e-material-alignment-intervention`.
Stage: `V5-E-MATERIAL-ALIGNMENT-INTERVENTION`.
Status: ACTIVE, awaiting user CUDA execution.

Question: with color alignment already present, does adding only material alias→canonical alignment remove material-involved residual errors without paired regressions?

```text
fresh seeds = 20261641..20261652
2 paired heads / seed, identical initialization
COLOR_AUX = main CE + 1.0 * color CE
COLOR_MATERIAL_AUX = main CE + 1.0 * color CE + 1.0 * material CE
same 49-d features / hidden 64 / residual 1.0
same AdamW lr 0.002 / 600 steps / logit scale 12.0
same 24 main training queries / 8 main candidates
material auxiliary: 12 training aliases vs 4 canonical material values
original raw evaluation text; no inference alias map/oracle
original 12-candidate safety ranking + full C143 64-candidate/1,728-query ranking
20,736 full-catalog rankings per arm
```

Changed variable: material-alignment auxiliary term only. Shape supervision is intentionally absent.

PASS requires: valid controls; COLOR_AUX control has material-involved errors; COLOR_MATERIAL_AUX has zero material-involved full-catalog errors; paired new errors = 0; treatment preserves all original-12 rankings with positive margins across all 12 seeds.

FAIL is a valid negative if any preregistered condition fails; report partial material-error reduction and regressions without tuning weight/steps or adding shape loss. INVALID covers prerequisite/hash/OOV/init/numeric/evaluation-mutation/execution failures.

C145 full-factorial portion is ranking-only; no expanded persisted retrieval/evidence/ANSWER. Explicit factor supervision is not unsupervised semantic discovery. Gate E remains NOT PASSED. No C146 before formal C145 judgment.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C145 factor fixtures are synthetic development tasks, not scalable production tokenizer or open-domain semantic evidence.
- Oracle substitution, explicit supervision, and automatically discovered semantic factors are distinct claims.
