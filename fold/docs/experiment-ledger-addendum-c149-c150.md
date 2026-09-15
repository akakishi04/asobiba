# FOLD experiment ledger addendum — C149 to C150

## C149 — ACCEPTED PASS (numerical accounting only)

Stage V5-E. Experiment `C149-v5e-frozen-margin-accounting` executed at `f02b3612183753973c1282924216f9703b49dbbe`.
Evidence: user-supplied complete log `貼り付けられたテキスト（1 点）(20260915-153020).txt`, SHA256 `fc9f840ce5bf9044d4983c0f3619a0b400810aad1d9b8836810ecfa4b8008987`. Reviewed 2026-09-16 (JST). No reviewer rerun of the actual models is claimed.
Full C149 report: `runs/c149-v5e-margin-accounting-44e251b5b99849c099196b996b617d94/summary.json`.
**C149 report SHA256:** `d2fdfab39fdc09f250ed5c9cdbdae159b148c3d06bd023288961993913a54250`.
Source C148 report: `runs/c148-v5e-train-consistent-composition-fe85fcf3544e4965ace63f90cca84223/summary.json`, SHA256 `4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e`.
Evaluation manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.

Focused regression **255/255**. All 24 source heads, both arms and all twelve source seeds were included. 41,472 full rankings and 288 original-12 controls replayed. All-case accounting completed, frozen weights and input/checkpoint identities held, and C37/fixture/source reports/manifest/tracked tree/HEAD postchecks passed. `run_execution_valid=True`. No training, fresh seeds, scorer change or runtime path.

| Error-only mean contribution | POOLED_TRAIN (11 errors) | COMPOSED_TRAIN (12 errors) |
|---|---:|---:|
| Same factor | +0.3146923217 | +0.3190750911 |
| Cross factor | -0.4162158787 | -0.4284724834 |
| Candidate norm | +0.0892313441 | +0.0878052995 |
| Sum | -0.0122922129 | -0.0215920927 |
| Maximum reconstruction error, all cases | 2.3360549542e-7 | 2.0823931440e-7 |

The reconstruction tolerance was 1e-5. Every error has a positive same-factor term, negative cross-factor term, and positive candidate-normalization term. This is a per-error fact, not just an average. Under the registered symmetric accounting convention, cross-factor contributions outweigh the two helpful contributions. Normalization is helping, not harming, those specific expected-versus-rival comparisons. It is not justified to label normalization the cause or remove it based on this result.

All 23 error observations cover **12 distinct query strings** and two expected/selected descriptor pairs: seed 20261683 confuses `red hexagonal stone` with `yellow hexagonal stone`; seed 20261692 confuses `blue hexagonal metal` with `blue round metal`. Eleven strings fail in both training arms and one additional string, `ruby hexagon rocky`, fails only in COMPOSED_TRAIN. These are not 23 independent tasks.

Example (POOLED_TRAIN, seed 20261683): `crimson hexagon rocky` has same +0.2896540874, cross -0.4081352313, norm +0.1022144483; sum is approximately the reported margin -0.0162667334. C149 does not alter its wrong selection.

**Claim:** complete, reproducible arithmetic accounting of existing scores; the sign reversal is localized to the cross-factor contribution in the declared decomposition. **Non-claims:** a unique causal explanation of training, safe deletion of cross terms, orthogonality as a general-language requirement, model improvement, independent-task generalization or Gate E success. Error-only averages do not describe the contribution distribution of correct cases. C148 singleton-fit values are stored in full records but not printed in the supplied C149 console; do not infer their exact values from C147's different models.

C148 remains ACCEPTED VALID NEGATIVE. Source errors remain 11/12 and source pairing remains 0 rescues/1 new error. Gate E remains **NOT PASSED**.

## Review decision

The inference scorer is not changed. In particular, no ground-truth factor-position mask, cross-term deletion, normalization sweep or larger model is introduced. The previous named-attribute-loss ladder and train-composition comparison stay closed.

Code inspection gives a separate, testable training hypothesis: each existing auxiliary loss only compares an alias with its own factor's four canonical words. Cross-factor canonical concepts do not compete inside that auxiliary CE. Full-query main loss can still create cross-factor gradients, so it would be incorrect to say there was no cross-factor learning at all.

Select one new comparison: expand the auxiliary competing-candidate pool, using the same positive pairs. This is a **negative-candidate construction intervention**, not another attribute, coefficient search or an inferred proven remedy. It can fail. No term is removed from the inference score.

## C150 — ACTIVE, awaiting user CUDA execution

Experiment `C150-v5e-global-auxiliary-negatives`, stage `V5-E-GLOBAL-AUXILIARY-NEGATIVES`.
**Scientific question:** with main training and inference fixed, is expanding auxiliary competitors from four within-factor concepts to all twelve existing canonical concepts sufficient for exhaustive positive-margin ranking across fresh paired seeds?

