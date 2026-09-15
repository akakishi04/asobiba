# FOLD experiment ledger addendum — C146 to C147

## C146 — ACCEPTED VALID NEGATIVE

Experiment: `C146-v5e-all-factor-supervised-reference`, stage V5-E.
Execution commit: `6582dac69fc6bab93cd8cdbc08ceef13d0542ba7`.
Evidence: the user's complete uploaded terminal log `貼り付けられたテキスト（1 点）(20260915-133939).txt`, SHA256 `946d7efeb4b34f490e9d9fc7d3c38dd68db18e33a1f0205b49b1f3e5dead49bc`. This is user execution evidence, not an independent reviewer CUDA rerun.
Local full report and 24 checkpoints: `runs/c146-v5e-all-factor-reference-9a40582d7ebb436e9debde9581131734/`.
Consumed C145 report SHA256: `c3c21bcb5687451ae6a1d4260e410dce7d47732c58bdf278dee8ac86ff670683`. C146's own report hash was not printed; do not substitute the prerequisite hash.

Focused regression **194/194**. Twelve fresh paired seeds `20261661..20261672`. Identical initial weights within each pair; 600 updates; no inference oracle or production change. Full and original-12 evaluations were ranking-only. Reported prerequisite, manifest, zero-OOV, lexical-overlap, frozen-evaluation, C37/fixture preservation, tracked-tree and execution-HEAD controls all passed. `run_execution_valid=True`.

| Metric | COLOR_MATERIAL_AUX | ALL_FACTOR_AUX |
|---|---:|---:|
| Full-catalog correct / total | 20,260 / 20,736 | 20,725 / 20,736 |
| Accuracy | 97.7044753% | 99.9469522% |
| Errors | 476 | 11 |
| Strict full-catalog model passes | 0/12 | 8/12 |
| Original-12 strict model passes | 12/12 | 12/12 |
| Original validation within 64 candidates | 140/144 | 144/144 |
| Minimum full-catalog expected margin | -0.1425258517 | -0.0178287327 |

Paired: 469 rescues, 4 new errors, 20,256 both correct, 7 both wrong. Net error reduction is `(476-11)/476 = 97.6891%`, distinct from the rescue count. Treatment is better in total accuracy for all twelve paired models, but the original all-model/all-case positive-margin gate failed.

Residuals are single-factor only: COLOR 5, MATERIAL 5, SHAPE 1. Four models contain errors: seed `20261664` has 2, `20261665` has 1, `20261666` has 7, and `20261671` has 1. The other eight are exhaustive-perfect on this fixed suite. New errors comprise COLOR 2 and MATERIAL 2. Nine residual cases are in NEW_COMBINATION and two in PRIOR_HELDOUT_COMBINATION; the training-combination group remains perfect.

### Interpretation and boundary

Adding the registered shape term to the color+material objective produced a large paired improvement, but did not guarantee perfect composition on the entire fixed catalog. This is a strong, explicitly supervised empirical reference, not an accepted perfect-capability result or a theoretical upper bound. C142's scoped PASS and C143/C145 negatives remain unchanged. Gate E remains NOT PASSED.

The eight successful models refute structural impossibility on this finite task. The eleven residuals do not prove that manual factor supervision cannot scale, that a larger head is necessary, that the current pooling is uniquely causal, or that automatic factor discovery has been demonstrated. The uploaded console does not contain the eleven exact query/selected-record pairs or per-model singleton alignment accuracies; those remain in the full C146 report. Do not invent those details from progress batch positions.

The existing C145 helper warning about converting a requires-grad scalar occurred during a passing unit test; the full run completed. It is not the basis for the scientific negative.

**The named color/material/shape auxiliary-loss ladder is now closed.** Do not add a fourth named attribute, pick only the eight successful models, lower C146's gate, or sweep coefficient/steps/width to erase these eleven cases. A separate composition-rule diagnostic follows; it is not extra training under C146.

## C147 — ACTIVE, awaiting user CUDA evaluation

Experiment: `C147-v5e-frozen-composition-order`.
Stage: `V5-E-FROZEN-COMPOSITION-ORDER`.

**Scientific question:** for the fixed C146 ALL_FACTOR_AUX heads, is independently encoding each whitespace-delimited expression and then summing sufficient to remove the residual ranking errors without losing original correct results?

Use all twelve ALL_FACTOR_AUX checkpoints, not just failures or successes. C146's COLOR_MATERIAL_AUX records are revalidated as prerequisite evidence but their checkpoints are not evaluated in C147. No checkpoint is trained again. Fresh seeds = 0; optimization steps = 0.

### Registered composition rules

