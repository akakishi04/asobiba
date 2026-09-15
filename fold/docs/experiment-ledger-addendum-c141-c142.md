# FOLD experiment ledger addendum — C141 to C142

## C141 — ACCEPTED PASS (oracle localization only)

Experiment: `C141-v5e-color-alias-localization`.
Execution commit: `b913e56950e7c0454ca63ec58f1f05f7439e7205` on `feat/sft-target-loss`.
Evidence: the user's complete terminal log supplied on 2026-09-15, not an independent reviewer CUDA rerun.
Local full report: `runs/c141-v5e-color-alias-localization-718ccf78048943dd92820ea86cfa11b0/summary.json`.
Consumed C140 summary SHA256: `a0b23c3a24d6674efd3f9c229d994543af4b1918318e4caa1e9c4c5e6e8d8ca8`.
The hash of the C141 report itself was not printed in the supplied log; do not confuse the prerequisite hash with that report's hash. C142 computes and records it locally.

Focused regression **108/108**. All twelve C140 seeds `20261601..20261612` were replayed; **fresh seed count = 0**. Full discrete baseline outcomes and margins matched the stored C140 report within the declared replay check. Frozen-head fingerprints, input hashes, zero-OOV checks, C37/fixture protection, tracked tree and execution HEAD all passed. `run_execution_valid = True`.

| Measurement | Result |
|---|---:|
| Baseline replay agreement | 12/12 seeds |
| Original-query correct decisions | 140/144 |
| Original failures rescued by color-only substitution | 4/4 |
| Original successes preserved | 140/140 |
| Newly introduced errors | 0 |
| Canonical-color known cases | 96/96 |
| Canonical-color unseen cases | 48/48 |
| Canonical-color total correct decisions | 144/144 |
| Positive treatment expected-class margins | 144/144 |

The four rescues correspond to `20261602: q10`, `20261604: q11`, `20261606: q11`, `20261612: q10`. No model update occurred between baseline and intervention evaluation within a seed. Reported total benchmark wall time was 77.6202966 seconds, including retraining and both evaluations; this is not an inference-latency benchmark.

**Supported claim:** on these replayed models and this finite fixture, evaluation-only replacement of the color alias by its canonical color was sufficient to rescue all observed C140 errors without introducing a new error. This meets the original C141 gate.

**Non-claims:** no original-query learned generalization improvement, no new independent seed evidence, no production fix, no proof that the heads never learned color, and no unique optimization-mechanism attribution. Canonical colors deliberately create lexical overlap with descriptors; the residual identity path may contribute to rescue. Shared pooling, color grounding, context interactions and training shortcuts are not completely separated by this result. C139/C140 remain valid negatives. Gate E remains **NOT PASSED**.

The earlier training audit still holds: eight training records have eight different shape/material pairs. That permits record selection without color, but is not direct evidence that a given head used that shortcut. Provenance authenticates a retrieved source, not relevance. Commit-once in this family remains a harness indicator, not a new crash-durability measurement.

## C142 — ACTIVE, AWAITING USER CUDA EXECUTION

Experiment: `C142-v5e-training-only-color-alignment`.
Stage: `V5-E-TRAINING-ONLY-COLOR-ALIGNMENT`.

**Scientific question:** can explicit color-alias alignment added only to the training objective make the unchanged shared head solve the original held-out alias queries across fresh paired seeds, without any inference-time oracle replacement?

### Paired arms and the changed variable

For each seed, create one initial `SharedRetrievalContentHead` and deep-copy it into two independent training arms. Assert identical initial state fingerprints. Train the Control Lane router once and reuse it, unchanged, for both arms.

- `BASELINE`: the original full-query versus eight-descriptor cross-entropy objective.
- `COLOR_AUX`: the same objective plus `1.0 * color_alignment_cross_entropy`.

The auxiliary term compares **12 distinct training color aliases against 4 canonical color words**, using the **same shared encoder and same score scale 12.0**. The first-position color correspondences are derived only from TRAIN_COMBINATION descriptors and training queries. They provide extra, explicitly structured **training supervision**. Neither validation strings, held-out combinations nor validation labels are used to construct auxiliary pairs. No additional full-combination positive or negative record is introduced into training.

Examples of auxiliary supervision: `emerald -> green`, `amber -> yellow`, with the other canonical color words as competing choices. The auxiliary coefficient is fixed at **1.0**, with no search or validation-based checkpoint selection.

