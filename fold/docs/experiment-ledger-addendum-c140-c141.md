# FOLD experiment ledger addendum — C140 to C141

## C140 — ACCEPTED VALID NEGATIVE

Experiment: `C140-v5e-collision-free-multiseed-robustness`.
Execution commit: `f036550182c99a06865d788dacf055e3dea5820d` on `feat/sft-target-loss`.
Evidence is the user's complete terminal log supplied on 2026-09-15, not an independent rerun by the reviewing agent. Full per-case records and margins remain in the local run's `summary.json`.

Focused regression: **96/96**. Twelve fresh seeds `20261601..20261612`, 12 cases per seed (8 known and 4 held-out combinations). All reported prerequisite, collision/OOV, provenance, commit indicator, ANSWER, protected-artifact and tracked-tree checks passed. No production runtime code changed. Gate E remains **NOT PASSED**.

| Measurement | Result |
|---|---:|
| Known combinations | 96/96 = 1.0 |
| Held-out recombinations | 44/48 = 0.9166666667 |
| Overall scenario / key / final evidence | 140/144 = 0.9722222222 |
| Completely correct seeds | 8/12 = 0.6666666667 |
| Worst seed unseen accuracy | 0.75 |
| Worst expected-class margin | -0.0787280798 |

All four errors:

| Seed | Expected key | Selected key | Expected margin (seed minimum) |
|---|---|---|---:|
| 20261602 | q10 | q2 | -0.04168138 |
| 20261604 | q11 | q1 | -0.07872808 |
| 20261606 | q11 | q1 | -0.05310401 |
| 20261612 | q10 | q2 | -0.00510031 |

The all-seed, all-case, strictly-positive-unseen-margin criterion was not met. C140 is closed as a valid negative, not retried until a favorable seed set appears. It replicates seed-associated variability under the unchanged C139 configuration. It does not identify a unique optimization mechanism or prove architectural impossibility. The 48 unseen decisions reuse only four distinct held-out queries; they are not 48 independent tasks.

### Interpretation and confound audit

The fixture identifies `q10 = green round stone` versus `q2 = blue round stone`, and `q11 = yellow square wood` versus `q1 = red square wood`. The observed wrong records retain shape and material but differ in color.

Static inspection of **training rows only** finds eight distinct shape/material pairs for eight records. Thus training record identities can be distinguished without using color. This is a data property, not proof that a particular learned head ignored color. A color-insensitive shortcut is permitted by the training task; capacity, nonlinear interactions, normalization, alias alignment and optimization are not separately isolated by the current log.

C138-to-C139 improvement must also not be reported as the isolated causal effect of hash collisions: input dimension changed from 128 to 49 (changing parameter shapes/counts), signed hashing became an unsigned vocabulary basis, and seed sets changed. This limits that cross-experiment causal attribution; it does not invalidate the fixed-configuration C140 replication.

`provenance = 1.0` authenticates the retrieved source, not relevance to the intended query. A real but wrong record can pass provenance checks. C140's `commit_count` is a harness-level acceptance indicator; this run does not independently re-establish transactional crash safety.

## C141 — ACTIVE, AWAITING USER CUDA EXECUTION

Experiment: `C141-v5e-color-alias-localization`.
Stage: `V5-E-COLOR-ALIAS-LOCALIZATION`.

**Scientific question:** with the C140 heads held fixed, does replacing only the query's color alias with its canonical color rescue all four observed errors without introducing any new errors?

This is an **oracle-assisted localization diagnostic**, not a proposed production feature. The alias map uses the existing fixture's color-first structure and TRAIN_COMBINATION descriptors/queries only. No evaluation label or held-out descriptor chooses the replacement. Nonetheless, extracting positional factor correspondences supplies privileged diagnostic structure and introduces intentional lexical overlap with record descriptors. It must not be described as a learned canonicalizer or alias generalization success.

Examples:

```text
emerald curved rocky -> green curved rocky
amber boxy timber   -> yellow boxy timber
```

### Changed / held constant

Changed: the first (color) word of each validation query at evaluation only, in the CANONICAL_COLOR arm. Shape/material wording is unchanged.

Held constant: training data, training objective/schedule, head architecture/width/residual scale, 49-dimensional vocabulary basis, all 12 record descriptors and candidates, actual persisted corpus, exact retrieval and the C140 evidence/ANSWER harness. Baseline and treatment within each seed share the same learned parameters; no extra optimizer step or fine-tuning is permitted.

Seeds: **the same twelve C140 seeds**, `20261601..20261612`. Fresh seed count is **zero**. All successes and failures are retained; no failure-seed selection. These are diagnostic replays, not additional independent robustness evidence.

C140 did not serialize head checkpoints. C141 therefore reuses the exact C139 training function, replays the original 144 decisions, and checks the full discrete case outcomes plus ranking identities and score margins against the local C140 `summary.json` (absolute tolerance `1e-5`). Any replay discrepancy is INVALID, not evidence for the intervention. Model-weight fingerprints must be unchanged across both evaluation arms.

```text
12 replay seeds
8 training combinations, 3 training queries per combination
12 live candidates
12 BASELINE_REPLAY cases / seed
12 CANONICAL_COLOR cases / seed
144 original cases + 144 intervention cases = 288 evaluated decisions
```

### Preregistered criteria

**PASS:** baseline replay and all controls are valid; all 4 original failures are rescued; all 140 original successes are preserved; all canonical-color cases succeed through retrieval/evidence/ANSWER and have strictly positive expected-class margins.

**VALID NEGATIVE / FAIL:** valid replay and controls, but incomplete rescue, new errors, or a nonpositive treatment margin. Report rescued failures and newly introduced errors separately. A mixed result is not collapsed into a single mechanism claim.

**INVALID:** wrong/missing full C140 prerequisite, wrong protected hashes, replay disagreement, OOV, nonfinite scores, changed weights/input files, failed authority controls or execution errors. Retry the same C141 number after resolving execution validity; do not register an architectural conclusion from it.

PASS supports sufficiency of this narrow oracle color substitution for the observed fixture failures, not that aliases were never learned or that pooling is otherwise correct. FAIL rejects its sufficiency, not all possible alias-related explanations. Neither result passes Gate E or changes the C139/C140 verdicts. No production implementation or C142 starts before C141 is judged.

### Implementation and validation

- `fold_lm/v05_benchmarks/gate_e_c141_color_alias_localization.py`
- `fold_lm/v05_benchmarks/gate_e_c141_cli.py`
- `tests_lm/test_v05_c141_color_alias_localization.py`

Before publication, the reviewing agent ran the **12 new helper tests on CPU**, successfully, and compiled the new Python files. The complete 108-test focused suite and paired CUDA experiment were **not run** by that agent; user execution remains required. The expected focused count is C140's 96 plus these 12 = 108, subject to the pinned source revision.

C141 stores its own `summary.json`, run commit, prerequisite/input hashes, environment, both arms' records/margins, rescue counts and frozen-weight fingerprints. It never overwrites `runs/chatgpt-last-result.json` (protected C37). A valid scientific FAIL returns CLI exit code 0; execution exceptions return nonzero, with `invalid.json` when the output directory has been established.
