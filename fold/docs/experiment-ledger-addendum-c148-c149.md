# FOLD experiment ledger addendum — C148 to C149

## C148 — ACCEPTED VALID NEGATIVE

Experiment `C148-v5e-train-consistent-composition`, stage V5-E. Execution commit `dd0387b9cbee8ba38142b4ad7594c277d02b8c9d`.
Evidence: user-uploaded complete terminal log `貼り付けられたテキスト（1 点）(20260915-145434).txt`, SHA256 `9f0a1039cb414554ff5110c6d2e3e7ecdc0905bd9f53b9815c49fbf9a415ccd3`. This is user execution evidence, not a reviewer rerun.
Full local report/checkpoints: `runs/c148-v5e-train-consistent-composition-fe85fcf3544e4965ace63f90cca84223/`.
**C148 report SHA256:** `4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e`.
Consumed C147 report SHA256: `c26700ba28b1616599617c73f36330dec5901c0f837744cdd86b4ea4580e632a`.
Manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.

Focused regression **236/236**. Twelve fresh paired seeds `20261681..20261692`, 24 heads, 600 updates per head. Same initial state within each pair; same auxiliary objectives; both arms evaluated ENCODE_THEN_POOL. Composition reference agreement, OOV, evaluation-weight preservation, C147/C37/fixture preservation, tracked tree and execution HEAD passed. No production change or runtime evaluation; `run_execution_valid=True`.

| Measurement | POOLED_TRAIN | COMPOSED_TRAIN |
|---|---:|---:|
| Full-catalog correct / total | 20,725 / 20,736 | 20,724 / 20,736 |
| Accuracy | 99.9469522% | 99.9421296% |
| Errors | 11 | 12 |
| Strict full-model passes | 10/12 | 10/12 |
| Original-12 strict model passes | 12/12 | 12/12 |
| Original validation in 64 candidates | 144/144 | 144/144 |
| Minimum full-catalog margin | -0.0279458463 | -0.0441289246 |
| COLOR / SHAPE / MATERIAL mismatches | 5 / 6 / 0 | 6 / 6 / 0 |

Paired: **0 rescues, 1 new error, 20,724 both correct, 11 both wrong**. All mismatches are single-factor. Seed `20261683` has 5 control errors and 6 treatment errors; seed `20261692` has 6 in each arm. Other seeds are exhaustive-perfect. The new error is COLOR. Each arm has 6 errors in PRIOR_HELDOUT_COMBINATION; NEW_COMBINATION has 5 control and 6 treatment errors. All TRAIN_COMBINATION cases pass.

### Interpretation and decision

The registered train-consistency intervention did not rescue any control error, introduced one additional error, and failed the strict sufficiency gate. There is no demonstrated accuracy benefit that justifies adopting this training-path change as the fix for C147's residuals. One extra error is not a statistically established claim that composed training is generally inferior. Equal full-model pass counts and near-ceiling accuracy do not establish equivalence either.

Training/evaluation mismatch alone is not a sufficient explanation/remedy under this registered setup. The result does not rule out every train-consistent encoder, every additive representation, or alternative training data/objectives. Exact failing texts, selected descriptors, per-arm timing and singleton training fits are not printed in this console; use the full report and checkpoints, not guesses from progress batch offsets. C147's four errors and C148's twelve errors use different seed sets; do not treat that cross-run change as a paired degradation.

The C145 helper scalar-conversion warning occurred in a passing unit test and is unrelated to the scientific verdict. It is not a reason to retry or reject C148.

**Review decision:** close this train-consistency comparison with its negative result. Keep both candidate representations as research references; do not promote COMPOSED_TRAIN, pick successful seeds, lower the C148 gate, add named attribute losses, or sweep coefficients/steps/width to erase the twelve residuals. The named attribute-loss ladder remains closed. Before another learning intervention, record what the existing score actually does. C149 is a read-only numerical accounting diagnostic, not another attempted fix. Gate E remains NOT PASSED.

## C149 — ACTIVE, awaiting user frozen-checkpoint audit

Experiment `C149-v5e-frozen-margin-accounting`, stage `V5-E-FROZEN-MARGIN-ACCOUNTING`.

**Scientific question:** how do same-factor contributions, cross-factor contributions and candidate normalization combine into the observed correct-versus-best-rival score margins of C148's frozen heads?

This is descriptive, not an intervention. **No training, new supervision, new scorer, altered predictions or model selection.** Load all 24 source checkpoints from both arms; reuse all twelve seeds. Fresh seed count is zero. The original 41,472 full-catalog rankings and 288 original-12 controls must replay against stored C148 outcomes. Discrete predictions/rivals must match, and score components must meet the existing absolute tolerance `1e-5`.