Let `B(text)` be the unchanged C139 collision-free normalized bag feature function, `h(x)` the unchanged stored head's unit-normalized encoder, and `N(x)` unit normalization.

```text
POOL_THEN_ENCODE(text) = h(B(text))

ENCODE_THEN_POOL(text) = N(sum(h(B(unit)) for unit in split_whitespace(text)))
```

Both query and candidate descriptor use the selected rule; final scoring remains their dot product. Unit order is sorted to remove permutation-dependent summation roundoff; repetitions retain multiplicity. Each unit is processed by the same head with no typed color/shape/material slots. No query word is replaced, no alias-to-canonical dictionary is consulted, and expected labels are used only after candidate scores have been computed.

`four-sided`, `six-sided`, etc. stay intact as whitespace units passed to the old feature function; its internal tokenizer still splits them as before. The alternative normalizes individual unit encodings before summation, therefore giving equal contribution norms to units. This changes normalization/weighting and nonlinear mixing order as one declared composition-rule intervention; it is **not** a pure isolated nonlinear-layer ablation.

Whitespace boundaries conveniently align with factor expressions in this synthetic fixture. That is retained structural bias, not discovered factorization or a general-language tokenizer solution. C146's explicit training supervision is retained. A successful diagnostic is not a method that learned composition without supervision.

### Fixed conditions, sizes and controls

- Same twelve model seeds `20261661..20261672`, same stored weights, feature vocabulary, parameter count and raw text.
- Same manifest: 64 candidates, 1,728 query strings per model, SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
- 20,736 original pooled rankings replayed and checked against C146; 20,736 new composition-rule rankings.
- Original-12 control: 144 replayed and 144 alternative rankings. Total 41,760 evaluated query decisions including these controls.
- Replay verifies discrete predictions, best rivals and all stored score/margin components within absolute tolerance `1e-5`. Any discrepancy is INVALID.
- Original C146 full records are reaggregated through its existing auditor before scoring. Checkpoint bytes, vocabulary/configuration and tensor fingerprints are validated. Weights and inputs remain unchanged.
- The encoder can cache unique unit vectors within each model evaluation. Cache size/encoded-unit counts are accounted for, not presented as an unbiased production latency benchmark.
- All evaluation is ranking-only. No persisted retrieval/provenance/commit/ANSWER or runtime promotion.

### Preregistered interpretation

**PASS:** baseline replay and all execution controls are valid; ENCODE_THEN_POOL gets all 20,736 full rankings correct with strictly positive finite expected-class margins; all 144 original-12 rankings also pass. This necessarily rescues all 11 residuals and preserves all 20,725 baseline successes. It supports sufficiency of this registered alternative computation for these frozen models/fixture, not unique causal attribution or production readiness.

**VALID NEGATIVE / FAIL:** valid replay but any alternative ranking error/nonpositive margin or original-12 failure remains. Report partial rescue, newly introduced errors and factor masks; do not tune pooling weights or try a sequence of alternative normalizations under the same number. Failure rejects the sufficiency of this specific rule, not all additive representations.

**INVALID:** wrong/incomplete prerequisite, checkpoint/manifest/protected hash or vocabulary mismatch, replay disagreement, nonfinite/undefined normalization, model/input mutation, or execution error. Resolve and retry C147; no retraining fallback and no silently accepting changed source models.

Save both modes' complete rankings, group metrics, paired transitions, the original eleven query/expected/predicted/margin comparisons, all new errors, and C146's stored singleton alignment diagnostics. The latter are source training-fit diagnostics, not a new generalization measurement.

**Transition boundary:** this is one composition diagnostic, not a new attribute-loss ladder. Its outcome informs a separately registered choice between a train-consistent composition architecture, less hand-labeled alignment supervision, and broader task/runtime integration. None of those is implemented by C147. Do not register C148 before C147 judgment. Gate E remains NOT PASSED.

### Implementation and reviewer verification

New files: `gate_e_c147_composition_order.py`, `gate_e_c147_cli.py`, `test_v05_c147_composition_order.py`, `tools/run_c147.ps1`, this addendum; authoritative handoff updated. Earlier experiments, production head, README, other projects and branch history are unchanged.

Reviewer CPU helper tests: **18/18 passed**, using toy weights and toy text features. Coverage includes exact composition arithmetic, single-unit equivalence, permutation invariance, repeated/hyphenated expressions, no encoder label interface, label-independent predictions, replay checks, strict margins, rescue/regression accounting and frozen checkpoint reconstruction/tamper rejection. Local production-head source matches Git blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. New Python files compile. The full **212-test** suite, full accepted-C146-record integration, CUDA benchmark and PowerShell are **not reviewer-executed**; no user checkpoint or official C147 result was evaluated here.
