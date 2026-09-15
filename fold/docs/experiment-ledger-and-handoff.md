# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; user runs `.venv-py31315\Scripts\python.exe`.
- Protected C37: `runs/chatgpt-last-result.json`; SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture: `runs/fixtures/v05-c-composition-20260921.pt`; SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry same C number; valid negatives close their number after interpretation.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, and this handoff before continuing. Preserve claim/non-claim, execution guards, progress and log collection.

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
`docs/evidence-recovery-mode-v0.1.md` is a separate design document, not implemented by the current ranking experiments.

## Accepted chain through C145

- C137: ACCEPTED PASS, lexical content-addressing / 8-to-12 corpus-growth scope.
- C138: ACCEPTED VALID NEGATIVE, compositional alias fixture with hashed front end.
- C139: ACCEPTED VALID NEGATIVE, collision-free diagnostic; finite solution possible but not all-seed robust. C138/C139 also change dimension/parameter shape and seeds, not an isolated collision-effect estimate.
- C140: ACCEPTED VALID NEGATIVE, 12-seed robustness replication; 8/12 fully correct.
- C141: ACCEPTED PASS, oracle evaluation-only color substitution; all C140 errors rescued, no new errors.
- C142: ACCEPTED PASS, training-only supervised color alignment on original 12-candidate fixture; 12/12 COLOR_AUX heads pass, BASELINE 5/12.
- C143: ACCEPTED VALID NEGATIVE, frozen exhaustive 64-candidate ranking; COLOR_AUX 19,211/20,736, 1,525 residual errors. No runtime path evaluated.
- C144: ACCEPTED PASS, descriptive attribution only; 162/162 regression; material involved in 1,032/1,525 residuals and 77/108 paired regressions. Attribution is not a unique causal explanation.
- C145: **ACCEPTED VALID NEGATIVE** based on the user's full log at `b7d82dad56fb03cd270a62a7e8d01fc014025197`; 174/174 regression; twelve fresh paired seeds `20261641..20261652`. Valid input/protection/init/weight/HEAD/tree checks, no production modification or runtime evaluation.

C145 paired comparison:

```text
COLOR_AUX:          19,272 / 20,736 = 92.9398148%; errors 1,464; material-involved 798
COLOR_MATERIAL_AUX: 20,390 / 20,736 = 98.3314043%; errors   346; material-involved  28
rescued = 1,153; new errors = 35; both wrong = 311; both correct = 19,237
material-involved rescues to complete correctness = 724; new material errors = 4
original-12 positive-margin passes = 12/12 models in both arms
full-catalog perfect models = 0/12 in both arms
```

C145 failed both zero material residual and zero new-error requirements despite large improvement. Material error-count reduction is 96.49%; total error-count reduction is 76.37%. Do not confuse net mismatch-count reduction with complete case rescue.

Treatment masks: SHAPE 294; COLOR 21; MATERIAL 15; SHAPE+MATERIAL 12; COLOR+SHAPE 3; COLOR+MATERIAL 1. Shape is involved in 309/346 (89.31%), material in 28, color in 25; counts overlap. This motivates a final all-three-factor supervised reference, not a claim that shape labels are uniquely causal.

Full C145 result and 24 saved heads: `runs/c145-v5e-material-alignment-60955308e1004127836054c3d8b024dc/`.
Consumed C144 hash: `c56823a036f22eae47da953d5ccdd0888eb7697ba9efb8ae41f8114a4ab0fe43` (NOT the C145 report's own hash).
Detailed evidence, limits and C146 preregistration: **`docs/experiment-ledger-addendum-c145-c146.md`**. Earlier detail remains in the corresponding chained addenda; C142 PASS and C143 negative are not overridden.

## Active experiment — C146

Experiment: `C146-v5e-all-factor-supervised-reference`.
Stage: `V5-E-ALL-FACTOR-SUPERVISED-REFERENCE`.
Status: ACTIVE, awaiting user CUDA execution. No C146 performance result claimed.

Question: does adding only shape alignment to the fixed color+material training objective make the unchanged shared head solve the entire existing factor/alias catalog?

```text
fresh seeds = 20261661..20261672; 24 newly trained heads, not checkpoint continuations
same copied initial state per seed; independent optimizers
COLOR_MATERIAL_AUX = main CE + color CE + material CE
ALL_FACTOR_AUX    = same + shape CE
coefficients = 1.0 for included auxiliary terms; shape absent in control
same 49-d features / hidden 64 / residual 1.0
same AdamW lr 0.002 / weight decay 0 / 600 steps / logit scale 12
24 main training queries / 8 main candidates
12 training aliases vs 4 canonical values per auxiliary factor
original raw text, no inference oracle or tokenizer changes
64 candidates / 1,728 queries / 20,736 full rankings per arm
plus original12 safety rankings (144 per arm)
```

All labels for auxiliary objectives derive from TRAIN_COMBINATION fields only. Shape aliases with hyphens retain the original feature tokenizer. Extra supervision/compute is disclosed; equal steps do not mean equal FLOPs. The model size and inference path do not change. All evaluation is ranking-only; no provenance/commit/ANSWER measurement.

PASS: every ALL_FACTOR_AUX full ranking and original-12 ranking is correct with a strictly positive finite margin across all twelve seeds; all controls valid. Report paired rescue/regression and lack of a baseline-error contrast if both arms are perfect. FAIL: valid execution but any treatment error/nonpositive margin or original-12 failure. INVALID: prerequisite/input/manifest/OOV/init/numeric/mutation/execution failure; resolve and retry C146.

The complete C145 result is reaggregated and bound to its accepted configuration/seed/mask/pair profile. Preserve C145/C37/fixture. The exact C143 manifest hash is verified with explicit LF/CRLF serialization handling; no new test cases are selected based on outcomes. Save both checkpoints, original/full rankings, all-factor masks, group metrics, training alias-fit diagnostics, initial/final fingerprints, input hashes, commit and environment.

**Scope/exit:** this completes the registered color/material/shape auxiliary-loss ladder as a supervised reference, not a theoretical ceiling or production solution. After judgment, do not keep adding named losses or tune this fixture until it passes. Review whether to compare a less hand-labeled learning method or investigate remaining representation/composition failures. Automatic factor discovery is not established, nor proven necessary. C147 is not yet registered. Gate E remains NOT PASSED.

Implementation: `gate_e_c146_all_factor_alignment.py`, `gate_e_c146_cli.py`, `tests_lm/test_v05_c146_all_factor_alignment.py`, `tools/run_c146.ps1`.
Reviewer verification: 20/20 new CPU helper tests, synthetic weights and full synthetic prerequisite records, Python compilation; production-head local source matched blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. Full 194-test focused regression, PowerShell and formal CUDA experiment are not reviewer-executed. No registered seed result inspected.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C146 factor fixtures are synthetic development tasks, not scalable production tokenization or open-domain semantic evidence.
- Oracle substitution, explicit supervision and automatically discovered semantic factors are distinct claims.
- Ranking-only success cannot be promoted to full-runtime or general FOLD intelligence claims.
