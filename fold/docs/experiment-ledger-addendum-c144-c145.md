# FOLD experiment ledger addendum — C144 to C145

## C144 — ACCEPTED PASS (descriptive attribution scope)

Experiment: `C144-v5e-factor-mismatch-attribution`.
Execution commit: `8bf17d36d95585750c7a14cd5de56f770f1de509`.
Evidence: user's complete terminal log supplied 2026-09-15.

Focused regression **162/162**. C144 loaded no model, performed no scoring/training/runtime retrieval, and recomputed the accepted C143 accounting from `summary.json` + `evaluation-manifest.json`. C143 summary/manifest hashes, tracked tree and execution HEAD were preserved. `run_execution_valid=True`.

C144 is a diagnostic execution PASS, not a model-capability PASS. It fully attributed every C143 ranking error to canonical factor mismatches.

### COLOR_AUX residual structure

C143 COLOR_AUX had 1,525 residual errors among 20,736 rankings.

| mismatch mask | errors |
|---|---:|
| MATERIAL | 679 |
| SHAPE | 305 |
| COLOR | 152 |
| SHAPE+MATERIAL | 168 |
| COLOR+MATERIAL | 147 |
| COLOR+SHAPE | 36 |
| COLOR+SHAPE+MATERIAL | 38 |

Material appears in `679+168+147+38 = 1,032` residual errors (**67.67%**). Shape appears in 547 (**35.87%**). Color appears in 373 (**24.46%**). Single-factor errors are 1,136/1,525; MATERIAL-only is the largest single class.

Bucket split remains consistent with C143: 351 COLOR_AUX errors on the four prior held-out combinations and 1,174 on the 52 newly evaluated combinations; training combinations remain error-free.

Value/alias diagnostics also show elevated material/shape pockets, e.g. expected `metal` error rate 0.089699 and aliases `steel` 0.09375, `alloy/mineral` 0.08912; shape `hexagonal` 0.091628 and aliases `six-sided` 0.105324, `honeycomb` 0.092593. These are descriptive rates, not isolated causes.

### Paired treatment transitions

C143 BASELINE→COLOR_AUX transitions recompute exactly:

```text
BOTH_CORRECT = 17070
RESCUED      = 2141
BOTH_WRONG   = 1417
REGRESSION   = 108
```

Rescued errors are broad, with COLOR involved in 1,301 and MATERIAL in 827. The 108 treatment regressions are concentrated away from color: MATERIAL is involved in 77 (**71.30%**), SHAPE in 38, COLOR in only 7. MATERIAL-only accounts for 65 regressions; SHAPE-only for 32.

Supported claim: after explicit color alignment, the dominant residual mismatch class is material-related, and material-related mismatches also dominate the small set of paired regressions. This justifies testing material alignment next.

Non-claim: C144 is post-hoc descriptive attribution. It does not prove that an auxiliary material objective will remove these errors or that material semantics are uniquely causal.

## C145 — ACTIVE

Experiment: `C145-v5e-material-alignment-intervention`.
Stage: `V5-E-MATERIAL-ALIGNMENT-INTERVENTION`.

**Scientific question:** when color alignment is already present, is adding only a training-time material alias→canonical alignment loss sufficient to eliminate material-involved residual errors without creating paired regressions?

### Paired design

Fresh seeds: `20261641..20261652`, disjoint from C138-C143 registered sets.

Per seed, create one initial `SharedRetrievalContentHead`, copy it into two arms, and assert identical initial fingerprints:

```text
COLOR_AUX:
  main retrieval CE + 1.0 * color alignment CE

COLOR_MATERIAL_AUX:
  main retrieval CE + 1.0 * color alignment CE + 1.0 * material alignment CE
```

Changed variable: **material alignment term only**.

Held constant: 49-d training-vocabulary features, hidden_dim 64, residual_scale 1.0, 24 main training queries, 8 main candidates, color supervision, AdamW lr 0.002, weight decay 0, 600 optimizer steps, logit scale 12.0, original raw evaluation text, 64-candidate C143 factorial catalog, no inference dictionary/oracle, no production runtime modification.

The material auxiliary derives 12 material aliases and 4 canonical material words from TRAIN_COMBINATION rows only. No validation/held-out fields construct the auxiliary labels. Coefficients are fixed at 1.0; no search or validation-selected checkpoint is permitted.

### Evaluation

Each arm is evaluated on:

1. the original 12 query / 12 candidate ranking as a scoped C142 safety control;
2. the complete C143 64-candidate / 1,728-query factorial ranking suite.

12 seeds × 1,728 = 20,736 full-catalog rankings per arm. Full-catalog evaluation remains ranking-only; expanded persisted retrieval/evidence/ANSWER is not executed.

For each arm, record total errors, mismatch masks, material-involved error count, group accuracy/margins, old-12 pass status and checkpoints. Pair query identities across arms to record rescues, new errors, material-related rescues and material-related regressions.

### Preregistered verdict

**PASS** requires all execution controls valid and:

- COLOR_AUX control has at least one material-involved full-catalog error (contrast exists);
- COLOR_MATERIAL_AUX has **zero material-involved full-catalog errors**;
- paired `new_errors == 0`;
- COLOR_MATERIAL_AUX preserves the original 12-query ranking with positive margin for all 12 seeds.

PASS is deliberately narrower than exhaustive all-case perfection: it establishes sufficiency for the registered material-related residual, not full factor composition.

**VALID NEGATIVE / FAIL:** controls valid but any preregistered condition fails. Report partial material-error reduction, total accuracy, rescues and regressions. Do not tune weights, increase steps, add shape supervision or change architecture under C145.

**INVALID:** C144 prerequisite/profile mismatch, protected/input hash failure, OOV, paired-init mismatch, nonfinite loss/scores, evaluation mutation or execution error. Resolve and retry C145.

Explicit material labels add training supervision and compute, not inference parameters. This remains synthetic development-set research. Gate E remains NOT PASSED. No C146 intervention before C145 is judged.
