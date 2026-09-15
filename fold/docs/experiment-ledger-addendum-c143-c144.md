# FOLD experiment ledger addendum — C143 to C144

## C143 — ACCEPTED VALID NEGATIVE

Experiment: `C143-v5e-frozen-factorial-ranking-audit`.
Execution commit: `52f5a3159c68c7138e2ff568b4276e9cd58e18fe`.
Evidence: user's complete terminal log supplied 2026-09-15.

Focused regression **152/152**. All 24 saved C142 checkpoints reconstructed successfully; original 12-query ranking replay matched at rate 1.0; frozen weights, manifest/input hashes, zero OOV, zero paired lexical overlap, protected C37/fixture, tracked tree and execution HEAD all passed. No training or production runtime modification occurred. C143 is ranking-only; expanded persisted retrieval/evidence/ANSWER was not exercised.

COLOR_AUX improved over BASELINE but failed the preregistered all-case criterion:

| Group | BASELINE | COLOR_AUX |
|---|---:|---:|
| ALL | 17178/20736 = 0.828414 | 19211/20736 = 0.926456 |
| TRAIN_COMBINATION | 2592/2592 = 1.0 | 2592/2592 = 1.0 |
| PRIOR_HELDOUT_COMBINATION | 603/1296 = 0.465278 | 945/1296 = 0.729167 |
| NEW_COMBINATION | 13983/16848 = 0.829950 | 15674/16848 = 0.930318 |
| ORIGINAL_VALIDATION_IN_64 | 115/144 = 0.798611 | 128/144 = 0.888889 |

COLOR_AUX residual errors: **1525**. BASELINE errors: **3558**. Paired comparison: **2141 rescued**, **108 regressions**, leaving **1417 both-wrong** cases. No model passed all 1728 extended rankings. COLOR_AUX minimum expected-class margin was `-0.1562342942`.

Supported claim: C142's training-only color alignment materially improves the frozen head on the exhaustive in-vocabulary synthetic catalog, including 52 newly evaluated combinations, but does not generalize perfectly once the candidate catalog and query coverage expand. C142 remains a valid scoped PASS on its original 12-candidate evaluation; C143 closes as a valid negative for exhaustive 64-candidate ranking.

Non-claims: no end-to-end runtime failure is established because C143 never exercised the expanded persisted retrieval path; no single causal factor is identified by aggregate accuracy; the 52 new combinations and 27 alias spellings remain synthetic variants generated from the known factor schema.

## C144 — ACTIVE

Experiment: `C144-v5e-factor-mismatch-attribution`.
Stage: `V5-E-FACTOR-MISMATCH-ATTRIBUTION`.

Scientific question: **which canonical factor differences dominate C143 residual errors and the treatment's rescued/regressed decisions?**

C144 is a pure post-hoc analysis of the accepted C143 `summary.json` and `evaluation-manifest.json`.

No model is loaded. No checkpoint is scored. No training, candidate ranking, runtime retrieval, provenance validation, commit, or ANSWER execution occurs. Additional training steps = 0; additional ranking decisions = 0. The analysis recomputes C143 aggregate counts from full records before attribution.

Every wrong prediction is classified by the canonical descriptor factors that differ between expected and selected candidates:

```text
COLOR
SHAPE
MATERIAL
COLOR+SHAPE
COLOR+MATERIAL
SHAPE+MATERIAL
COLOR+SHAPE+MATERIAL
```

It also reports Hamming distance in factor space, bucket-specific masks, expected-value and alias-token error rates, and paired BASELINE→COLOR_AUX transitions. The 2141 rescues and 108 regressions receive their own mismatch-mask distributions.

This is descriptive attribution, not a causal intervention. Concentration in one factor does not prove that adding a matching auxiliary loss will fix it. Factor labels come from the synthetic evaluation manifest.

Execution-valid PASS means the full C143 records/manifest are internally consistent with the accepted aggregate profile and every error is completely attributable to one of the registered factor masks. The substantive scientific output is the distribution itself, which determines the next experiment. INVALID means prerequisite/hash/count/record inconsistency or execution failure; retry C144 after resolution.

No C145 intervention should be selected before C144's factor distribution is inspected.
