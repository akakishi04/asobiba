# FOLD experiment ledger addendum — C147 to C148

## C147 — ACCEPTED VALID NEGATIVE

Experiment `C147-v5e-frozen-composition-order`, stage V5-E. Execution commit `beae04e34ec9298453953f6535de0328ead6be87`.
Evidence: the user's uploaded complete terminal log `貼り付けられたテキスト（1 点）(20260915-141837).txt`, SHA256 `e28a29b97fe1cf1e53ddbffbd0b077ca8442b9daa80235d23c183f652cb11b2a`. This is user execution evidence, not a reviewer rerun.
Full local report: `runs/c147-v5e-composition-order-3df2d310b2354400a4e2de697ac1c83e/summary.json`.
**C147 report SHA256:** `c26700ba28b1616599617c73f36330dec5901c0f837744cdd86b4ea4580e632a`.
Consumed C146 report SHA256: `693fadc5b4e76ab253d8395f9197b653ff2d6253435830a9165925948d99622b`.
Manifest SHA256 remains `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.

Focused regression **212/212**. All twelve C146 ALL_FACTOR_AUX checkpoints were used, with **zero fresh seeds and zero additional training steps**. Original full rankings and original-12 controls replayed at rate 1.0. Frozen weights, checkpoint/input/manifest/protected hashes, tracked tree and execution HEAD passed. Both modes are ranking-only: no persisted retrieval, provenance validation, commit or ANSWER was executed. `run_execution_valid=True`.

| Metric | POOL_THEN_ENCODE | ENCODE_THEN_POOL |
|---|---:|---:|
| Correct / full rankings | 20,725 / 20,736 | 20,732 / 20,736 |
| Accuracy | 99.9469522% | 99.9807099% |
| Errors | 11 | 4 |
| Strict full-model passes | 8/12 | 11/12 |
| Original-12 strict model passes | 12/12 | 12/12 |
| NEW_COMBINATION correct | 16,839 / 16,848 | 16,848 / 16,848 |
| PRIOR_HELDOUT_COMBINATION correct | 1,294 / 1,296 | 1,292 / 1,296 |
| Minimum full-catalog margin | -0.0178287327 | -0.0045864284 |

Paired: **10 rescued, 3 new errors, 20,722 both correct, 1 both wrong**. Net error-count reduction is seven, not ten. The three regressions must not be hidden by the perfect NEW_COMBINATION bucket. The four alternative-rule failures are all COLOR mismatches, all in model seed `20261666`, all in PRIOR_HELDOUT_COMBINATION. Exact texts for the three new errors are absent from the console; they remain in the full report's `changed_or_wrong_cases`. Do not invent them.

The original remaining error shown in the console is `vermillion three-sided transparent`, expected `red triangular glass`, selected `yellow triangular glass`; its margin improves from -0.0178287327 to -0.0045864284 without changing correctness. A rescued example `ruby three-sided transparent` has only +0.0003759861 alternative margin. This is a score difference, not a calibrated probability or a robustness certificate.

Source training singleton alignment accuracy is **1.0 for all three axes in all twelve models**. This is accuracy against each axis's four canonical candidates on its training aliases, not exact equality of alias/canonical vectors, separation from all other concepts, or guaranteed contextual composition. Even individually correct relations can interact differently when vectors are summed and normalized. The numerical contributions of those interactions have not been measured by C147.

**Supported:** the registered inference-only composition intervention improves aggregate ranking on these fixed supervised models/fixture, removes ten of eleven old errors, but is not a sufficient non-regressing solution. The original all-case positive-margin gate fails. Eleven perfect models do not justify dropping the twelfth.

**Non-claims:** unique causality from mixing order alone (normalization/equal-unit weighting also changed); automatic factor discovery; fresh-task/seed robustness; speedup from the 2.1973427-second diagnostic wall time; production readiness. Original C146 remains negative. Gate E stays NOT PASSED.

## C148 — ACTIVE, awaiting user CUDA execution

Experiment `C148-v5e-train-consistent-composition`, stage `V5-E-TRAIN-CONSISTENT-COMPOSITION`.

**Scientific question:** keeping the encode-then-pool evaluation rule fixed, is using that same rule in the main training objective sufficient for exhaustive positive-margin ranking on fresh paired seeds?

C147 changed only inference on heads trained with pooled full-query representations. It therefore did **not** test training a composition-consistent model. C148 isolates that remaining training-path choice; it does not assume it caused the four residuals.

### Paired arms

```text
POOLED_TRAIN (control):
  main-task training = POOL_THEN_ENCODE
  evaluation         = ENCODE_THEN_POOL

COMPOSED_TRAIN (treatment):
  main-task training = ENCODE_THEN_POOL
  evaluation         = ENCODE_THEN_POOL

Both objectives:
  main retrieval CE + 1.0*color CE + 1.0*material CE + 1.0*shape CE
