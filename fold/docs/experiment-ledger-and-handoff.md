# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; user runs `.venv-py31315\Scripts\python.exe`.
- Protected C37: `runs/chatgpt-last-result.json`; SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture: `runs/fixtures/v05-c-composition-20260921.pt`; SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry same number; valid negatives close after interpretation.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, and this handoff before continuing. Preserve claim/non-claim, guards, progress and log collection.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E architecture and boundaries

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

Hardening through C132 covers receipt binding/scope/authority, commit-context checks, replay suppression, atomic claim, crash recovery, ownership and fencing. C133-C135 moved RETRIEVE onto persisted corpus/StructuralIndex. C136 learned fixed-address query formation; C137 moved to shared content addressing and dynamic candidate growth.

Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains a separate design, not implemented by the current ranking diagnostics.

## Accepted chain through C147

- C137: ACCEPTED PASS, lexical addressing / 8-to-12 corpus growth.
- C138: ACCEPTED VALID NEGATIVE, hashed compositional alias fixture.
- C139: ACCEPTED VALID NEGATIVE, collision-free but not all-seed robust. C138/C139 also differ in dimensions/parameter shapes and seeds; do not isolate collision causality from their comparison.
- C140: ACCEPTED VALID NEGATIVE, twelve-seed replication; 8/12 completely correct.
- C141: ACCEPTED PASS, oracle evaluation-only color substitution, not learned raw-query improvement.
- C142: ACCEPTED PASS, training-only color alignment on the original 12-candidate fixture.
- C143: ACCEPTED VALID NEGATIVE, expanded frozen ranking; 1,525 COLOR_AUX errors in 20,736 cases; no runtime path.
- C144: ACCEPTED PASS, descriptive attribution only; material involved in 1,032/1,525 residuals and 77/108 regressions. Description is not unique causality.
- C145: ACCEPTED VALID NEGATIVE, paired material supervision. Errors 1,464->346, material involvement 798->28, 1,153 rescues and 35 regressions. See `docs/experiment-ledger-addendum-c145-c146.md`.
- C146: ACCEPTED VALID NEGATIVE, final all-three-factor supervised reference; 194/194 regression. Errors 476->11, 469 rescues/4 new errors, 8/12 strict full-model passes. Residual masks COLOR 5, MATERIAL 5, SHAPE 1. See `docs/experiment-ledger-addendum-c146-c147.md`.
- C147: **ACCEPTED VALID NEGATIVE**, frozen composition-order diagnostic, user log at `beae04e34ec9298453953f6535de0328ead6be87`; 212/212 regression; original-full and original12 replay match 1.0; all reported checkpoint/input/immutability/protected/HEAD/tree controls valid. No training, fresh seeds or production/runtime evaluation.

```text
C147 all 12 C146 ALL_FACTOR_AUX checkpoints, source seeds 20261661..20261672
POOL_THEN_ENCODE: 20,725/20,736 correct; 11 errors; 8/12 strict full-model passes
ENCODE_THEN_POOL: 20,732/20,736 correct; 4 errors; 11/12 strict full-model passes
Paired: 10 rescued; 3 new errors; 20,722 both correct; 1 both wrong
Alternative errors: COLOR 4, all seed 20261666, all PRIOR_HELDOUT_COMBINATION
NEW_COMBINATION: 16,839/16,848 -> 16,848/16,848
PRIOR_HELDOUT_COMBINATION: 1,294/1,296 -> 1,292/1,296
Original-12 strict model passes: 12/12 in both modes
Source training singleton fit: COLOR/SHAPE/MATERIAL all 1.0 on all source models
```

Singleton training accuracy is not vector identity or a composition guarantee. C147 changes normalization/equal-unit weighting as well as mixing order. It improves aggregate results without proving a unique mechanism or a non-regressing solution. Exact three newly wrong query strings are not printed in the console; consult full records, do not invent them. C146/C147 negatives and earlier scoped PASS results remain intact.

