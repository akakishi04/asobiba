# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`, branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`: SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read AGENTS.md, docs/experiment-conversation-handoff-protocol.md and this handoff before continuing. One scientific question per C number; invalid executions retry the same number; accepted negatives stay recorded.

## Gate status and boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier harden binding, scope, authority, replay, atomic claim, recovery and fencing. C133-C135 use persisted corpus/StructuralIndex. C136 selects fixed addresses; C137 introduces shared content addressing/dynamic candidates.
Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains separate design, not implemented by ranking diagnostics.

## Accepted through C150

- C137 PASS, lexical addressing/growth. C138-C140 VALID NEGATIVE, composition/seed sensitivity. C138/C139 did not isolate hash-collision causality (dimensions, parameter shapes and seeds also differ).
- C141 PASS, oracle substitution only. C142 PASS, train-only color supervision on the original small task.
- C143 VALID NEGATIVE on expanded rankings. C144 PASS, descriptive mismatch accounting.
- C145 VALID NEGATIVE: material supervision, errors 1464->346. C146 VALID NEGATIVE: all-factor reference, errors 476->11; named-attribute-loss ladder closed. See corresponding addenda.
- C147 VALID NEGATIVE: frozen composition change 11->4, with 3 new errors. C148 VALID NEGATIVE: train-consistency change 11->12, 0 rescues/1 regression; no demonstrated remedy. See `docs/experiment-ledger-addendum-c147-c148.md` and `docs/experiment-ledger-addendum-c148-c149.md`.
- C149 PASS, numerical accounting only. Same-factor positive, cross-factor negative, candidate normalization positive in all 23 source errors. This is convention-dependent arithmetic, not unique training causality or authorization to delete cross terms. See `docs/experiment-ledger-addendum-c149-c150.md`.
- **C150 ACCEPTED PASS**, registered synthetic GLOBAL_CONCEPT ranking sufficiency. User complete log at `1e9cfdbaf3631dbb207d2177f6ff6291673ec286`; regression 275/275, all reported controls/protected files/tree/HEAD valid. No runtime or production change.

```text
C150 paired fresh seeds 20261701..20261712
WITHIN_FACTOR: 20735/20736, 1 error, 11/12 exhaustive-perfect models
GLOBAL_CONCEPT: 20736/20736, 0 errors, 12/12 exhaustive-perfect models
Original12 strict passes: 12/12 in both arms
Paired: 1 rescue, 0 regressions, 20735 both correct, 0 both wrong
Worst margin: -0.00006809830666 -> +0.14257526397705
Only control error: seed 20261712, SHAPE+MATERIAL, prior-heldout bucket
Exact failing text/selected descriptor not printed; do not guess them.
```

Accuracy contrast is one decision, not broad statistical superiority. The larger observed worst-case margin is not calibrated confidence or proof of universal per-case improvement. C150 did not rerun C149 decomposition or train prior failure seeds; do not claim it proves orthogonality or rescues C148's failures. All earlier scoped verdicts remain unchanged.

C150 report: `runs/c150-v5e-global-negatives-073fe58a1c744fd28eebb9b8d225c7f9/summary.json`.
**C150 report SHA256:** `7e87a93e60ad334a9077fa132a0dc73da07a3da159c6f572d81190b66c8b95e7`.
Manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Detailed evidence and preregistration: **`docs/experiment-ledger-addendum-c150-c151.md`**.

## Review decision

Close tuning of the original eight-combination split. GLOBAL_CONCEPT is a task-scoped research candidate, not a deployed fix. Named-loss, train-composition and negative-pool intervention series are not invitations to sweep coefficients/width/steps/temperature. Keep the two C150 recipes fixed and test sensitivity to replacement training splits.

## Active C151 — Cross-split replication

`C151-v5e-cross-split-replication`, stage `V5-E-CROSS-SPLIT-REPLICATION`; ACTIVE awaiting user CUDA execution, no performance result claimed.

Question: does the fixed GLOBAL_CONCEPT recipe meet the exhaustive gate across four new main-training splits, compared with the unchanged WITHIN_FACTOR control?

- Four balanced eight-combination training sets, excluding original eight and mutually disjoint; each value appears twice per axis. Each set gives 24 queries with the original ordered alias schedule. Selection is data-only, never outcome-dependent.
- S1 seeds 20261721..23; S2 20261724..26; S3 20261727..29; S4 20261730..32. Twelve unique paired initializations / 24 heads.
- Same C150 training function, within-four/global-twelve candidates, 36 auxiliary positive pairs, 600 updates/.002 lr/scale12, three auxiliary weights1, head feature49/hidden64/residual1.
- Same POOL_THEN_ENCODE main training and ENCODE_THEN_POOL evaluation. No inference dictionary, scorer change, extra loss or checkpoint continuation.
- Same 64 candidates/1728 queries. Each split: 8 current training combinations and 56 held-out; metrics must use CURRENT_TRAIN_COMBINATION and HELDOUT_COMBINATION, not C143's obsolete split flags.
- 41472 full rankings plus 288 legacy original12 controls. Original12 is not necessarily held out under a new split.

**Split plan SHA256:** `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`. All four concrete plans are written before training. Vocabulary and 36 positives are re-extracted from each new training split and checked against the original training specification. Source C150 full report must match its exact hash and reaggregate through the existing C146 auditor. Old checkpoints are neither loaded nor modified.

PASS: all GLOBAL_CONCEPT full and original12 rankings correct with strictly positive finite margins on all four splits/twelve models, with valid controls. Report every split and paired rescue/regression; if both arms perfect, no demonstrated superiority.
FAIL: valid execution with treatment residual/nonpositive margin; do not retune or change splits. INVALID: identity/reaggregation/plan/config/vocabulary/init/numeric/reference/mutation/execution discrepancy; repair same C151.

**This is new splits in the same synthetic task, NOT an independent task-family or language benchmark.** Fresh seeds do not create fresh semantic tasks. No automatic factor discovery, production readiness or Gate E promotion. Review independent task-family evaluation or runtime integration after this bounded replication, not further automatic fixture optimization. No C152 registered.

Implementation: `gate_e_c151_cross_split.py`, `gate_e_c151_cli.py`, `tests_lm/test_v05_c151_cross_split.py`, `tools/run_c151.ps1`.
Reviewer: **23/23 CPU helper tests** plus compilation. Full **298-test** suite, real full-prerequisite integration, CUDA training/scoring and PowerShell not reviewer-executed. No official C151 model performance inspected. Per-run checkpoints include experiment/split/negative-scope/composition metadata.

## Non-claims

Shared-Basis partition and KV/context work remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store. Oracle substitution, explicit supervision, manual composition and discovered factors differ. Ranking-only success does not establish retrieval/provenance/commit/ANSWER or general FOLD intelligence.
