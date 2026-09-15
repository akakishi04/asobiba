# FOLD experiment ledger addendum — C142 to C143

## C142 — ACCEPTED PASS (supervised, finite-fixture scope)

Experiment: `C142-v5e-training-only-color-alignment`.
Execution commit: `680ad7b4063e284504a36e0ded1c05a781d467a3`, branch `feat/sft-target-loss`.
Evidence: the user's uploaded complete terminal log on 2026-09-15, not a reviewer CUDA rerun.
Source log SHA256: `c989aea738e29e516ebe68726eabde928cdbd1d86457afdfe677e920300a8888`.
Local full result: `runs/c142-v5e-training-only-color-alignment-90ebc41c7ada4d679d20b7c902cd3d29/summary.json`.
Consumed C141 SHA256: `1a3ded18c9066cfbfc7ab4a60839058ced82120abc3036258dad9170fc7deadc`.
The C142 result's own SHA256 is not printed in that log and is not the C141 prerequisite hash; C143 computes it locally.

Focused regression **130/130**. Twelve fresh paired seeds `20261621..20261632`, 24 heads, 144 original-query cases per arm. Initial paired weights, inference-oracle exclusion, zero paired lexical overlap, zero OOV, evaluation-weight preservation, prerequisite/input/protected hashes, tracked tree and execution HEAD checks all passed. No production runtime code changed. `run_execution_valid = True`.

| Metric | BASELINE | COLOR_AUX |
|---|---:|---:|
| Known-combination correct cases | 96/96 | 96/96 |
| Held-out-combination correct cases | 39/48 = 0.8125 | 48/48 = 1.0 |
| All cases | 135/144 = 0.9375 | 144/144 = 1.0 |
| Completely correct models | 5/12 | 12/12 |
| Worst unseen expected-class margin | -0.0809568167 | +0.0474634767 |

All **9** baseline errors were rescued; all **135** baseline successes were preserved; **0** new errors. The preregistered COLOR_AUX all-case/all-seed positive-margin criterion is met. Baseline-error contrast is available; this is not a both-arms-perfect result.

Baseline errors:

- `20261622: q9 -> q2`
- `20261623: q11 -> q1`
- `20261625: q10 -> q2`
- `20261628: q11 -> q1`
- `20261629: q10 -> q2, q11 -> q1`
- `20261631: q10 -> q2, q11 -> q1`
- `20261632: q11 -> q1`

Supported claim: in this registered paired experiment, adding the specified training-only color-alignment auxiliary loss to the unchanged shared head was sufficient for all tested original alias queries, and improved the observed baseline outcomes. Unlike C141, evaluation did not replace words or consult a color map. No new inference parameters or processing stage were introduced.

Non-claims: not open-domain language understanding, unsupervised factor discovery, a scalable tokenizer, a general all-seed guarantee, or production/Gate E readiness. Training receives explicit color-first factor supervision and extra forward/backward work. Equal 600 optimizer steps is not equal training compute. Only four distinct held-out combinations were tested, repeatedly across seeds, after the fixture had already informed intervention design. C139/C140 remain accepted negatives under their own conditions.

Mechanism caution: `q9 = blue hexagonal metal` versus selected `q2 = blue round stone` preserves color and changes shape/material. Thus not all C142 baseline errors are literal wrong-color choices. The shared encoder is changed by the auxiliary gradients; the result does not isolate one internal semantic mechanism. Source provenance still does not establish query relevance, and commit-once in the C142 harness is not a new transactional-durability measurement.

## C143 — ACTIVE, awaiting user checkpoint evaluation

Experiment: `C143-v5e-frozen-factorial-ranking-audit`.
Stage: `V5-E-FROZEN-FACTORIAL-RANKING-AUDIT`.

**Question:** do the frozen C142 COLOR_AUX heads select the correct descriptor across the entire in-vocabulary color/shape/material product and all available alias spellings, rather than only the four repeatedly studied held-out queries?

### Frozen-model evaluation extension

No training, coefficient tuning, architecture change, checkpoint selection or inference-time oracle is allowed. Load **all 24 saved C142 checkpoints**, both arms for all 12 original seeds. These are reused models, **fresh seed count = 0**, additional optimizer steps = 0. No retraining fallback is allowed when a checkpoint is missing or incompatible.

First validate the full accepted C142 report and its exact case profile. Load checkpoint bytes from the same run directory using `weights_only=True`, verify file SHA/size, config, ordered vocabulary and tensor fingerprint. Freeze the head, then reproduce the original **12-query / 12-candidate** ranking results and margins against the C142 report (absolute tolerance `1e-5`). A replay discrepancy is INVALID, not a scientific negative. It verifies ranking reconstruction only; the saved heads do not include a router.

### Complete deterministic evaluation manifest

From TRAIN_COMBINATION rows only, collect four canonical colors, four shapes, four materials, and the three existing alias spellings for each factor value. Whitespace separates the three fixture factors; hyphenated aliases remain intact until the unchanged C139 tokenizer processes raw text.

Enumerate the full factor product before loading or scoring any model:

```text
4 colors x 4 shapes x 4 materials = 64 candidate descriptions
8 training combinations
4 previously evaluated held-out combinations
52 newly evaluated combinations

3 color aliases x 3 shape aliases x 3 material aliases = 27 raw queries / combination
64 x 27 = 1,728 unique query strings / model
24 saved models x 1,728 = 41,472 ranking decisions
plus 24 x 12 = 288 original-12 reconstruction controls
```

Original descriptor indices 0..11 are preserved; the remaining 52 descriptions are appended in lexicographic order. All 64 descriptors compete in every extended query. Alias tuples are enumerated lexicographically, with no outcome-based filtering. The positional factor map belongs to the labeled test generator, not to inference: the scorer receives only raw-text features and descriptor features. Expected labels are used after scoring to compute correctness and margins. All target-paired lexical overlaps must be zero and all words must fit the original 49-dimensional training vocabulary.

Per-model reporting groups:

- `TRAIN_COMBINATION`: 8 x 27 = 216 query strings, including the original 24 training strings; not all are held out.
- `PRIOR_HELDOUT_COMBINATION`: 4 x 27 = 108 query strings.
- `NEW_COMBINATION`: 52 x 27 = 1,404 query strings.
- `ORIGINAL_VALIDATION_IN_64`: the exact 12 original validation strings, now ranked against all 64 candidates. This overlaps the groups above and must not be added to their counts.

The original-12 replay separates reconstruction validity from evaluation expansion. The `ORIGINAL_VALIDATION_IN_64` metric helps reveal losses due to the larger candidate set, while the newly generated queries test expanded coverage. This is an exhaustive evaluation extension, not a single-confound causal estimate: catalog size and query coverage expand together.

### Deliberate scope: ranking only

**C143 does not execute PersistedStructuralRetrievalAdapter, evidence/provenance validation, commit or ANSWER for the expanded candidates.** The 64 descriptions are a generated evaluation catalog, not an expansion of the production persisted corpus. `runtime_path_exercised = False`. This stage audits the learned selector directly without changing or attributing results to a new runtime path. Full persisted integration for any expanded corpus would require a separately registered experiment. Never label C143 ranking accuracy as end-to-end retrieval/evidence accuracy.

Held constant: stored learned weights, both original comparison arms, shared head implementation, 49-dimensional vocabulary/feature implementation, cosine-equivalent scoring, and inference without an alias map. The actual C139 feature functions are reused by the formal runner; no alternative encoder is silently substituted.

### Preregistered verdict

**PASS:** all reconstruction/input/checkpoint/lexical/numeric/immutability controls are valid, and all **20,736 COLOR_AUX ranking decisions** (12 x 1,728) are correct with a strictly positive finite expected-class margin. Record the BASELINE comparison and paired rescues/new errors, but do not require baseline failures or replace models to obtain a contrast.

**VALID NEGATIVE / FAIL:** controls are valid but any COLOR_AUX ranking error or nonpositive margin remains. Preserve the scoped C142 PASS; conclude that its success does not extend to the registered exhaustive factor/alias catalog. Report combination-group outcomes and original-query-in-64 outcomes separately before choosing another intervention. Do not automatically add auxiliary losses to other factors or tune the coefficient within C143.

**INVALID:** missing/wrong full C142 prerequisite, checkpoint bytes/config/vocabulary/fingerprint mismatch, reconstruction mismatch, OOV/lexical-control failure, nonfinite scores, input/model/protected-file mutation or execution failure. Resolve and retry C143 without silently retraining.

Even a PASS covers only this finite synthetic vocabulary and the stored models. The 52 combinations are newly evaluated but not a separately sourced sealed dataset; the aliases and factor schema are already known. Neither 41,472 repeated model decisions nor 1,728 related query strings are independent real-world tasks. No general reasoning, open-domain generalization, production scalability or Gate E pass follows.

### Implementation and verification

- `fold_lm/v05_benchmarks/gate_e_c143_frozen_factorial_audit.py`
- `fold_lm/v05_benchmarks/gate_e_c143_cli.py`
- `tests_lm/test_v05_c143_frozen_factorial_audit.py`
- `tools/run_c143.ps1`

Reviewer verification: **22/22 new CPU tests passed**; new Python modules compiled. The local production head and fixture copies used by the tests matched repository Git blobs `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6` and `dabd0b59cfa1078c3534baaba516d6d097a38ac7`. Tests used synthetic model weights, not the user's C142 checkpoints. No formal C143 outcome has been observed. The full **152-test** focused suite and CUDA checkpoint evaluation remain for user execution. The PowerShell script was reviewed but was not executed by the reviewer (PowerShell unavailable).

Write a unique run directory containing the evaluation manifest and its hash, all per-query rankings/margins, per-group summaries, reconstruction records, checkpoint/input hashes, commit and environment. C142 checkpoint files and the protected C37/fixture are read-only. Summary publication is atomic; scientific FAIL returns exit code zero, while execution failures return nonzero and retain `invalid.json`. No C144 before formal C143 judgment.