```

Only the full-query/full-descriptor representation inside the **main training loss** differs. Auxiliary labels, candidate sets, coefficients and their direct shared-encoder computation are unchanged. This is not adding another attribute loss, and not removing the existing explicit three-factor supervision. Training/evaluation composition consistency is a hypothesis; FAIL does not disprove all additive encoders.

The differentiable computation is the exact mathematical C147 rule: each sorted whitespace unit is encoded by the same shared head; its unit-normalized vectors are summed with multiplicity and the sum is normalized. Hyphenated expressions remain intact before the existing feature function. No typed slots, alias dictionary, expected labels, or position-dependent factor matching enter the encoder. Whitespace happens to delimit the fixture's factors; this remains structural bias, not learned segmentation.

The C147 helper deliberately uses inference_mode and cannot be used for training. C148 adds a gradient-enabled diagnostic helper and compares its evaluation embeddings against C147's reference at absolute tolerance 1e-6. It caches only immutable input features/indexing, not detached learned vectors between optimizer steps. The gradient path is tested with float64 finite differences.

### Fixed conditions and sizes

Fresh paired seeds **20261681..20261692**, twelve distinct initializations; both arms start from identical copied weights and independent optimizers. No C146/C147 checkpoint is continued, loaded or selected for C148 training.

- Same head: feature dimension 49, hidden dimension 64, residual scale 1.0; no added parameters.
- Same 24 main training queries and 8 main candidates; same 12 aliases versus 4 canonical candidates per auxiliary factor, extracted solely from TRAIN_COMBINATION fields via C146's existing helper.
- AdamW learning rate 0.002, weight decay 0, 600 steps, logit scale 12.0; no tuning or validation-based checkpoint selection.
- Same raw queries, 64 candidates and 1,728-query C143 manifest, checked against its accepted byte hash.
- Both arms evaluate ENCODE_THEN_POOL: 20,736 full rankings plus 144 original-12 rankings per arm; 41,760 total decisions.
- No inference oracle or production changes. All evaluation remains ranking-only, including original12. No retrieval/ANSWER claim.

Equal steps and parameter count do not imply equal training computation. Per-arm training wall time and CUDA peak allocation/reservation are recorded, but both models remain resident and arm order is fixed; these are diagnostic cost accounts, not unbiased production benchmarks.

### Preregistered verdict

**PASS:** every COMPOSED_TRAIN full-catalog ranking and original-12 control is correct with a strictly positive finite margin on all twelve seeds, with all execution controls valid. Compare paired rescues and regressions. If control is also perfect, sufficiency is demonstrated on the tested conditions but superiority is not identified; do not replace seeds to force a contrast.

**VALID NEGATIVE / FAIL:** valid execution but any treatment error/nonpositive margin or original-12 failure. Report partial improvement or degradation, group metrics, all mismatch masks, margins, singleton training diagnostics and paired counts. Do not silently use a pooled evaluator for one arm to change the question.

**INVALID:** wrong/missing full C147 report, hash/prerequisite reaggregation failure, different manifest/OOV/configuration, unequal initial weights, nonfinite computation, disagreement with composition reference, input/weight mutation, or execution error. Resolve and retry C148 without altering its scientific conditions.

### Exit and production relevance

C148 tests whether a deployable inference computation can also be used as the training computation, not whether another post-hoc fixture-specific adjustment can erase four known errors. It is still only an empirical synthetic reference. The named attribute-loss ladder remains closed. No coefficient/width/step sweep and no discarding failure seeds is authorized. After this single consistency comparison, review the representation/training candidates before any separately registered less-supervised, independently partitioned, natural-language or runtime-integration experiment. The frozen artificial suite is a development set, not an untouched benchmark. No C149 is registered by this change; Gate E is NOT PASSED.

### Implementation and reviewer verification

New benchmark, CLI, test and PowerShell files plus this addendum; authoritative handoff updated. Production head, old experiments, root README and branch history are unchanged.
Reviewer ran **24/24 new CPU tests** using toy weights/features and full-size synthetic prerequisite records with an injected toy auditor. Coverage includes differentiable composition, finite-difference gradients, no stale vector cache, exact pooled-control update arithmetic, identical auxiliary terms, pairing, strict margins, safe checkpoint metadata, and prerequisite glue. The synthetic glue tests do not constitute integration with the real C147 report/C146 auditor. Local production-head bytes match Git blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. New Python files compile. Full **236-test** suite, real-prerequisite integration, CUDA experiment and PowerShell are not reviewer-executed. No registered fresh-seed performance was inspected.

C148 requires C147's exact accepted report SHA, reaggregates its full records via existing C146/C147 auditors, and preserves the prior and protected inputs. It saves original/full predictions, group metrics, losses, fingerprints, model-only checkpoints with training/inference composition metadata, input/manifest hashes and environment. The report is atomically published; scientific FAIL returns exit code zero, execution exceptions return nonzero with an invalid marker once the output directory exists.
