# FOLD experiment ledger addendum — C145 to C146

## C145 — ACCEPTED VALID NEGATIVE

Experiment `C145-v5e-material-alignment-intervention`, execution commit `b7d82dad56fb03cd270a62a7e8d01fc014025197`, stage V5-E.
Evidence: the user's complete uploaded terminal log `貼り付けられたテキスト（1 点）(20260915-085356).txt`, SHA256 `a16f1ba0dae1e639067a19b281f54844711924ac110f4e64326e2a91d659a785`. This is not a reviewer rerun.
Full local result: `runs/c145-v5e-material-alignment-60955308e1004127836054c3d8b024dc/summary.json`.
Consumed C144 result SHA256: `c56823a036f22eae47da953d5ccdd0888eb7697ba9efb8ae41f8114a4ab0fe43`. The C145 result's own SHA is not printed in the log; C146 computes it locally. Do not confuse the prerequisite hash with the report hash.

Focused regression **174/174** passed. Twelve fresh paired seeds `20261641..20261652`, 24 heads, identical initial parameters within each pair. No inference oracle, production change or runtime retrieval/ANSWER evaluation. C37, fixture and C144 input were preserved; tracked tree and execution HEAD remained clean/unchanged. `run_execution_valid=True`.

The `float(a)` / `float(b)` warning occurred in a helper test comparing differentiable scalar losses. The test passed; the benchmark uses detached scalar values for progress and did not abort. This warning is not evidence of failed optimization. It remains a test-hygiene issue, not a reason to discard the result.

| Metric | COLOR_AUX | COLOR_MATERIAL_AUX |
|---|---:|---:|
| Correct full-catalog rankings | 19,272 / 20,736 | 20,390 / 20,736 |
| Accuracy | 92.9398148% | 98.3314043% |
| Total errors | 1,464 | 346 |
| Material-involved errors | 798 | 28 |
| All-case-perfect full-catalog models | 0 / 12 | 0 / 12 |
| Original 12-candidate positive-margin passes | 12 / 12 models | 12 / 12 models |
| Minimum full-catalog expected margin | -0.1540646851 | -0.1000825763 |

Paired rescues = **1,153**; new errors = **35**; both-wrong = **311**; both-correct = **19,237**. Material-involved errors that became entirely correct = **724**; new material-involved errors = **4**. The net material-error-count reduction (798 -> 28, 96.49%) is not a count of cases made entirely correct: an error can change its mismatch type while remaining wrong. Total error count fell 76.37%. These compare paired conditions within C145, not different seed sets across C143/C145.

The preregistered zero material residual and zero paired regression criteria both failed. The original-12 preservation condition passed. Do not relabel the strict FAIL as a PASS because the improvement is large.

Treatment residual masks:

```text
SHAPE             294
COLOR              21
MATERIAL           15
SHAPE+MATERIAL     12
COLOR+SHAPE         3
COLOR+MATERIAL      1
```

Shape appears in **309/346 (89.31%)**, material in **28/346**, color in **25/346**. Involvement overlaps across masks. Shape-only accounts for 294/346 (84.97%). This describes the output mismatches; it is not proof that missing shape labels are the unique cause. The former dominant material mismatch is substantially reduced by the tested training intervention, but non-regression and exhaustive composition are not achieved. All 12 treatment models improve total correct counts, yet none is exhaustive-perfect.

**Supported:** on the registered synthetic task, adding the specified material objective to the color-alignment objective yields a large paired improvement, while leaving the two stated failure conditions unresolved.
**Not supported:** automatically discovered semantic factors, general language understanding, a requirement to redesign the architecture, or production readiness. Preserved original-12 rankings are not a new provenance/commit/ANSWER test. C142's scoped PASS and C143's scoped negative remain in force. Gate E remains NOT PASSED.

## C146 — ACTIVE, awaiting user CUDA execution

Experiment `C146-v5e-all-factor-supervised-reference`, stage `V5-E-ALL-FACTOR-SUPERVISED-REFERENCE`.

**Scientific question:** with color and material alignment already present, does adding the remaining shape-alignment term make the unchanged shared encoder solve the complete registered factor/alias catalog on fresh paired seeds?

This is the final **three-factor explicitly supervised reference** in this attribute-loss ladder. It is not a theoretical upper bound and not a proposal to accumulate hand-written attribute objectives in production. Its purpose is to establish whether this finite task can be learned with all available factor correspondence supervision before evaluating less hand-labeled methods or investigating remaining composition failures. Neither outcome alone proves that automatic factor discovery is necessary or achievable.