```text
WITHIN_FACTOR (control):
  each of the three auxiliary alias tasks compares against 4 same-factor canonical words
GLOBAL_CONCEPT (treatment):
  the SAME alias queries and SAME positive target words compare against all 12 canonical words

Both: pooled main-query training, encode-then-pool evaluation
Both: main CE + 1.0*color CE + 1.0*material CE + 1.0*shape CE
```

Only auxiliary candidate scope changes. Each group retains its twelve positive alias queries. CE reduction is a **sum of three twelve-alias means**, not a single 36-alias mean (which would silently divide auxiliary weight by three). Group order remains color, material, shape. Positive pairs remain **36**; each alias now has **11 negatives instead of 3**. Thus eight extra exclusion comparisons are added per alias. No new positive labels or full-combination examples are added, but supervision is NOT unchanged: extra negative constraints are the treatment.

Canonical candidates and positive labels are extracted exclusively from TRAIN_COMBINATION fields using C146's existing helper. Candidate expansion consumes only these extracted specifications, not validation text/labels. Labels are remapped by canonical identity, never by evaluation address. Cross-factor duplicate names, ambiguous aliases and lexical overlap are rejected. The closed artificial vocabulary makes these exclusion labels meaningful here; blindly treating unrelated-looking natural-language expressions as exclusive negatives is not justified by this experiment.

### Fixed conditions and accounting

- Fresh seeds **20261701..20261712**, twelve unique paired initializations. No source checkpoint continuation or failure-seed selection.
- Same `SharedRetrievalContentHead`, feature dimension 49, hidden dimension 64, residual scale 1.0; same parameter count.
- Same 24 main queries and eight main candidates. Both use POOL_THEN_ENCODE in the main loss, retaining C148's POOLED_TRAIN reference; train consistency was not demonstrated as a fix.
- Same AdamW lr 0.002, weight decay 0, 600 updates, logit scale 12.0, auxiliary coefficients all 1.0; last checkpoint only, no tuning or early stopping based on evaluation.
- Same raw query strings, ENCODE_THEN_POOL evaluation, zero OOV, original C143 manifest and 64 candidates. Both evaluators are checked against the existing C147 composition reference at atol 1e-6.
- 24 learned heads, 20,736 full rankings and 144 original-12 rankings per arm, **41,760 total query decisions**. All ranking-only. No persisted retrieval/provenance/commit/ANSWER path or production change.
- Costs are not matched: larger auxiliary denominators add candidate comparisons and gradients. Record training times and CUDA peak allocated/reserved memory, with both heads resident and fixed arm order; not a production performance benchmark.
- Both within-factor and global-concept singleton fits are recorded for each arm using their respective candidate sets. They are training-fit diagnostics, not unseen-task evidence.

### Preregistered interpretation and boundary

**PASS:** every GLOBAL_CONCEPT full ranking and original-12 control is correct with a strictly positive finite expected-class margin on all twelve seeds, and all execution controls pass. Compare paired rescues, new errors and factor masks. If WITHIN_FACTOR is also perfect, sufficiency is observed but superiority is not established; do not replace seeds to force a contrast.

**VALID NEGATIVE / FAIL:** valid execution but any treatment error/nonpositive margin or original-12 failure remains. Report partial gains and regressions without altering the criterion. This rejects sufficiency of this registered negative-pool change, not all globally contrastive training.

**INVALID:** prior/hash/reaggregation/manifest/configuration/OOV/initialization/numerical/reference/immutability/execution discrepancy. Repair and retry C150 without altering scientific conditions.

PASS does not prove orthogonal factors, removal of all cross-factor interference, automatic discovery, open-domain generalization or production readiness. The same development fixture has informed the change; new seeds are not new tasks. This is one bounded comparison of negative-candidate scope, not authorization for temperature/width/steps/negative-sampling sweeps. After judgment, review a separately specified independent task split or acquisition/runtime boundary instead of automatically extending this fixture-optimization series. No C151 is registered here. Gate E remains NOT PASSED.

### Implementation and reviewer verification

New benchmark, CLI, helper tests and PowerShell runner plus this addendum and handoff. Production source, prior experiments, root README and existing history are untouched.
Reviewer CPU: **20/20 new tests passed**, using toy training inputs and synthetic full-sized prerequisite accounting. Tests verify candidate/positive identity, global label remapping, sum-of-means weight preservation, exact explicit control update arithmetic, pairing, validation failures and safe checkpoint metadata. The locally tested production-head bytes match Git blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. Python compilation passed. Full **275-test** suite, real C149/C148 full-record integration, formal CUDA training and PowerShell are not reviewer-executed. No official fresh-seed performance has been inspected.
C150 requires exact C149 and C148 full-report hashes, revalidates the C148 records with the existing auditor and reaggregates C149 accounting against them. Source checkpoints are not loaded or modified. The run preserves source/protected files and stores its own manifest, alignment specification, both arms' full/old-12 rankings, margins, fits/losses/costs, fingerprints and scope-tagged checkpoints. Reports publish atomically. Scientific FAIL returns zero; execution exceptions return nonzero and leave an invalid marker when the output directory exists.
