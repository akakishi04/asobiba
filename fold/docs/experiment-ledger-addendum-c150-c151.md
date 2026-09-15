# FOLD experiment ledger addendum — C150 to C151

## C150 — ACCEPTED PASS (registered synthetic ranking scope)

Experiment `C150-v5e-global-auxiliary-negatives`, stage V5-E. Execution commit `1e9cfdbaf3631dbb207d2177f6ff6291673ec286`.
Evidence: user's complete terminal log `貼り付けられたテキスト（1 点）(20260915-160711).txt`, SHA256 `1c1c4427fcef6f356d7af9596d07d5e35ea1b5ed66f8c164c568e6502563dbd7`. Reviewed 2026-09-16 JST; not a reviewer CUDA rerun.
Full report: `runs/c150-v5e-global-negatives-073fe58a1c744fd28eebb9b8d225c7f9/summary.json`.
**C150 report SHA256:** `7e87a93e60ad334a9077fa132a0dc73da07a3da159c6f572d81190b66c8b95e7`.

Focused regression **275/275**. Twelve fresh paired seeds `20261701..20261712`; 24 heads; 600 updates. Same initial weights, declared composition-reference agreement, zero OOV, unchanged evaluation weights, protected C37/fixture/C148/C149/manifest, tracked tree and execution HEAD all passed. `run_execution_valid=True`. Runtime path and production changes remain false.

| Measurement | WITHIN_FACTOR | GLOBAL_CONCEPT |
|---|---:|---:|
| Correct / full ranking cases | 20,735 / 20,736 | 20,736 / 20,736 |
| Accuracy | 99.99517747% | 100% |
| Errors | 1 | 0 |
| Strict exhaustive model passes | 11/12 | 12/12 |
| Original12 strict model passes | 12/12 | 12/12 |
| Minimum full-catalog margin | -0.00006809830666 | +0.14257526397705 |
| NEW_COMBINATION correct | 16,848 / 16,848 | 16,848 / 16,848 |
| NEW_COMBINATION minimum margin | +0.00724089145660 | +0.14257526397705 |

Paired: **1 rescue, 0 new errors, 20,735 both correct, 0 both wrong**. The only control error is seed `20261712`, bucket PRIOR_HELDOUT_COMBINATION, mask SHAPE+MATERIAL. Exact query/selected descriptor are omitted from the supplied console; do not infer them from progress offsets. All GLOBAL_CONCEPT errors/mismatch masks are zero.

C150 meets its original sufficiency gate without moving thresholds. The paired accuracy advantage is **one decision**, not a large demonstrated general accuracy gain. The observed worst-case score gap is larger with GLOBAL_CONCEPT, but is not calibrated confidence, adversarial robustness, or proof that every individual margin improved. Per-model costs/fits are in the local full report, not the printed aggregates; do not invent them. A larger loss with twelve candidates is not directly comparable to four-candidate CE as if the tasks were identical.

C149 motivates the candidate-scope hypothesis but C150 does not remeasure its decomposition, prove cross terms vanish, establish orthogonality, or identify a unique learning mechanism. Its seed set differs from C148; do not claim it rescued C148's 11/12 errors. Earlier negatives stay accepted. Gate E remains **NOT PASSED**; every measurement here is ranking-only.

## Review decision

Close optimization of the original eight-combination development split. Retain GLOBAL_CONCEPT as a **task-scoped research candidate**, with WITHIN_FACTOR as the control, not a production promotion. No coefficient/temperature/width/step sweep or favorable-seed selection follows this PASS.

The next bounded question is split sensitivity, not another model improvement: keep the complete C150 recipes fixed and change which eight combinations provide main-task training. This is an intermediate generalization check **within the same artificial lexicon and task**, not an independent natural-language task, unseen-word evaluation or automatic factor discovery. This distinction is intentional; calling new splits independent semantic benchmarks would overstate the evidence.

## C151 — ACTIVE, awaiting user CUDA execution