At evaluation, both arms receive exactly the original C138/C139/C140 query strings, such as `emerald curved rocky` and `amber boxy timber`. No color dictionary is passed to evaluation; no query word is replaced. Query/paired-descriptor lexical overlap must remain zero. Held-out combination labels are used only to score results, not to select candidates.

### Held constant, and costs not held constant

- 49-dimensional collision-free training-vocabulary features; zero evaluation OOV.
- The unchanged `SharedRetrievalContentHead`: hidden dimension 64, residual scale 1.0, no additional parameters.
- 24 full training queries, 8 full training candidates, 12 evaluation candidates, 4 held-out combinations.
- AdamW, learning rate 0.002, weight decay 0.0, 600 optimizer steps per arm, score scale 12.0.
- Same initial parameters within each seed; independent optimizers; no checkpoint transfer between arms.
- Original descriptors, persisted C137 corpus, exact retrieval, provenance/evidence/ANSWER harness.
- Last scheduled checkpoint only, irrespective of validation results.

**Not compute-matched:** the auxiliary term adds forward/backward work and training labels, even though optimizer-step count and parameter count are equal. Training time and CUDA allocated/reserved peaks are recorded per arm, but both head copies remain resident and baseline is run first. These are diagnostic accounting numbers, not unbiased production performance comparisons.

### Seeds and size

Fresh seeds: `20261621..20261632`, twelve distinct seeds, disjoint from the C138/C139/C140 sets. C141 reused C140 seeds. These are not replay seeds.

```text
12 unique fresh seeds
2 paired training arms / seed = 24 learned heads
12 original-query cases / arm / seed
144 baseline + 144 COLOR_AUX = 288 evaluated decisions
```

The task fixture is reused after observing earlier results; this is a targeted development-set intervention, not a sealed independent task test. The 48 unseen decisions per arm repeat only four distinct held-out queries. A later independent fixture would be needed for broader claims.

### Preregistered interpretation

**PASS:** with all input/protection/provenance/paired-initialization/no-inference-oracle controls valid, the COLOR_AUX arm gets every one of its 144 original-query cases correct through retrieval/evidence/ANSWER, with a strictly positive finite expected-class margin for every case, on all 12 seeds.

This supports sufficiency of the registered supervised training intervention on the tested fixture/seeds. Compare baseline errors, rescued errors, preserved successes and new errors. If BASELINE is also perfect, mark `baseline_error_contrast_available = False`: treatment sufficiency passed, but improvement over baseline is not identified. Do not require a conveniently failing baseline or substitute seeds.

**VALID NEGATIVE / FAIL:** controls are valid but any COLOR_AUX error or nonpositive margin remains. Report partial rescue and newly introduced errors separately; no width/step/weight adjustment under the same C number. Failure of this one auxiliary objective is not proof that alignment supervision in general cannot help.

**INVALID:** prerequisite or protected hash failure, OOV/overlap/coverage failure, wrong training configuration, unequal initial weights, mutation during evaluation, nonfinite numerical results, retrieval authority failure or execution error. Resolve and retry C142, preserving invalid-run evidence.

This is **explicitly supervised attribute-alignment research**, not unsupervised discovery of semantic factors or a scalable production tokenizer proposal. No production runtime changes; no Gate E pass; do not begin C143 before C142 is judged.

### Implementation and validation

New files:

- `fold_lm/v05_benchmarks/gate_e_c142_color_alignment.py`
- `fold_lm/v05_benchmarks/gate_e_c142_cli.py`
- `tests_lm/test_v05_c142_color_alignment.py`

Reviewer validation: **22/22 new tests passed on CPU**, including the zero-auxiliary reference update, paired initialization and divergent auxiliary gradients, training-only extraction, unchanged evaluation text, prerequisite validation, adapter/provenance handling with a synthetic test adapter, and safe checkpoint reconstruction. The production head used in these local tests was verified against repository blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. New Python files compiled. No registered fresh seed was used in a reviewer benchmark. The full **130-test** focused suite (108 prior + 22 new) and full CUDA experiment are **not reviewer-executed**.

C142 requires the full accepted C141 report, validates its identity and case profile, and saves a unique run directory with both arms' cases, margins, losses, initial/final weight fingerprints, model-only checkpoints, prerequisite/input hashes, commit and environment. Checkpoints contain tensors/basic metadata and support `torch.load(..., weights_only=True)`. The final report is written atomically. `PASS` and scientific `FAIL` return CLI exit code zero; exceptions return nonzero and write `invalid.json` once the output directory is created. Protected C37 is never overwritten.