C147 full report: `runs/c147-v5e-composition-order-3df2d310b2354400a4e2de697ac1c83e/summary.json`.
**C147 report SHA256:** `c26700ba28b1616599617c73f36330dec5901c0f837744cdd86b4ea4580e632a`.
Source C146 report SHA256: `693fadc5b4e76ab253d8395f9197b653ff2d6253435830a9165925948d99622b`.
Manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Detailed verdict and C148 preregistration: **`docs/experiment-ledger-addendum-c147-c148.md`**.

**The named color/material/shape auxiliary-loss ladder is closed at C146.** Do not add named factors, sweep coefficients/steps/width or discard failing models to chase this development fixture's 100%.

## Active experiment — C148

Experiment `C148-v5e-train-consistent-composition`.
Stage `V5-E-TRAIN-CONSISTENT-COMPOSITION`.
Status ACTIVE, awaiting user CUDA execution; no performance result claimed.

Question: with ENCODE_THEN_POOL evaluation held fixed, is using that same composition in main-task training sufficient for exhaustive positive-margin ranking on fresh paired seeds?

```text
fresh seeds = 20261681..20261692; 24 new paired heads, no checkpoint continuation
POOLED_TRAIN:   main training POOL_THEN_ENCODE -> evaluation ENCODE_THEN_POOL
COMPOSED_TRAIN: main training ENCODE_THEN_POOL -> evaluation ENCODE_THEN_POOL
Both: main CE + color CE + material CE + shape CE, all coefficients 1.0
Same 49-d features / hidden 64 / residual 1.0
Same AdamW lr .002 / weight decay 0 / 600 updates / score scale 12
Same 24 main training queries / 8 main candidates
Same 12 aliases vs 4 canonical words per supervised factor, TRAIN_COMBINATION only
Same raw full-query and descriptor texts, no inference dictionary or typed slots
64 candidates / 1,728 queries / 20,736 full rankings per arm
144 original12 rankings per arm; 41,760 total decisions
```

Changed variable is the main-task training computation only. Auxiliary supervision stays fixed, with no extra labels or losses. Source helpers extract training labels without evaluation fields. The gradient-enabled composition is checked against C147's frozen evaluator at absolute tolerance 1e-6. Only input features/indexing are cached during training; learned vectors are recomputed every update. Equal optimizer steps do not mean equal compute. Record per-arm cost with both heads resident; not a production benchmark.

PASS: all COMPOSED_TRAIN full and original12 rankings are correct with strictly positive finite margins across all twelve seeds and all controls valid. Report paired rescue/regression. Control perfection means no demonstrated superiority, not permission to select worse seeds.
FAIL: valid execution but any treatment error/nonpositive margin/original12 failure. Do not change weights/steps/width or evaluation mode after seeing results.
INVALID: prior/hash/reaggregation/manifest/OOV/configuration/initialization/numeric/reference-match/mutation/execution failure; repair and retry C148.

Prerequisite is C147's exact full report SHA, reaggregated through existing C146/C147 auditors. Preserve C147/C37/fixture and accepted generated manifest. Save full/old rankings, metrics, losses, fingerprints, and checkpoints containing training/inference composition metadata. All evaluation remains ranking-only; no retrieval/provenance/commit/ANSWER or Gate E promotion.

This single consistency comparison follows the closed attribute-loss ladder. Its output informs a separate decision about generalization, less hand-labeled supervision or runtime integration; it is not a mandate to keep optimizing this fixture. The synthetic task has repeatedly informed design and is not a sealed test set. C149 is not registered here.

Implementation: `gate_e_c148_train_consistent_composition.py`, `gate_e_c148_cli.py`, `tests_lm/test_v05_c148_train_consistent_composition.py`, `tools/run_c148.ps1`.
Reviewer: **24/24 new CPU tests**, toy weights/features and synthetic full-size prior records with a toy injected auditor; finite differences and exact control updates verified. Production head source byte-matched blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. Python compilation passed. Full **236-test** suite, real-prerequisite integration, CUDA and PowerShell are not reviewer-executed; no registered fresh-seed performance inspected.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference, not the V5-E persistent store.
- Synthetic vocabulary/factor fixtures are not scalable tokenization or open-domain semantic proof.
- Oracle substitution, explicit training supervision, hand-specified composition and learned factor discovery are distinct claims.
- Ranking-only results cannot be promoted to full-runtime or general FOLD intelligence claims.