Experiment `C151-v5e-cross-split-replication`, stage `V5-E-CROSS-SPLIT-REPLICATION`.
**Question:** does the fixed GLOBAL_CONCEPT recipe satisfy the exhaustive positive-margin gate across four preregistered replacement main-training splits, and how does the fixed WITHIN_FACTOR control behave on the same paired initializations?

Each replacement split contains eight unique triples, with each value occurring twice in each axis. Its training triples exclude the original eight and are disjoint from the other three replacement splits. Splits use a data-only SHA256 column-order generator, taking the first structurally admissible set (attempt numbers 5, 0, 42, 344); no performance-based generation or outcome-dependent rejection. The source TRAIN rows alone supply the original ordered three-alias schedule for each value. The 24 new main-query strings use that unchanged schedule, not a new query-template policy.

**Pinned split-plan SHA256:** `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.
The generator and all four concrete plans are fixed before any C151 model performance is inspected. `split-plan.json` is written and checked before training starts. Its original training list, generated positives, seed mapping and marginal counts remain in the run.

| Split | Fresh seeds | Main combinations / queries | Held-out combinations |
|---|---|---|---:|
| S1 | 20261721..20261723 | 8 / 24 | 56 |
| S2 | 20261724..20261726 | 8 / 24 | 56 |
| S3 | 20261727..20261729 | 8 / 24 | 56 |
| S4 | 20261730..20261732 | 8 / 24 | 56 |

All 36 auxiliary positive pairs and their within-four/global-twelve candidates are identical to C150 and verified from the new TRAIN rows. Same 49-dimensional vocabulary, head hidden64/residual1, AdamW lr .002/weight_decay0, 600 updates, scale12, sum of three auxiliary means. Main training remains POOL_THEN_ENCODE and evaluation ENCODE_THEN_POOL. Training calls the existing C150 function; no new training rule is implemented. Identical initial parameters within each pair; separate optimizers; no checkpoint continuation. Timing/VRAM retains fixed arm order and both heads resident, so not an unbiased production comparison.

Same frozen C143 catalog and raw query strings: 64 candidates and 1,728 rankings/head, with **CURRENT_TRAIN_COMBINATION** (216/head) and **HELDOUT_COMBINATION** (1,512/head) defined anew for each split. Legacy C143 TRAIN/heldout bucket names are not reused for current-split metrics. The original12 ranking check is retained as a legacy control, not necessarily a held-out set under each replacement split. Across 24 heads: **41,472 full rankings + 288 original12 rankings**. The evaluation task/vocabulary is unchanged; initializations are nested within splits, not twelve independent tasks.

### Gate and limitations

**PASS:** all GLOBAL_CONCEPT full and original12 rankings are correct with strictly positive finite margins, across all four splits and all twelve initializations, and all execution guards pass. Publish per-split metrics, paired rescues/regressions and control performance even if both conditions are perfect. No superiority claim when the control provides no error contrast.

**VALID NEGATIVE / FAIL:** valid execution but any treatment error/nonpositive margin remains. Report which splits fail; do not alter split lists, seed sets or the frozen recipe under C151. This limits cross-split sufficiency, not the validity of C150's scoped PASS.

**INVALID:** prerequisite/hash/reaggregation/manifest/split-plan/vocabulary/positive-pair/init/numeric/reference/mutation/execution failure; repair and retry C151 without changing its scientific conditions.

No runtime retrieval/provenance/commit/ANSWER evaluation, no production mutation, no Gate E promotion. No new attribute loss, inference dictionary, expected-label routing or typed-factor scorer. After C151, review independent task-family evaluation or acquisition/runtime integration; do not automatically tune these new splits to 100%. No C152 registered.

### Reviewer verification

**23/23 new CPU helper tests passed**: data-only plan determinism/pinned hash, source immutability, validation exclusion, disjoint/balanced splits, original alias schedule, all 36 pairs, new grouping semantics, strict gate, early prerequisite rejection, and toy checkpoint serialization. Python compilation passed. These helper tests do not exercise the full C150 prerequisite reaggregator or actual training/scoring integration. Full **298-test** focused suite (275+23), real full-report integration, CUDA and PowerShell were **not reviewer-executed**. No C151 registered seed was trained or scored by the reviewer.
