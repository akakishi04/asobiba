# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
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

## Accepted chain through C146

- C137: ACCEPTED PASS, lexical addressing / 8-to-12 corpus growth.
- C138: ACCEPTED VALID NEGATIVE, hashed compositional alias fixture.
- C139: ACCEPTED VALID NEGATIVE, collision-free but not all-seed robust. C138/C139 also differ in dimensions/parameter shapes and seeds; do not isolate collision causality from their comparison.
- C140: ACCEPTED VALID NEGATIVE, twelve-seed replication; 8/12 completely correct.
- C141: ACCEPTED PASS, oracle evaluation-only color substitution, not learned raw-query improvement.
- C142: ACCEPTED PASS, training-only color alignment on the original 12-candidate fixture.
- C143: ACCEPTED VALID NEGATIVE, expanded frozen ranking; 1,525 COLOR_AUX errors in 20,736 cases; no runtime path.
- C144: ACCEPTED PASS, descriptive attribution only; material involved in 1,032/1,525 residuals and 77/108 regressions. Description is not unique causality.
- C145: ACCEPTED VALID NEGATIVE, paired material supervision. Errors 1,464->346, material involvement 798->28, 1,153 rescues and 35 regressions; both zero-residual/nonregression criteria failed. Detailed result and C146 registration: `docs/experiment-ledger-addendum-c145-c146.md`.
- C146: **ACCEPTED VALID NEGATIVE**, final all-three-factor supervised reference, based on user's complete log at `6582dac69fc6bab93cd8cdbc08ceef13d0542ba7`. Focused regression 194/194, all reported input/init/immutability/protection/HEAD/tree controls passed. No production or runtime evaluation.

```text
C146 fresh paired seeds: 20261661..20261672
COLOR_MATERIAL_AUX: 20,260/20,736 correct; 476 errors; 0/12 perfect models
ALL_FACTOR_AUX:     20,725/20,736 correct;  11 errors; 8/12 perfect models
Treatment accuracy 99.9469522%; net error reduction 97.6891%
Paired: rescued 469; new errors 4; both correct 20,256; both wrong 7
Residual masks: COLOR 5; MATERIAL 5; SHAPE 1
Failure models: 20261664 (2), 20261665 (1), 20261666 (7), 20261671 (1)
Original-12 strict model passes: 12/12 both arms
Original validation in 64 candidates: control 140/144; treatment 144/144
```

The strict all-case positive-margin gate failed; no favorable threshold/seed selection. Successful models show finite-task representability, not guaranteed learnability across seeds or general language competence. The console does not give the exact eleven failing texts or the stored singleton alignment accuracies; inspect full records rather than infer them.

Full C146 report, manifest and checkpoints: `runs/c146-v5e-all-factor-reference-9a40582d7ebb436e9debde9581131734/`.
Consumed C145 hash `c3c21bcb5687451ae6a1d4260e410dce7d47732c58bdf278dee8ac86ff670683` is not the C146 report's own hash.
Detailed verdict and C147 preregistration: **`docs/experiment-ledger-addendum-c146-c147.md`**.

**The color/material/shape named auxiliary-loss ladder is closed at C146.** Do not add more named factors or sweep losses/steps/width to chase 100% on this fixture. C142's scoped PASS and subsequent scoped negatives remain intact.

## Active experiment — C147

Experiment: `C147-v5e-frozen-composition-order`.
Stage: `V5-E-FROZEN-COMPOSITION-ORDER`.
Status: ACTIVE, awaiting user CUDA evaluation; no C147 result claimed.

Question: can independently encoding whitespace expressions and then pooling eliminate the eleven residuals on the same frozen C146 ALL_FACTOR_AUX heads?

```text
Source: all 12 ALL_FACTOR_AUX checkpoints, not just selected failures/successes
fresh seeds = 0; additional training = 0
POOL_THEN_ENCODE: h(B(whole text))
ENCODE_THEN_POOL: normalize(sum(h(B(unit)) for whitespace unit in text))
Same rule for query and descriptor; final dot-product ranking unchanged
64 candidates / 1,728 queries / same manifest and original raw text
20,736 full replay + 20,736 alternative rankings
144 original-12 replay + 144 alternative controls
```

No typed slots, axis-specific matching, alias dictionary or expected labels enter the new encoder. Hyphenated expressions retain their spelling and the original feature tokenizer within each unit. Equal unit normalization and changed nonlinear mixing are part of the declared alternative rule, not separately isolated causes. Whitespace boundaries match this synthetic fixture's attribute expressions; no automatic segmentation or factor discovery is claimed. Source explicit supervision remains.

Original full rankings and old-12 controls must replay with identical discrete predictions/rivals and score components within absolute tolerance 1e-5. Revalidate full C146 records via its auditor; verify source manifest, checkpoints, vocabulary/config and fingerprints. No retraining fallback. Preserve source files, C37 and fixture. All evaluation remains ranking-only; Gate E stays NOT PASSED.

- PASS: alternative full rankings and old-12 controls are all correct with strictly positive finite margins on all twelve models. Supports this alternative rule's sufficiency only; necessarily rescues 11 and preserves 20,725.
- FAIL: valid execution but residual/new errors or nonpositive margins remain. Report rescued/new cases and masks; no pooling-weight or normalization search under this number.
- INVALID: prerequisite/manifest/checkpoint/hash/vocabulary/replay/numeric/immutability/execution problem; repair and retry C147.

Save complete mode-wise rankings, group metrics, paired transitions, the original eleven cases and all new errors, and source singleton-fit diagnostics. Per-unit cache accounting is not a performance benchmark.

This is one composition diagnostic before a separately registered decision on train-consistent composition, less manual supervision, or broader task/runtime work. Do not register C148 before judging C147.

Implementation: `gate_e_c147_composition_order.py`, `gate_e_c147_cli.py`, `tests_lm/test_v05_c147_composition_order.py`, `tools/run_c147.ps1`.
Reviewer: **18/18 new CPU helper tests**, toy weights/features; Python compilation passed; production-head source byte-matched blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. Full **212-test** suite, full accepted-record integration, CUDA and PowerShell not reviewer-executed. No real source checkpoint evaluated here.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference, not the V5-E persistent store.
- Synthetic vocabulary/factor fixtures are not scalable tokenization or open-domain semantic proof.
- Oracle substitution, explicit training supervision, hand-specified composition and learned factor discovery are distinct claims.
- Ranking-only results cannot be promoted to full-runtime or general FOLD intelligence claims.