### One changed training term

```text
Control:   COLOR_MATERIAL_AUX = main CE + 1.0*color CE + 1.0*material CE
Treatment: ALL_FACTOR_AUX     = same objective + 1.0*shape CE
```

Shape pairs are derived from TRAIN_COMBINATION queries/descriptors only: 12 alias expressions versus 4 canonical shapes. `four-sided`, `three-sided` and `six-sided` remain original raw expressions; the unchanged C139 feature tokenizer processes them. There is no tokenizer repair, extra example augmentation, extra full-combination target, new head or model-size change. Each existing color/material coefficient remains 1.0; shape is 0 in control and 1 in treatment. No coefficient sweep or held-out-selected checkpoint.

Held constant: head `feature_dim=49, hidden_dim=64, residual_scale=1.0`; original 24 main queries and eight main candidates; AdamW lr 0.002, weight decay 0, 600 steps, score scale 12; same raw full queries and 64-candidate evaluation manifest. Original C143 feature/scoring/suite helpers are reused. Both heads start from the same copied state within each seed and train with separate optimizers. No inference dictionary or alias substitution.

Fresh seeds **20261661..20261672**, 12 new seeds, 24 trained heads. These are not continuations of C145 checkpoints and not fresh tasks. The same synthetic evaluation has already informed development; the 52 new combinations from C143 are no longer an untouched test set.

```text
Each arm: 12 seeds x 1,728 full-catalog queries = 20,736 rankings
Both arms: 41,472 full-catalog rankings
Additional original-12 controls: 12 seeds x 12 queries x 2 arms = 288 rankings
```

All evaluation remains **ranking-only**, including original-12 controls. No expanded persisted retrieval, provenance validation, commit, recovery or ANSWER. Additional shape supervision changes training computation/gradient balance as well as available labels; equal step counts do not mean compute matching. Per-arm time is diagnostic (fixed arm order, both heads resident), not a production performance comparison.

### Preregistered verdict and stopping rule

- **PASS:** every ALL_FACTOR_AUX full-catalog ranking is correct with a strictly positive finite expected-class margin, on all 12 seeds; original-12 treatment rankings are also all correct with positive margins; all execution controls valid. Report paired rescue/regression counts. If control is also perfect, report the absence of an error contrast rather than replacing seeds.
- **ACCEPTED VALID NEGATIVE / FAIL:** valid execution but any treatment ranking error/nonpositive margin remains, or original-12 safety fails. Report full and group accuracy, all factor masks, individual alias-fit training diagnostics, rescues and new errors. Singleton correspondence fit must not be mislabeled contextual composition.
- **INVALID:** wrong/incomplete C145 report, inconsistent reaggregation, input/manifest/protected hash failure, OOV, unequal initial weights, nonfinite values, evaluation mutation or execution error. Retry C146 after resolving validity; never discard a scientific negative or tune under the same number.

This gate is intentionally different from C145's material-only question, and is fixed before formal C146 evaluation. C145 remains negative regardless of C146. After C146, do **not** add further named attribute losses or silently sweep weights/steps to chase this fixture's 100%. Review the supervised reference and decide the next separately registered generalization/learning or representation question. C147 is not registered by this change. Gate E remains NOT PASSED.

### Implementation and verification

New files: `gate_e_c146_all_factor_alignment.py`, `gate_e_c146_cli.py`, `test_v05_c146_all_factor_alignment.py`, `tools/run_c146.ps1`, this addendum; authoritative handoff updated. No production source, earlier experiment, README, branch history or other project is modified.

The C145 full records are revalidated by recomputing masks, original-12 outcomes, paired counts and ordered seed coverage. The same C143 manifest is regenerated and its accepted byte hash checked, explicitly handling LF versus Windows CRLF serialization without accepting a different manifest. Evaluation cannot mutate the head, query manifest or protected inputs. Both model-only checkpoints are saved, and the report is atomically published; valid scientific FAIL returns CLI exit code 0, execution exceptions return nonzero and retain an invalid marker.

Reviewer: **20/20 new CPU helper tests passed**, with synthetic weights and synthetic full prerequisite records (not the user's checkpoints). Tests cover training-only extraction, hyphenated expressions, control update equality to the explicit C145 treatment formula, paired initialization, gradients, strict gate, masks, full-record reaggregation and serialization hashes. Local production-head source matched Git blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`. Python modules compiled. Full **194-test** focused suite, formal CUDA run and PowerShell execution were **not performed by reviewer**. No registered fresh seed result was inspected.