Known fixture positions are used only AFTER ranking to label a 3-by-3 dot-product matrix. Neither expected labels nor typed factor positions enter the original encoder or ranking calculation. This audit does not introduce a factor-aware production inference path or discover factor structure.

### Registered exact accounting convention

Let a_i be the query's three unit vectors, b^E_j the correct descriptor's unit vectors, and b^R_j the highest-scoring incorrect candidate's unit vectors. These are the original float32 head outputs. Each expression uses the unchanged tokenizer and shared encoder, including hyphenated expressions.

Define A=sum(a_i), B_E=sum(b^E_j), B_R=sum(b^R_j), and nQ=norm(A), nE=norm(B_E), nR=norm(B_R). Let E=A dot B_E and R=A dot B_R. The existing margin is:

```text
m = E/(nQ*nE) - R/(nQ*nR)
alpha = (1/nE + 1/nR)/2
beta  = (1/nE - 1/nR)/2
D = sum_i [a_i dot b^E_i - a_i dot b^R_i]
X = E - R - D

same_factor   = alpha * D / nQ
cross_factor  = alpha * X / nQ
candidate_norm = beta * (E + R) / nQ
m = same_factor + cross_factor + candidate_norm
```

This symmetric identity handles differing candidate norms without silently deleting or equalizing them. The split is one declared algebraic convention, not a unique causal attribution. Changing only the row ordering of the query terms can change the same/cross split while leaving the total score unchanged; a helper test explicitly verifies this limitation. Positive same-factor terms do not prove each individual alias classifier is correct. Negative cross/norm terms do not prove that removing those terms would be a safe or generalizable improvement.

All accounting is accumulated in float64 from the **same frozen float32 unit vectors**, not from a new float64 model. Every reconstructed margin must match the original float32 score margin within `1e-5`. The internal algebraic identity must agree within `1e-10`. No term is removed; no alternative predictions or rescue counts from a modified score are produced.

### Outputs and evidence controls

- Validate C148's exact full-report SHA; reaggregate stored model/group/mask/pair results through the existing C146 auditor and pair helper.
- Validate manifest bytes, generator agreement, checkpoint names/bytes/config/vocabulary/mode metadata/tensor fingerprints. Load using weights_only=True; no retraining fallback.
- Replay all 24 models and all queries, not just two failure seeds.
- Save decomposition for all 41,472 full cases, including successful cases, and detailed matrices/norms/texts for the **23 error observations** (11 control + 12 treatment). These are not 23 independent unique problems; paired observations overlap.
- Preserve exact per-case contributions, original margins, reconstruction residuals, source training singleton-fit diagnostics, hashes and environment. Aggregate positive same-factor and adverse cross/norm counts separately; those counts may overlap.
- Preserve source reports, all source checkpoints, fixture and protected C37. No model/scoring/runtime/production changes.

### Verdict and stopping boundary

**PASS — diagnostic accounting only:** every replay and identity/protection check is valid; all full-case margins reconstruct; error counts remain 11/12 and paired outcomes remain 0 rescue/1 new error; complete accounting is saved. This PASS says nothing about model improvement. **INVALID:** any prerequisite/replay/numerical/coverage/protection/execution discrepancy; repair and retry C149. There is no model-performance FAIL criterion because no model intervention is being tested. An unexpected contribution distribution is still valid evidence, not a failed execution.

After this audit, choose a separately registered learning/representation/generalization question from the measured evidence rather than starting another coefficient sweep. This does not authorize deleting cross-factor terms or normalizing candidates differently. General language relations need not decompose like these disjoint artificial attributes. No C150 is registered by this change; Gate E remains NOT PASSED.

### Implementation and reviewer verification

Files: `gate_e_c149_margin_accounting.py`, `gate_e_c149_cli.py`, `test_v05_c149_margin_accounting.py`, `tools/run_c149.ps1`, this addendum and authoritative handoff. Production sources, older experiments and other projects are unchanged.

Reviewer ran **19/19 new CPU helper tests**, using synthetic unit vectors and a toy checkpoint class. Tests cover the exact identity, diagonal/cross/norm partition, permutation/convention sensitivity, unchanged inputs, finite-value/normalization guards, summary accounting, rejection of incomplete prerequisites, and checkpoint identity/freeze checks. New Python modules compile. These are not a real C148-checkpoint or full-prerequisite integration run. Full **255-test** focused suite, formal CUDA replay and PowerShell are not reviewer-executed. No source model performance was inspected beyond the supplied log.
