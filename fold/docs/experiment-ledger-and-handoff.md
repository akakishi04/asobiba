# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in chained experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; user runs `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`, SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`, SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same number; accepted negatives are retained.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, and this handoff. Preserve claim/non-claim, guards, progress and log collection.

## Gate status and scope

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

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

Hardening through C132 covers receipt binding/scope/authority, commit-context checks, replay suppression, atomic claim, recovery, ownership and fencing. C133-C135 moved RETRIEVE onto persisted corpus/StructuralIndex. C136 learned fixed-address query formation; C137 introduced shared content addressing/dynamic candidates.
Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` is separate design, not implemented by ranking diagnostics.

## Accepted chain through C148

- C137 PASS, lexical addressing / 8-to-12 corpus growth.
- C138 VALID NEGATIVE, hashed compositional alias fixture.
- C139 VALID NEGATIVE, collision-free but seed-sensitive. C138/C139 also differ in dimensions/parameter shapes and seeds; no isolated collision-causality estimate.
- C140 VALID NEGATIVE, twelve-seed replication; 8/12 completely correct.
- C141 PASS, oracle evaluation-only color substitution; not learned raw-query improvement.
- C142 PASS, supervised train-only color alignment on original 12-candidate fixture.
- C143 VALID NEGATIVE, expanded frozen ranking; 1,525 COLOR_AUX errors; no runtime test.
- C144 PASS, descriptive factor-mismatch attribution only.
- C145 VALID NEGATIVE, paired material supervision; errors 1,464->346, 1,153 rescues/35 new errors. See `docs/experiment-ledger-addendum-c145-c146.md`.
- C146 VALID NEGATIVE, final named three-factor supervised reference; errors 476->11, 8/12 full-model passes. Named auxiliary-loss ladder closed. See `docs/experiment-ledger-addendum-c146-c147.md`.
- C147 VALID NEGATIVE, frozen inference composition change; errors 11->4, 10 rescues/3 new errors, 11/12 full-model passes. Different normalization/weighting as well as nonlinear mixing order; no unique causality. See `docs/experiment-ledger-addendum-c147-c148.md`.
- **C148 ACCEPTED VALID NEGATIVE**, user log at `dd0387b9cbee8ba38142b4ad7594c277d02b8c9d`; focused regression **236/236**, all reported init/reference/OOV/weight/protected/HEAD/tree checks valid. Same encode-then-pool evaluator, different main training composition. No production or runtime test.

```text
C148 fresh paired seeds 20261681..20261692
POOLED_TRAIN:   20,725/20,736 correct, 11 errors, 10/12 perfect models
COMPOSED_TRAIN: 20,724/20,736 correct, 12 errors, 10/12 perfect models
Paired: 0 rescued, 1 new error, 20,724 both correct, 11 both wrong
Masks: control COLOR 5 / SHAPE 6; treatment COLOR 6 / SHAPE 6; no MATERIAL errors
Failure seeds: 20261683 (5->6 errors), 20261692 (6->6 errors)
Original12 strict passes: 12/12 both arms
Original validation in 64: 144/144 both arms
Worst margin: control -0.0279458463; treatment -0.0441289246
```

C148 did not demonstrate an accuracy benefit; do not adopt train consistency as the proven fix. One new error does not establish general inferiority or equivalence. Exact texts and source singleton fits are absent from its console report. C147/C148 use different seed sets, so their total residuals are not paired evidence. Earlier scoped results remain unchanged.

Source run: `runs/c148-v5e-train-consistent-composition-fe85fcf3544e4965ace63f90cca84223/`.
**C148 report SHA256:** `4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e`.
Manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Full C148 judgment, review and C149 registration: **`docs/experiment-ledger-addendum-c148-c149.md`**.

## Review decision

Named attribute-loss additions remain closed at C146; the one train-consistency comparison closes negative at C148. No coefficient/step/width sweep, no discarding failure seeds, no gate lowering, and no new scorer is authorized. Both representations remain research references, not promoted production fixes. Before another learning intervention, measure the existing score's components. C149 is read-only accounting, not another attempt to erase the remaining twelve cases.

## Active experiment — C149

`C149-v5e-frozen-margin-accounting`, stage `V5-E-FROZEN-MARGIN-ACCOUNTING`.
Status **ACTIVE, awaiting user checkpoint audit**; no result claimed.

Question: how do same-factor, cross-factor and candidate-normalization contributions combine into C148's actual correct-versus-best-rival margins?

```text
Source: all 24 C148 checkpoints, both arms/all 12 source seeds
fresh seeds=0; training=0; scorer change=False
same ENCODE_THEN_POOL encoder and dot-product ranking
64 candidates / 1,728 queries / same manifest
41,472 full-case replays and decompositions + 288 original12 replays
known factor positions used AFTER ranking for accounting only
```

C148's exact report hash is required. Reaggregate source results/pairs, validate model bytes/config/vocabulary/composition metadata/fingerprints, replay the original CUDA scores. All discrete predictions/rivals must agree; score tolerance `1e-5`. Accumulate the unchanged float32 unit embeddings in float64 for decomposition; do not re-encode the model in float64. Preserve all sources, weights, C37 and fixture.

The symmetric exact identity is specified in the addendum: `margin = same_factor + cross_factor + candidate_norm`. It is one bookkeeping convention, not unique causal attribution. A factor's singleton 4-class correctness is not the same measurement as its contribution to a 64-candidate ranking. No term is deleted and no alternative score or predictions are used. Attribute labels do not enter model inference.

Save all cases' contributions and the 23 error observations' text/matrices/norms (11+12 paired errors, not 23 independent problems). Report source singleton-fit diagnostics without inventing their values. Adverse component counts can overlap.

**PASS is descriptive accounting only:** all original rankings replay, all margins reconstruct, all input/protection checks pass, and source residual counts remain 11/12. **INVALID:** any replay/numeric/coverage/identity/execution discrepancy, then retry C149. No model-performance FAIL gate applies to an unchanged model audit. No Gate E promotion.

After C149, review the measured geometry before a separately registered learning/representation/generalization decision; no automatic removal of cross terms or normalization. C150 is not registered.

Implementation: `gate_e_c149_margin_accounting.py`, `gate_e_c149_cli.py`, `tests_lm/test_v05_c149_margin_accounting.py`, `tools/run_c149.ps1`.
Reviewer: **19/19 new CPU helper tests**, synthetic vectors/toy checkpoints; Python compilation. Full **255-test** suite, actual C148-checkpoint/prerequisite integration, CUDA and PowerShell are not reviewer-executed.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E persistent store.
- These are repeatedly inspected synthetic development tasks, not sealed open-domain benchmarks.
- Oracle replacement, explicit supervision, hand-specified composition and discovered factors are distinct.
- Ranking-only results do not establish retrieval/provenance/commit/ANSWER correctness or general intelligence.
